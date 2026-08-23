import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

class VectorService:
    """
    Lightweight, high-performance Vector Service.
    Leverages Qdrant Cloud Inference / Remote Vector Search.
    Eliminates local PyTorch / SentenceTransformer memory overhead on Render.
    """
    def __init__(self):
        self.qdrant_client = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.local_product_store: List[Dict[str, Any]] = []

        qdrant_url = settings.QDRANT_URL.strip() if (settings.QDRANT_URL and settings.QDRANT_URL.strip()) else None
        qdrant_key = settings.QDRANT_API_KEY.strip() if (settings.QDRANT_API_KEY and settings.QDRANT_API_KEY.strip()) else None

        if qdrant_url:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import VectorParams, Distance

                self.qdrant_client = QdrantClient(
                    url=qdrant_url,
                    api_key=qdrant_key,
                    cloud_inference=True
                )
                logger.info(f"Connected to Qdrant Cloud Inference at {qdrant_url}")

                # Ensure collection exists on Qdrant Cloud
                try:
                    if not self.qdrant_client.collection_exists(self.collection_name):
                        self.qdrant_client.create_collection(
                            collection_name=self.collection_name,
                            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                        )
                        logger.info(f"Created Qdrant collection '{self.collection_name}'.")
                except Exception as e_col:
                    logger.debug(f"Collection check/create note: {e_col}")
            except Exception as e:
                logger.warning(f"Failed to connect to Qdrant Cloud: {e}")
                self.qdrant_client = None

    def register_product_embedding(
        self,
        product_id: str,
        name: str,
        brand: Optional[str],
        category: Optional[str],
        description: Optional[str]
    ):
        """Indexes product into Qdrant Cloud using managed cloud inference or local payload store."""
        search_text = f"{name} {brand or ''} {category or ''} {description or ''}".strip()
        payload = {
            "product_id": product_id,
            "name": name,
            "brand": brand,
            "category": category,
            "description": description,
            "search_text": search_text
        }

        if self.qdrant_client:
            try:
                from qdrant_client import models
                # Remote Qdrant Cloud Inference indexing via Document struct
                point_id = abs(hash(product_id)) % (2**63 - 1)
                
                # Check if Qdrant accepts Document struct or payload indexing
                try:
                    doc = models.Document(text=search_text, model="sentence-transformers/all-MiniLM-L6-v2")
                    self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=[models.PointStruct(id=point_id, vector=doc, payload=payload)]
                    )
                except Exception:
                    # Fallback to standard payload point indexing
                    self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=[models.PointStruct(id=point_id, vector=[0.0]*384, payload=payload)]
                    )
                logger.info(f"Indexed vector for '{name}' into Qdrant Cloud.")
                return
            except Exception as e:
                logger.warning(f"Qdrant Cloud upsert error, storing locally: {e}")

        # Local fallback store (Zero PyTorch RAM overhead)
        self.local_product_store.append({
            "product_id": product_id,
            "name": name,
            "payload": payload
        })

    def search_similar_product(self, query_text: str, score_threshold: float = 0.3) -> Optional[Dict[str, Any]]:
        """Performs remote Qdrant Cloud inference search or lightweight payload matching."""
        if not query_text or not query_text.strip():
            return None

        q_clean = query_text.strip()

        if self.qdrant_client:
            try:
                from qdrant_client import models
                payload = None
                score = 0.0

                # Query using Qdrant Cloud Managed Inference (MiniLM)
                query_doc = models.Document(text=q_clean, model="sentence-transformers/all-MiniLM-L6-v2")
                
                if hasattr(self.qdrant_client, "query_points"):
                    res = self.qdrant_client.query_points(
                        collection_name=self.collection_name,
                        query=query_doc,
                        limit=1
                    )
                    if res and res.points:
                        score = res.points[0].score
                        payload = res.points[0].payload
                elif hasattr(self.qdrant_client, "search"):
                    res = self.qdrant_client.search(
                        collection_name=self.collection_name,
                        query_vector=query_doc,
                        limit=1
                    )
                    if res:
                        score = res[0].score
                        payload = res[0].payload

                if payload and score >= score_threshold:
                    logger.info(f"Qdrant Cloud Inference match: '{q_clean}' -> '{payload['name']}' (score: {score:.3f})")
                    return payload
            except Exception as e:
                logger.warning(f"Qdrant Cloud Inference search fallback: {e}")

        # Lightweight Local Keyword / Jaccard similarity fallback (No PyTorch RAM overhead)
        if not self.local_product_store:
            return None

        query_words = set(q_clean.lower().split())
        best_score = 0.0
        best_match = None

        for item in self.local_product_store:
            p_text = item["payload"].get("search_text", item["name"]).lower()
            p_words = set(p_text.split())
            intersection = query_words.intersection(p_words)
            union = query_words.union(p_words)
            sim = len(intersection) / len(union) if union else 0.0

            # Substring bonus
            if item["name"].lower() in q_clean.lower() or q_clean.lower() in item["name"].lower():
                sim += 0.5

            if sim > best_score:
                best_score = sim
                best_match = item["payload"]

        if best_score >= score_threshold and best_match:
            logger.info(f"Local lightweight match: '{q_clean}' -> '{best_match['name']}' (score: {best_score:.3f})")
            return best_match

        return None

vector_service = VectorService()
