"""Score exact evidence matches and preserve the retrieval trace."""
from collections import defaultdict
from typing import Any

from .ingestion import normalize_text


def canonical(text: str) -> str:
    return " ".join(normalize_text(text).split())


def evidence_options(question: dict[str, Any]) -> list[dict[str, Any]]:
    return [question, *question.get("alternative_gold", [])]


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [
        (gold["gold_source_id"], gold["gold_page"], canonical(gold["evidence_quote"]))
        for gold in evidence_options(question)
    ]
    ranked = []
    for rank, hit in enumerate(hits[:3], 1):
        text = canonical(hit["text"])
        matched = any(
            sid == hit["document_id"] and page == hit["page"] and quote and quote in text
            for sid, page, quote in evidence
        )
        ranked.append({**hit, "rank": rank, "evidence_hit": matched})
    return {
        "benchmark": question,
        "split": question["split"],
        "top_3": ranked,
        "hit_at_1": bool(ranked and ranked[0]["evidence_hit"]),
        "hit_at_3": any(hit["evidence_hit"] for hit in ranked),
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    groups = defaultdict(list)
    for trace in traces:
        groups[(trace["strategy"], trace["split"])].append(trace)

    summary = {}
    for (strategy, split), group in sorted(groups.items()):
        metrics = {"questions": len(group)}
        for field in ("hit_at_1", "hit_at_3"):
            hits = sum(trace[field] for trace in group)
            metrics[field] = {"hits": hits, "total": len(group), "rate": hits / len(group)}
        summary.setdefault(strategy, {})[split] = metrics
    return summary
