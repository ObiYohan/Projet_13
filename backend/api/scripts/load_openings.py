"""Read data/openings.json, embed each opening, and load it into Milvus.

Run inside the api container once the `standalone` Milvus service is healthy:
    docker compose exec api python -m api.scripts.load_openings
"""

import json
import os
from pathlib import Path

from ..services.chunking import build_opening_chunks
from ..services.embedding_service import EmbeddingService
from ..services.milvus_service import MilvusService

DEFAULT_DATA_PATH = Path(os.environ.get("OPENINGS_DATA_PATH", "/app/data/openings.json"))


def load_openings(data_path: Path = DEFAULT_DATA_PATH) -> None:
    records = json.loads(data_path.read_text(encoding="utf-8"))

    embeddings = EmbeddingService()
    milvus = MilvusService()
    milvus.ensure_collection(dimension=embeddings.dimension)

    chunks = [(record, chunk) for record in records for chunk in build_opening_chunks(record)]
    vectors = embeddings.embed_documents([chunk["text"] for _, chunk in chunks])

    rows = [
        {
            "id": i,
            "vector": vector,
            "lang": chunk["lang"],
            "text": chunk["text"],
            "opening_name": record["opening_name"],
            "opening_name_fr": record.get("opening_name_fr", ""),
            "eco_code": record["eco_code"],
            "moves_san": record["moves_san"],
            "source_url": record["source_url"],
            "description_url": chunk["url"],
        }
        for i, ((record, chunk), vector) in enumerate(zip(chunks, vectors))
    ]
    milvus.insert(rows)
    print(
        f"Loaded {len(records)} opening(s) as {len(rows)} chunk(s) "
        f"into Milvus collection '{milvus.collection_name}'."
    )


if __name__ == "__main__":
    load_openings()
