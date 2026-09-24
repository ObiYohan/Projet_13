import os

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")


class EmbeddingService:
    """Wraps a sentence-transformers model to embed documents and queries."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        return self._model.get_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self._model.encode(
            [text], prompt_name="query", normalize_embeddings=True
        )
        return embedding[0].tolist()
