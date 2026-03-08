import os
from typing import Any
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

load_dotenv()
api_key = os.getenv("QDRANT_API_KEY")
db_url = os.getenv("QDRANT_ENDPOINT")

class QdrantStorage:
    def __init__(self, url: str | None = db_url, collection: str = "docs", dim: int = 768):
        if not url:
            raise ValueError("QDRANT_ENDPOINT is required.")

        self.client = QdrantClient(url=url, api_key=api_key, timeout=30)
        self.collection = collection
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
            )
    
    def upsert(self, ids: list[str], vectors: list[list[float]], payloads: list[dict[str, Any]]) -> None:
        if not (len(ids) == len(vectors) == len(payloads)):
            raise ValueError("ids, vectors, and payloads must have identical lengths.")
        if not ids:
            return

        points = [PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i]) for i in range(len(ids))]
        self.client.upsert(self.collection, points=points)
    
    def search(self, query_vector: list[float], top_k: int = 5) -> dict[str, list[str]]:
        if not query_vector:
            return {"contexts": [], "sources": []}

        response = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            with_payload=True,
            limit=top_k
        )

        contexts = []
        sources = set()
        for result in response.points:
            payload = getattr(result, "payload", None) or {}
            text = payload.get("text", "")
            source = payload.get("source", "")
            if text:
                contexts.append(text)
                if source:
                    sources.add(source)

        return {"contexts": contexts, "sources": list(sources)}
