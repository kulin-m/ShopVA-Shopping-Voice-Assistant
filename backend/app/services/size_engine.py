from typing import Optional, Tuple, List
from collections import Counter
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.models import Product, ProductSize, PurchaseHistory
import logging

logger = logging.getLogger("uvicorn.error")

class SizeDecisionResult:
    def __init__(
        self,
        size: str,
        is_unresolved: bool,
        reason: str,
        available_sizes: List[str] = None,
        requires_user_clarification: bool = False,
        clarification_message: Optional[str] = None
    ):
        self.size = size
        self.is_unresolved = is_unresolved
        self.reason = reason
        self.available_sizes = available_sizes or []
        self.requires_user_clarification = requires_user_clarification
        self.clarification_message = clarification_message

class SizeDecisionEngine:
    def evaluate_size_decision(
        self,
        db: Session,
        user_id: str,
        product: Optional[Product],
        explicit_size: Optional[str] = None
    ) -> SizeDecisionResult:
        """
        Executes brochure-based 5-rule priority size decision engine:
        RULE 1: Explicit size requested by user -> validate against brochure catalog.
        RULE 2: Single size variant in brochure -> auto-select.
        RULE 3: Multiple sizes + history preference -> check if preferred size in brochure -> auto-select.
        RULE 4: Multiple sizes + history preference NOT in brochure -> ask user for size choice.
        RULE 5: Multiple sizes + no clear preference -> mark unresolved and return brochure options.
        """
        if not product:
            return SizeDecisionResult(
                size="__________",
                is_unresolved=True,
                reason="Product not found in supermarket catalog",
                available_sizes=[],
                requires_user_clarification=True,
                clarification_message="Product not found in supermarket catalog."
            )

        catalog_sizes: List[ProductSize] = product.sizes if product.sizes else []
        avail_size_values = [s.size_value for s in catalog_sizes]

        # RULE 1: Explicit size specified by user
        if explicit_size and explicit_size.strip():
            norm_explicit = explicit_size.strip()
            matching_size = next((s for s in avail_size_values if s.lower() == norm_explicit.lower()), None)
            if matching_size:
                return SizeDecisionResult(
                    size=matching_size,
                    is_unresolved=False,
                    reason=f"Explicitly specified valid catalog size: '{matching_size}'",
                    available_sizes=avail_size_values,
                    requires_user_clarification=False
                )
            else:
                sizes_str = ", ".join(avail_size_values) if avail_size_values else "None"
                msg = f"'{norm_explicit}' {product.name} is not listed in the supermarket catalog. Available sizes are {sizes_str}. Please choose a size."
                return SizeDecisionResult(
                    size="__________",
                    is_unresolved=True,
                    reason=f"Requested size '{norm_explicit}' not available in brochure catalog ({sizes_str})",
                    available_sizes=avail_size_values,
                    requires_user_clarification=True,
                    clarification_message=msg
                )

        # RULE 2: Single catalog size variant
        if len(avail_size_values) == 1:
            single_size = avail_size_values[0]
            return SizeDecisionResult(
                size=single_size,
                is_unresolved=False,
                reason=f"Single catalog size variant auto-selected: '{single_size}'",
                available_sizes=avail_size_values,
                requires_user_clarification=False
            )

        if len(avail_size_values) == 0:
            return SizeDecisionResult(
                size="__________",
                is_unresolved=True,
                reason="No size variants defined in supermarket catalog",
                available_sizes=[],
                requires_user_clarification=True,
                clarification_message=f"No size variants defined in supermarket catalog for {product.name}."
            )

        # RULE 3 & 4: Multiple sizes exist -> Check user purchase history
        recent_purchases = (
            db.query(PurchaseHistory)
            .filter(PurchaseHistory.user_id == user_id, PurchaseHistory.product_name.ilike(f"%{product.name}%"))
            .order_by(PurchaseHistory.purchased_at.desc())
            .limit(settings.HISTORY_LIST_COUNT)
            .all()
        )

        size_history = [p.size for p in recent_purchases if p.size and p.size != "__________"]

        if size_history:
            counts = Counter(size_history)
            most_common_size, highest_count = counts.most_common(1)[0]

            if highest_count >= settings.SIZE_PREFERENCE_THRESHOLD:
                # RULE 3: Check if preferred size exists in current brochure catalog
                matching_history_size = next((s for s in avail_size_values if s.lower() == most_common_size.lower()), None)
                if matching_history_size:
                    return SizeDecisionResult(
                        size=matching_history_size,
                        is_unresolved=False,
                        reason=f"Historical preference: selected '{matching_history_size}' ({highest_count}/{len(size_history)} recent purchases)",
                        available_sizes=avail_size_values,
                        requires_user_clarification=False
                    )
                else:
                    # RULE 4: Preferred size from history is NO LONGER available in brochure
                    sizes_str = ", ".join(avail_size_values)
                    msg = f"You usually buy {most_common_size} {product.name}, but {most_common_size} isn't available in this supermarket catalog. Available sizes are {sizes_str}. Please choose a size."
                    return SizeDecisionResult(
                        size="__________",
                        is_unresolved=True,
                        reason=f"Historical preferred size '{most_common_size}' no longer available in brochure catalog ({sizes_str})",
                        available_sizes=avail_size_values,
                        requires_user_clarification=True,
                        clarification_message=msg
                    )

        # RULE 5: No clear historical preference -> Unresolved
        sizes_str = ", ".join(avail_size_values)
        msg = f"Please select a size for {product.name}. Available sizes: {sizes_str}"
        return SizeDecisionResult(
            size="__________",
            is_unresolved=True,
            reason=f"Multiple catalog sizes available ({sizes_str}). No clear historical preference found.",
            available_sizes=avail_size_values,
            requires_user_clarification=True,
            clarification_message=msg
        )

size_decision_engine = SizeDecisionEngine()
