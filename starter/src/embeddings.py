"""Local multilingual E5 embedding adapter."""
from typing import Protocol

from sentence_transformers import SentenceTransformer


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, question: str) -> list[float]:
        ...


class MyEmbedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, local_files_only=True, device="cpu")
        self.dimensions = self.model.get_embedding_dimension()
        if not self.dimensions:
            raise ValueError("Embedding model did not report a dimension")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self.model.encode(
            ["passage: " + text for text in texts],
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

    def embed_query(self, question: str) -> list[float]:
        return self.model.encode(
            "query: " + question, normalize_embeddings=True, show_progress_bar=False
        ).tolist()
