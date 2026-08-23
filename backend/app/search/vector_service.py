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

    def get_vector_diagnostics(self) -> Dict[str, Any]:
        """Safe admin diagnostic method reporting Qdrant collection status without secrets."""
        if not self.qdrant_client:
            return {
                "collection_name": self.collection_name,
                "qdrant_connected": False,
                "collection_exists": False,
                "point_count": len(self.local_product_store),
                "vector_configuration": "Local Payload Store (384-dim fallback)"
            }

        try:
            exists = self.qdrant_client.collection_exists(self.collection_name)
            point_count = 0
            config_str = "Unknown"
            if exists:
                info = self.qdrant_client.get_collection(self.collection_name)
                point_count = getattr(info, "points_count", 0) or 0
                config_str = "384 dims, COSINE (Qdrant Cloud Managed)"

            return {
                "collection_name": self.collection_name,
                "qdrant_connected": True,
                "collection_exists": exists,
                "point_count": point_count,
                "vector_configuration": config_str
            }
        except Exception as e:
            return {
                "collection_name": self.collection_name,
                "qdrant_connected": True,
                "collection_exists": False,
                "point_count": 0,
                "error": str(e)
            }

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
                point_id = abs(hash(product_id)) % (2**63 - 1)
                
                try:
                    doc = models.Document(text=search_text, model="sentence-transformers/all-MiniLM-L6-v2")
                    self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=[models.PointStruct(id=point_id, vector=doc, payload=payload)]
                    )
                except Exception:
                    self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=[models.PointStruct(id=point_id, vector=[0.0]*384, payload=payload)]
                    )
                logger.info(f"Indexed vector for '{name}' into Qdrant Cloud.")
                return
            except Exception as e:
                logger.warning(f"Qdrant Cloud upsert error, storing locally: {e}")

        # Local fallback store (Zero PyTorch RAM overhead)
        # Update existing point if product_id exists to ensure idempotency
        for item in self.local_product_store:
            if item["product_id"] == product_id:
                item["name"] = name
                item["payload"] = payload
                return

        self.local_product_store.append({
            "product_id": product_id,
            "name": name,
            "payload": payload
        })

    def search_similar_products(self, query_text: str, limit: int = 5, score_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """Performs multi-candidate Qdrant Cloud inference search or lightweight payload matching."""
        if not query_text or not query_text.strip():
            return []

        q_clean = query_text.strip()
        matches = []

        if self.qdrant_client:
            try:
                from qdrant_client import models
                query_doc = models.Document(text=q_clean, model="sentence-transformers/all-MiniLM-L6-v2")
                
                points = []
                if hasattr(self.qdrant_client, "query_points"):
                    res = self.qdrant_client.query_points(
                        collection_name=self.collection_name,
                        query=query_doc,
                        limit=limit
                    )
                    if res and res.points:
                        points = res.points
                elif hasattr(self.qdrant_client, "search"):
                    res = self.qdrant_client.search(
                        collection_name=self.collection_name,
                        query_vector=query_doc,
                        limit=limit
                    )
                    if res:
                        points = res

                for pt in points:
                    score = getattr(pt, "score", 0.0)
                    payload = getattr(pt, "payload", {}) or {}
                    if payload and score >= score_threshold:
                        res_dict = dict(payload)
                        res_dict["score"] = score
                        matches.append(res_dict)
                        logger.info(f"🔎 [QDRANT CANDIDATE] Query='{q_clean}' | Candidate='{payload.get('name')}' | Score={score:.3f}")

                if matches:
                    return matches
            except Exception as e:
                logger.warning(f"Qdrant Cloud Inference search fallback: {e}")

        # Lightweight Local Keyword / Jaccard similarity fallback (No PyTorch RAM overhead)
        if not self.local_product_store:
            return []

        query_words = set(q_clean.lower().split())

        for item in self.local_product_store:
            p_text = item["payload"].get("search_text", item["name"]).lower()
            p_words = set(p_text.split())
            intersection = query_words.intersection(p_words)
            union = query_words.union(p_words)
            sim = len(intersection) / len(union) if union else 0.0

            # Substring bonus
            if item["name"].lower() in q_clean.lower() or q_clean.lower() in item["name"].lower():
                sim += 0.5

            if sim >= score_threshold:
                res_dict = dict(item["payload"])
                res_dict["score"] = sim
                matches.append(res_dict)
                logger.info(f"🔎 [LOCAL CANDIDATE] Query='{q_clean}' | Candidate='{item['name']}' | Score={sim:.3f}")

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    def search_similar_product(self, query_text: str, score_threshold: float = 0.3) -> Optional[Dict[str, Any]]:
        """Single candidate search wrapper for 100% backward compatibility."""
        results = self.search_similar_products(query_text=query_text, limit=1, score_threshold=score_threshold)
        return results[0] if results else None

vector_service = VectorService()
