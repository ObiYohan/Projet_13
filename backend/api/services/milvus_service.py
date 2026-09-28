import os
import re

from pymilvus import MilvusClient, MilvusException

ECO_CODE = re.compile(r"[A-E]\d\d")

DEFAULT_HOST = os.environ.get("MILVUS_HOST", "standalone")
DEFAULT_PORT = os.environ.get("MILVUS_PORT", "19530")
COLLECTION_NAME = "openings"
OUTPUT_FIELDS = [
    "lang", "text", "opening_name", "opening_name_fr", "eco_code",
    "moves_san", "source_url", "description_url",
]


class MilvusServiceError(Exception):
    """Base error for failures while talking to Milvus."""


class MilvusService:
    """Encapsulates the connection to Milvus and the openings collection."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: str = DEFAULT_PORT,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self.collection_name = collection_name
        self._client = MilvusClient(uri=f"http://{host}:{port}")

    def ensure_collection(self, dimension: int) -> None:
        """(Re)create the collection with the given vector dimension."""
        if self._client.has_collection(collection_name=self.collection_name):
            self._client.drop_collection(collection_name=self.collection_name)
        self._client.create_collection(
            collection_name=self.collection_name,
            dimension=dimension,
            metric_type="COSINE",
        )

    def count(self) -> int:
        """Number of chunks stored in the collection (0 if it doesn't exist)."""
        try:
            if not self._client.has_collection(collection_name=self.collection_name):
                return 0
            rows = self._client.query(
                collection_name=self.collection_name, filter="", output_fields=["count(*)"]
            )
        except MilvusException as exc:
            raise MilvusServiceError(f"Failed to count Milvus records: {exc}") from exc
        return rows[0]["count(*)"] if rows else 0

    def insert(self, records: list[dict]) -> None:
        try:
            self._client.insert(collection_name=self.collection_name, data=records)
        except MilvusException as exc:
            raise MilvusServiceError(f"Failed to insert records into Milvus: {exc}") from exc

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        lang: str | None = None,
        eco: str | None = None,
    ) -> list[dict]:
        """Nearest chunks to `query_vector`, restricted to a language ("fr" /
        "en") and / or an ECO code when given."""
        conditions = []
        if lang in ("fr", "en"):
            conditions.append(f'lang == "{lang}"')
        if eco and ECO_CODE.fullmatch(eco):
            conditions.append(f'eco_code == "{eco}"')
        try:
            results = self._client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=top_k,
                output_fields=OUTPUT_FIELDS,
                filter=" and ".join(conditions),
            )
        except MilvusException as exc:
            raise MilvusServiceError(f"Milvus search failed: {exc}") from exc

        hits = results[0] if results else []
        return [{"id": hit["id"], "score": hit["distance"], **hit["entity"]} for hit in hits]
