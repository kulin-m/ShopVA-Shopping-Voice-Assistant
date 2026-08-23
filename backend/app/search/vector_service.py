import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

class VectorService:
    def __init__(self):
        self._embedding_model = None
        self.qdrant_client = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.local_product_store: List[Dict[str, Any]] = []

        # Initialize Qdrant client
        if settings.QDRANT_URL and settings.QDRANT_URL.strip():
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import VectorParams, Distance
                
                self.qdrant_client = QdrantClient(
                    url=settings.QDRANT_URL.strip(),
                    api_key=settings.QDRANT_API_KEY.strip() if settings.QDRANT_API_KEY else None
                )
                logger.info(f"Connected to Qdrant Cloud at {settings.QDRANT_URL}")
                
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
                logger.warning(f"Failed to connect to Qdrant cloud: {e}")

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            try:
                logger.info("Lazy-loading sentence-transformers MiniLM model...")
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("MiniLM embedding model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading MiniLM model: {e}")
        return self._embedding_model

    def generate_embedding(self, text: str) -> List[float]:
        model = self.embedding_model
        if not model:
            return []
        vector = model.encode(text, convert_to_numpy=True)
        return vector.tolist()

    def register_product_embedding(self, product_id: str, name: str, brand: Optional[str], category: Optional[str], description: Optional[str]):
        search_text = f"{name} {brand or ''} {category or ''} {description or ''}".strip()
        vector = self.generate_embedding(search_text)

        payload = {
            "product_id": product_id,
            "name": name,
            "brand": brand,
            "category": category,
            "description": description
        }

        if self.qdrant_client:
            try:
                from qdrant_client.models import PointStruct
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[PointStruct(id=abs(hash(product_id)) % (2**63 - 1), vector=vector, payload=payload)]
                )
                logger.info(f"Indexed vector for '{name}' into Qdrant Cloud.")
                return
            except Exception as e:
                logger.warning(f"Qdrant upsert error, storing locally: {e}")

        self.local_product_store.append({
            "product_id": product_id,
            "name": name,
            "vector": vector,
            "payload": payload
        })

    def search_similar_product(self, query_text: str, score_threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        if not query_text:
            return None

        query_vector = self.generate_embedding(query_text)
        if not query_vector:
            return None

        if self.qdrant_client:
            try:
                payload = None
                score = 0.0

                if hasattr(self.qdrant_client, "query_points"):
                    res = self.qdrant_client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        limit=1
                    )
                    if res and res.points:
                        score = res.points[0].score
                        payload = res.points[0].payload
                elif hasattr(self.qdrant_client, "search"):
                    res = self.qdrant_client.search(
                        collection_name=self.collection_name,
                        query_vector=query_vector,
                        limit=1
                    )
                    if res:
                        score = res[0].score
                        payload = res[0].payload

                if payload and score >= score_threshold:
                    logger.info(f"Qdrant vector match: '{query_text}' -> '{payload['name']}' (score: {score:.3f})")
                    return payload
            except Exception as e:
                logger.warning(f"Qdrant search fallback: {e}")

        # Local fallback vector search
        if not self.local_product_store:
            return None

        import numpy as np
        best_score = -1.0
        best_match = None

        q_vec = np.array(query_vector)
        norm_q = np.linalg.norm(q_vec)
        if norm_q == 0:
            return None

        for item in self.local_product_store:
            p_vec = np.array(item["vector"])
            norm_p = np.linalg.norm(p_vec)
            if norm_p == 0:
                continue
            similarity = float(np.dot(q_vec, p_vec) / (norm_q * norm_p))
            if similarity > best_score:
                best_score = similarity
                best_match = item["payload"]

        if best_score >= score_threshold:
            logger.info(f"Local vector match: '{query_text}' -> '{best_match['name']}' (score: {best_score:.3f})")
            return best_match

        return None

vector_service = VectorService()
