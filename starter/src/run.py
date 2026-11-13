"""Run the fixed Day 06 benchmark and export reproducible traces."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import file_digest
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
import re
from statistics import mean
from time import perf_counter

from dotenv import load_dotenv
import psycopg

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import canonical, evaluate_query, evidence_options, summarize
from .ingestion import load_pdf
from .store import PgVectorStore

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
CHUNK_SIZE = 1200
OVERLAP = 200
STRATEGY_INDEX = {"A": "A", "B": "B", "C": "B"}
logger = logging.getLogger(__name__)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_corpus(manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpus = {}
    for source in manifest["sources"]:
        sid = source["source_id"]
        if not source["counted_pages"]:
            continue
        relative_path = source["source_path_or_url"]
        pdf_path = ROOT / relative_path
        with pdf_path.open("rb") as stream:
            checksum = file_digest(stream, "sha256").hexdigest()
        if checksum != source["snapshot_version"]["sha256"]:
            raise ValueError(f"{sid}: PDF SHA-256 differs from manifest")
        pages = load_pdf(pdf_path, sid, relative_path)
        if len(pages) != source["physical_pages"]:
            raise ValueError(f"{sid}: PDF page count differs from manifest")
        page_specs = {spec["physical_page_number"]: spec for spec in source["pages"]}
        if set(page_specs) != set(range(1, len(pages) + 1)):
            raise ValueError(f"{sid}: incomplete page list")
        for page in pages:
            spec = page_specs[page.page]
            if not spec["counted_in_30_page_quota"]:
                continue
            if not page.text or len(canonical(page.text)) != spec["normalized_char_count"]:
                raise ValueError(f"{spec['page_id']}: extracted text differs from manifest count")
            key = sid, page.page
            if key in corpus:
                raise ValueError(f"Duplicate page {key}")
            page.metadata.update(page_id=spec["page_id"], topic=source["topic"], language=source["language"])
            corpus[key] = page
    if len(corpus) < 30 or len(corpus) != manifest["total_counted_pages"]:
        raise ValueError("Expected the manifest's selected corpus and at least 30 usable pages")
    return corpus


def load_questions(path, corpus):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    splits = {"dev": [], "test": []}
    seen_ids = set()
    topics = {page.metadata["topic"] for page in corpus.values()}
    for row in rows:
        qid = row["id"]
        if qid in seen_ids or row["split"] not in splits or not row["question"].strip():
            raise ValueError(f"Invalid or duplicate question {qid}")
        seen_ids.add(qid)
        splits[row["split"]].append(row)
        if not row["expected_answer"].strip():
            raise ValueError(f"{qid}: empty expected answer")
        for gold in evidence_options(row):
            page = corpus.get((gold["gold_source_id"], gold["gold_page"]))
            quote = canonical(gold["evidence_quote"])
            if not page or not quote or quote not in canonical(page.text):
                raise ValueError(f"{qid}: evidence missing from its selected source page")
        filters = row.get("filter", {})
        if filters and (filters.keys() != {"topic"} or filters["topic"] not in topics):
            raise ValueError(f"{qid}: invalid topic filter")
    if len(splits["dev"]) < 15 or len(splits["test"]) < 5:
        raise ValueError("Expected at least 15 dev and 5 test questions")
    if sum(bool(row.get("filter")) for row in rows) < 3 or not any(
        row.get("filter") for row in splits["test"]
    ):
        raise ValueError("Expected at least 3 filtered questions, including at least 1 test question")
    return splits


def ingest(corpus, model, store):
    snapshots = {}
    stats = {}
    store.create_schema()
    for name, split_page in (
        ("A", lambda page: fixed_size(page, CHUNK_SIZE, OVERLAP)),
        ("B", lambda page: by_paragraph(page, CHUNK_SIZE)),
    ):
        start = perf_counter()
        chunks = [chunk for page in corpus.values() for chunk in split_page(page)]
        texts = [chunk.text for chunk in chunks]
        token_counts = [
            len(ids) for ids in model.model.tokenizer(
                ["passage: " + text for text in texts], truncation=False, verbose=False
            )["input_ids"]
        ]
        if max(token_counts) > model.model.max_seq_length:
            raise ValueError(f"{name}: chunk exceeds the model token limit")
        vectors = model.embed_documents(texts)
        store.upsert(name, chunks, vectors)
        elapsed = perf_counter() - start
        initial_ids = store.snapshot_ids(name)
        store.upsert(name, chunks, vectors)
        if initial_ids != sorted(chunk.chunk_id for chunk in chunks) or store.snapshot_ids(name) != initial_ids:
            raise RuntimeError(f"{name}: snapshot changed during idempotence check")
        lengths = [len(text) for text in texts]
        stats[name] = {
            "chunks": len(chunks),
            "characters": {"min": min(lengths), "mean": mean(lengths), "max": max(lengths), "total": sum(lengths)},
            "passage_tokens": {"min": min(token_counts), "mean": mean(token_counts),
                               "max": max(token_counts), "total": sum(token_counts)},
            "ingest_seconds": elapsed,
            "external_cost_usd": 0,
            "repeat_ingest_same_ids": True,
        }
        snapshots[name] = chunks
        logger.info("Stored %s: %d chunks in %.2fs", name, len(chunks), elapsed)
    stats["C"] = {**stats["B"], "ingest_seconds": None, "shared_snapshot": "B"}
    return snapshots, stats


def retrieve(rows, model, store):
    traces = []
    for question in rows:
        vector = model.embed_query(question["question"])
        for strategy, index in STRATEGY_INDEX.items():
            filters = question.get("filter", {}) if strategy == "C" else {}
            start = perf_counter()
            hits = store.search(index, vector, filters=filters)
            seconds = perf_counter() - start
            trace = evaluate_query(question, hits)
            traces.append({**trace, "strategy": strategy, "applied_filter": filters,
                           "search_seconds": seconds})
    return traces


def write_audit_samples(output, corpus, dev, snapshots, test_traces):
    coherence = []
    for question in dev[:10]:
        page = corpus[question["gold_source_id"], question["gold_page"]]
        quote = canonical(question["evidence_quote"])
        # A collapsed whitespace offset can be mapped back via the same evidence
        # pattern with a flexible separator for the preserved paragraph breaks.
        pattern = r"\s+".join(re.escape(word) for word in quote.split())
        offset = re.search(pattern, page.text).start()
        for strategy, index in STRATEGY_INDEX.items():
            candidates = [
                chunk for chunk in snapshots[index]
                if (chunk.document_id, chunk.page) == (page.document_id, page.page)
                and chunk.metadata["char_start"] <= offset < chunk.metadata["char_end"]
            ]
            chunk = min(candidates, key=lambda c: c.metadata["char_start"], default=None)
            coherence.append({"question_id": question["id"], "strategy": strategy,
                              "page_id": page.metadata["page_id"], "source_offset": offset,
                              "chunk": asdict(chunk) if chunk else None, "score": None, "reason": ""})
    write_jsonl(output / "coherence_samples.jsonl", coherence)
    audit = []
    for trace in test_traces:
        row = trace["benchmark"]
        audit.append({
            "question_id": row["id"], "strategy": trace["strategy"],
            "grounding_score": None, "grounding_reason": "",
            "filter_compliant": None,
            "metadata": [{"chunk_id": hit["chunk_id"], "correct_and_complete": None, "reason": ""}
                         for hit in trace["top_3"]],
        })
    write_jsonl(output / "test_audit_template.jsonl", audit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(args.output / "ingestion.log", encoding="utf-8", mode="w")],
    )
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    load_dotenv(STARTER / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("DATABASE_URL is missing. Copy starter/.env.example to starter/.env.")
    corpus = load_corpus(ROOT / "data" / "manifest.json")
    questions = load_questions(ROOT / "benchmark" / "questions.jsonl", corpus)
    model = MyEmbedder(str(STARTER / "models" / "multilingual-e5-small"))
    store = PgVectorStore(database_url, model.dimensions)
    with psycopg.connect(database_url) as conn:
        postgres, pgvector = conn.execute("""
            SELECT current_setting('server_version'), extversion
            FROM pg_extension WHERE extname = 'vector'
        """).fetchone() or (None, None)
    if pgvector is None:
        raise RuntimeError("PostgreSQL database is missing the vector extension")
    snapshots, stats = ingest(corpus, model, store)
    dev = retrieve(questions["dev"], model, store)
    dev_summary = summarize(dev)
    selected = max(STRATEGY_INDEX, key=lambda strategy: (
        dev_summary[strategy]["dev"]["hit_at_3"]["hits"],
        dev_summary[strategy]["dev"]["hit_at_1"]["hits"],
        -stats[strategy]["chunks"],
    ))
    write_jsonl(args.output / "dev_traces.jsonl", dev)
    write_json(args.output / "selection.json", {"strategy": selected, "dev_metrics": dev_summary})
    logger.info("Selected %s on dev before test retrieval", selected)
    test = retrieve(questions["test"], model, store)
    write_jsonl(args.output / "test_traces.jsonl", test)
    write_audit_samples(args.output, corpus, questions["dev"], snapshots, test)
    write_json(args.output / "summary.json", {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection": selected,
        "pages": len(corpus),
        "model": "intfloat/multilingual-e5-small",
        "dimensions": model.dimensions,
        "versions": {**{name: version(name) for name in ("pypdf", "psycopg", "sentence-transformers", "torch")},
                     "postgresql": postgres, "pgvector": pgvector},
        "metric": "exact cosine",
        "chunk_size_chars": CHUNK_SIZE,
        "fixed_overlap_chars": OVERLAP,
        "strategy_stats": stats,
        "metrics": summarize(dev + test),
    })


if __name__ == "__main__":
    main()
