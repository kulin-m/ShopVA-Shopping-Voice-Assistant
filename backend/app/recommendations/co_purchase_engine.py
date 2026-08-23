from typing import List, Dict, Any, Set
from collections import Counter, defaultdict
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.models import ShoppingList, ShoppingItem, Product
from app.schemas.recommendation import SuggestionItem, SuggestionResponse
from app.services.size_engine import size_decision_engine
from app.search.vector_service import vector_service
import logging

logger = logging.getLogger("uvicorn.error")

class CoPurchaseRecommendationEngine:
    def generate_recommendations(self, db: Session, user_id: str, current_list_id: str) -> SuggestionResponse:
        """
        Analyzes the user's last N completed lists to calculate co-purchase patterns with items in current list.
        Validates every candidate recommendation against the brochure/catalog:
        - If candidate does NOT exist in brochure catalog, suppresses the recommendation.
        - Uses SizeDecisionEngine to resolve the preferred catalog size for recommendations.
        """
        # 1. Fetch current active shopping list items
        current_items = (
            db.query(ShoppingItem)
            .filter(ShoppingItem.list_id == current_list_id)
            .all()
        )
        if not current_items:
            return SuggestionResponse(suggestions=[])

        current_item_names = {item.product_name.lower().strip() for item in current_items}

        # 2. Fetch last N completed lists for the user
        completed_lists = (
            db.query(ShoppingList)
            .filter(ShoppingList.user_id == user_id, ShoppingList.status == "COMPLETED")
            .order_by(ShoppingList.updated_at.desc())
            .limit(settings.HISTORY_LIST_COUNT)
            .all()
        )

        total_lists_count = len(completed_lists)
        if total_lists_count == 0:
            return SuggestionResponse(suggestions=[])

        # Co-occurrence tracking: candidate_name -> trigger_item_name -> list_count
        co_occurrences = defaultdict(lambda: defaultdict(int))

        for lst in completed_lists:
            list_item_names = {item.product_name.strip() for item in lst.items if item.product_name}
            list_item_names_lower = {name.lower(): name for name in list_item_names}

            # Check which items from current list are present in this completed list
            triggers_in_list = current_item_names.intersection(list_item_names_lower.keys())

            for trigger in triggers_in_list:
                for candidate_lower, original_name in list_item_names_lower.items():
                    if candidate_lower not in current_item_names:
                        co_occurrences[original_name][trigger] += 1

        # Rank and validate suggestions against Brochure Catalog
        suggestions: List[SuggestionItem] = []

        total_catalog_products = db.query(Product).count()

        for candidate_name, trigger_dict in co_occurrences.items():
            # ── Brochure Catalog Validation (Requirement 21) ─────────────────
            catalog_product_name = candidate_name
            suggested_size = None

            if total_catalog_products > 0:
                product = db.query(Product).filter(Product.name.ilike(f"%{candidate_name}%")).first()
                if not product:
                    vector_match = vector_service.search_similar_product(candidate_name)
                    if vector_match:
                        product = db.query(Product).filter(Product.id == vector_match["product_id"]).first()

                # Suppress recommendation if candidate product does NOT exist in supermarket catalog
                if not product:
                    logger.info(f"Smart Suggestion suppressed: '{candidate_name}' is not in current brochure catalog.")
                    continue

                catalog_product_name = product.name
                # ── Brochure Catalog Size Resolution (Requirement 22) ────────────
                size_res = size_decision_engine.evaluate_size_decision(db, user_id, product)
                suggested_size = size_res.size if (not size_res.is_unresolved and size_res.size != "__________") else None

            # Pick strongest co-purchased trigger
            best_trigger_lower, count = max(trigger_dict.items(), key=lambda x: x[1])
            best_trigger_name = best_trigger_lower.capitalize()

            reason = (
                f"You bought {catalog_product_name} with {best_trigger_name} in "
                f"{count} of your last {total_lists_count} shopping lists."
            )
            freq_text = f"Bought together {count} / {total_lists_count} recent lists"

            suggestions.append(
                SuggestionItem(
                    product_name=catalog_product_name,
                    suggested_size=suggested_size,
                    reason=reason,
                    frequency_text=freq_text,
                    co_occurrence_count=count,
                    total_lists_analyzed=total_lists_count
                )
            )

        # Sort by co-occurrence count descending
        suggestions.sort(key=lambda s: s.co_occurrence_count, reverse=True)

        return SuggestionResponse(suggestions=suggestions[:5])

co_purchase_engine = CoPurchaseRecommendationEngine()
