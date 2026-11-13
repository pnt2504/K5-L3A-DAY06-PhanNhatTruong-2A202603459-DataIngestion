"""Persist snapshots and run exact cosine search in PostgreSQL."""
from math import isfinite
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not isinstance(dimensions, int) or dimensions <= 0:
            raise ValueError("Expected a positive vector dimension")
        self.database_url = database_url
        self.dimensions = dimensions

    def _vector(self, values: list[float]) -> str:
        if len(values) != self.dimensions or not all(isfinite(value) for value in values):
            raise ValueError(f"Expected {self.dimensions} finite embedding values")
        if not any(values):
            raise ValueError("Cosine distance requires a nonzero vector")
        return "[" + ",".join(str(value) for value in values) + "]"

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS day06_chunks (
                    strategy text NOT NULL CHECK (strategy IN ('A', 'B')),
                    chunk_id text NOT NULL,
                    document_id text NOT NULL,
                    source text NOT NULL,
                    page integer NOT NULL CHECK (page > 0),
                    text text NOT NULL,
                    metadata jsonb NOT NULL,
                    embedding vector({dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )
            """).format(dimensions=sql.Literal(self.dimensions)))

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace one strategy's complete snapshot in a single transaction."""
        rows = [
            (strategy, c.chunk_id, c.document_id, c.source, c.page, c.text,
             Jsonb(c.metadata), self._vector(vector))
            for c, vector in zip(chunks, vectors, strict=True)
        ]
        if strategy not in {"A", "B"} or not rows:
            raise ValueError("Expected a nonempty snapshot for A or B")
        with psycopg.connect(self.database_url) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("day06_chunks:" + strategy,))
            cursor.execute("DELETE FROM day06_chunks WHERE strategy = %s", (strategy,))
            cursor.executemany("""
                INSERT INTO day06_chunks
                    (strategy, chunk_id, document_id, source, page, text, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
            """, rows)

    def snapshot_ids(self, strategy: str) -> list[str]:
        with psycopg.connect(self.database_url) as conn:
            rows = conn.execute("""
                SELECT chunk_id FROM day06_chunks WHERE strategy = %s ORDER BY chunk_id
            """, (strategy,)).fetchall()
        return [row[0] for row in rows]

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        if filters and (filters.keys() != {"topic"} or not isinstance(filters["topic"], str)
                        or not filters["topic"].strip()):
            raise ValueError("Only a string topic filter is supported")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            rows = conn.execute("""
                SELECT chunk_id, document_id, source, page, text, metadata,
                       embedding <=> %s::vector AS distance
                FROM day06_chunks
                WHERE strategy = %s AND metadata @> %s
                ORDER BY distance, chunk_id
                LIMIT %s
            """, (self._vector(query_vector), strategy, Jsonb(filters), top_k)).fetchall()
        for row in rows:
            row["score"] = 1 - row["distance"]
        return rows
