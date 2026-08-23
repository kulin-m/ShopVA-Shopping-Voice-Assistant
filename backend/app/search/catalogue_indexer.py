import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.database.models import Product, ProductSize
from app.search.vector_service import vector_service
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

class CatalogueIndexerService:
    """
    Dedicated Service for indexing the PostgreSQL Product Catalogue into Qdrant Cloud.
    Maintains full idempotency and preserves 384-dimensional vector payloads.
    """
    def index_all_products(self, db: Session) -> Dict[str, Any]:
        products: List[Product] = db.query(Product).all()
        total_products = len(products)
        indexed_count = 0
        failed_count = 0

        logger.info(f"🚀 [CATALOGUE INDEXER] Starting re-indexing for {total_products} products into Qdrant ('{settings.QDRANT_COLLECTION_NAME}')...")

        for prod in products:
            try:
                vector_service.register_product_embedding(
                    product_id=prod.id,
                    name=prod.name,
                    brand=prod.brand,
                    category=prod.category,
                    description=prod.description
                )
                indexed_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to index product ID={prod.id} ('{prod.name}'): {e}")

        logger.info(f"✅ [CATALOGUE INDEXER] Indexing completed: Total={total_products}, Indexed={indexed_count}, Failed={failed_count}")
        return {
            "total_products": total_products,
            "indexed": indexed_count,
            "failed": failed_count,
            "collection_name": settings.QDRANT_COLLECTION_NAME
        }

catalogue_indexer = CatalogueIndexerService()
