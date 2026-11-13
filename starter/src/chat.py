"""Serve a local chat UI backed by the Day 06 vector index."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import re
from threading import Lock

from dotenv import load_dotenv

from .embeddings import MyEmbedder
from .store import PgVectorStore

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
PAGE = ROOT / "docs" / "day06-chat.html"
SENTENCES = re.compile(r"(?<=[.!?…])\s+|\n\s*\n|\s+(?=•)")


class DocumentChat:
    def __init__(self, model, store, sources):
        self.model = model
        self.store = store
        self.sources = sources
        self.model_lock = Lock()
        self.topics = {source["topic"] for source in sources.values()}

    def answer(self, question, topic):
        with self.model_lock:
            query_vector = self.model.embed_query(question)
        hits = self.store.search("B", query_vector, filters={"topic": topic} if topic else None)
        if not hits:
            return {"answer": "", "sources": [], "answer_source": None}

        candidates = []
        for rank, hit in enumerate(hits, 1):
            for part in SENTENCES.split(hit["text"]):
                passage = " ".join(part.split()).removeprefix("• ").strip()
                if len(passage) >= 25:
                    candidates.append((rank, passage))
        if not candidates:
            candidates = [(1, hits[0]["text"])]
        with self.model_lock:
            vectors = self.model.embed_documents([text for _, text in candidates])
        best_rank, best_text = max(
            zip(candidates, vectors, strict=True),
            key=lambda pair: sum(a * b for a, b in zip(query_vector, pair[1], strict=True)),
        )[0]

        sources = [
            {
                "rank": rank, "title": self.sources[hit["document_id"]]["title"],
                "page": hit["page"], "score": hit["score"], "text": hit["text"],
            }
            for rank, hit in enumerate(hits, 1)
        ]
        return {"answer": best_text, "sources": sources, "answer_source": best_rank}


def make_handler(chat):
    class Handler(BaseHTTPRequestHandler):
        def send_content(self, status, mime, content):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def send_json(self, status, data):
            self.send_content(
                status, "application/json; charset=utf-8",
                json.dumps(data, ensure_ascii=False).encode("utf-8"),
            )

        def do_GET(self):
            if self.path == "/":
                self.send_content(200, "text/html; charset=utf-8", PAGE.read_bytes())
            else:
                self.send_json(404, {"error": "Không tìm thấy trang."})

        def do_POST(self):
            if self.path != "/api/chat":
                self.send_json(404, {"error": "Không tìm thấy đường dẫn."})
                return
            if self.headers.get_content_type() != "application/json":
                self.send_json(415, {"error": "Yêu cầu phải ở định dạng JSON."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError
                body = json.loads(self.rfile.read(length))
                question = body.get("question", "") if isinstance(body, dict) else ""
                topic = body.get("topic", "") if isinstance(body, dict) else ""
                if not isinstance(question, str) or not 1 <= len(question.strip()) <= 600:
                    raise ValueError
                if not isinstance(topic, str) or (topic and topic not in chat.topics):
                    raise ValueError
            except (ValueError, UnicodeError):
                self.send_json(400, {"error": "Nhập câu hỏi từ 1 đến 600 ký tự và chọn chủ đề hợp lệ."})
                return
            try:
                result = chat.answer(question.strip(), topic)
            except Exception:
                logging.exception("Chat retrieval failed")
                self.send_json(503, {"error": "Không truy xuất được. Kiểm tra pgvector và dữ liệu đã nạp."})
                return
            self.send_json(200, result)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    load_dotenv(STARTER / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL is missing from starter/.env")
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    sources = {s["source_id"]: s for s in manifest["sources"] if s["counted_pages"]}
    model = MyEmbedder(str(STARTER / "models" / "multilingual-e5-small"))
    store = PgVectorStore(url, model.dimensions)
    if not store.snapshot_ids("B"):
        parser.error("Snapshot B is empty. Run python -m src.run from starter first.")
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(DocumentChat(model, store, sources))) as server:
        print(f"Day 06 Chat: http://127.0.0.1:{args.port}/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
