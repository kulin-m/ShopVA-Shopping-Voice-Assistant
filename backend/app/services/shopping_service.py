import re
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.core.config import settings
from app.database.models import ShoppingList, ShoppingItem, Product, ProductSize, PurchaseHistory
from app.schemas.command import ParsedCommand, IntentEnum, CommandResponse
from app.services.size_engine import size_decision_engine
from app.search.vector_service import vector_service

logger = logging.getLogger("uvicorn.error")

SIZE_REGEX = r'\b(\d+(?:\.\d+)?)\s*(ml|milliliter|milliliters|millilitre|millilitres|l|liter|liters|litre|litres|g|gram|grams|kg|kilogram|kilograms|oz|lbs|pound|pounds)\b'

def normalize_product_query(query_text: str) -> str:
    """
    Normalizes user item string for catalog resolution:
    - Strips explicit sizes (e.g. 500g, 1kg, 650ml)
    - Strips standalone units and 'of' (e.g. packets of, bottles of)
    - Strips command verbs (add, buy, get, need)
    - Trims whitespace and converts to lowercase
    """
    if not query_text:
        return ""
    text = query_text.strip().lower()
    text = re.sub(SIZE_REGEX, '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*(?:add|include|buy|i need|put|get|want|at|please)\b\s*', '', text, flags=re.IGNORECASE)

    stop_words = ["of", "packet", "packets", "bottle", "bottles", "pack", "packs", "can", "cans", "bag", "bags", "piece", "pieces", "pcs", "gram", "grams", "kg", "ml", "liter", "liters", "litre", "litres"]
    for sw in stop_words:
        text = re.sub(r'\b' + re.escape(sw) + r'\b', '', text, flags=re.IGNORECASE)

    text = re.sub(r'\b\d+\b', '', text)
    cleaned = re.sub(r'\s+', ' ', text).strip()
    return cleaned if cleaned else query_text.strip().lower()

class ShoppingService:
    def get_or_create_active_list(self, db: Session, user_id: str) -> ShoppingList:
        shopping_list = (
            db.query(ShoppingList)
            .filter(ShoppingList.user_id == user_id, ShoppingList.status == "ACTIVE")
            .first()
        )
        if not shopping_list:
            shopping_list = ShoppingList(user_id=user_id, status="ACTIVE")
            db.add(shopping_list)
            db.commit()
            db.refresh(shopping_list)
        return shopping_list

    def resolve_catalogue_product(self, db: Session, raw_query: str) -> Optional[Product]:
        """
        4-Step Robust Catalogue Resolution Pipeline:
        Step 1: Exact DB normalized name match
        Step 2: Database lexical / substring match
        Step 3: Qdrant Cloud semantic search (Top-K candidates with PRODUCT_SIMILARITY_THRESHOLD)
        Step 4: PostgreSQL candidate validation (PostgreSQL is authoritative source of truth)
        """
        cleaned = normalize_product_query(raw_query)
        if not cleaned:
            logger.warning(f"[CATALOGUE RESOLUTION] query='{raw_query}' (clean='') | exact_match=false | lexical_match=false | validated_product_id=null | result=PRODUCT_NOT_IN_CATALOGUE")
            return None

        # Step 1: Exact normalized name match
        product = db.query(Product).filter(func.lower(Product.name) == cleaned).first()
        if product:
            logger.info(f"🔎 [CATALOGUE RESOLUTION] query='{raw_query}' (clean='{cleaned}') | exact_match=true | validated_product_id='{product.id}' | resolved_product='{product.name}' | category='{product.category}' | result=VALID")
            return product

        # Step 2: Lexical DB Substring / ILIKE Match
        candidates = db.query(Product).filter(
            or_(
                Product.name.ilike(f"%{cleaned}%"),
                Product.category.ilike(f"%{cleaned}%"),
                Product.brand.ilike(f"%{cleaned}%")
            )
        ).all()
        if candidates:
            best_lexical = min(candidates, key=lambda p: abs(len(p.name) - len(cleaned)))
            logger.info(f"🔎 [CATALOGUE RESOLUTION] query='{raw_query}' (clean='{cleaned}') | lexical_match=true | validated_product_id='{best_lexical.id}' | resolved_product='{best_lexical.name}' | category='{best_lexical.category}' | result=VALID")
            return best_lexical

        # Reverse Substring Match (e.g. query is "Amul Pasteurised Butter" -> matches "Butter")
        all_products = db.query(Product).all()
        for p in all_products:
            if p.name.lower() in cleaned or cleaned in p.name.lower():
                logger.info(f"🔎 [CATALOGUE RESOLUTION] query='{raw_query}' (clean='{cleaned}') | database_substring_match=true | validated_product_id='{p.id}' | resolved_product='{p.name}' | category='{p.category}' | result=VALID")
                return p

        # Step 3 & 4: Qdrant Cloud Semantic Search + PostgreSQL Validation
        threshold = getattr(settings, "PRODUCT_SIMILARITY_THRESHOLD", 0.65)
        vector_candidates = vector_service.search_similar_products(cleaned, limit=5, score_threshold=threshold)
        for match in vector_candidates:
            p_id = match.get("product_id")
            score = match.get("score", 0.0)
            if p_id and score >= threshold:
                product = db.query(Product).filter(Product.id == p_id).first()
                if product:
                    logger.info(f"🔎 [CATALOGUE RESOLUTION] query='{raw_query}' (clean='{cleaned}') | qdrant_candidate='{product.name}' | qdrant_score={score:.3f} | validated_product_id='{product.id}' | category='{product.category}' | result=VALID")
                    return product

        logger.warning(f"🔎 [CATALOGUE RESOLUTION] query='{raw_query}' (clean='{cleaned}') | exact_match=false | lexical_match=false | validated_product_id=null | result=PRODUCT_NOT_IN_CATALOGUE")
        return None

    def process_command(self, db: Session, user_id: str, parsed: ParsedCommand) -> CommandResponse:
        active_list = self.get_or_create_active_list(db, user_id)
        intent = parsed.intent

        if intent in (IntentEnum.ADD_ITEM, IntentEnum.ADD_ITEMS):
            return self._handle_add_items(db, user_id, active_list, parsed)
        elif intent == IntentEnum.REMOVE_ITEM:
            return self._handle_remove_item(db, active_list, parsed)
        elif intent == IntentEnum.UPDATE_ITEM:
            return self._handle_update_item(db, user_id, active_list, parsed)
        elif intent == IntentEnum.SHOW_LIST:
            return CommandResponse(
                success=True,
                message=f"Current list has {len(active_list.items)} items.",
                parsed=parsed,
                action_taken="SHOW_LIST"
            )
        elif intent == IntentEnum.CLEAR_LIST:
            db.query(ShoppingItem).filter(ShoppingItem.list_id == active_list.id).delete()
            db.commit()
            return CommandResponse(
                success=True,
                message="Cleared all items from your shopping list.",
                parsed=parsed,
                action_taken="CLEAR_LIST"
            )
        else:
            return CommandResponse(
                success=False,
                message=f"Command not recognized: {parsed.raw_transcript}",
                parsed=parsed,
                action_taken="NONE"
            )

    def _handle_add_items(self, db: Session, user_id: str, active_list: ShoppingList, parsed: ParsedCommand) -> CommandResponse:
        items_to_process = parsed.get_items()
        if not items_to_process:
            return CommandResponse(
                success=False,
                message="No items specified to add.",
                parsed=parsed,
                action_taken="NONE"
            )

        item_results = []
        messages = []
        any_success = False

        for cmd_item in items_to_process:
            raw_name = cmd_item.item or "item"
            quantity = max(1, cmd_item.quantity or 1)
            explicit_size = cmd_item.size

            try:
                # ── 1. Strict Catalogue Resolution Pipeline ──────────
                product = self.resolve_catalogue_product(db, raw_name)

                # ── CASE A: Product Exists & Validated in Catalogue ──────────────
                if product:
                    size_result = size_decision_engine.evaluate_size_decision(
                        db=db,
                        user_id=user_id,
                        product=product,
                        explicit_size=explicit_size
                    )
                    selected_size = size_result.size if size_result else explicit_size
                    is_unresolved = size_result.is_unresolved if size_result else False
                    unresolved_reason = size_result.reason if size_result else None

                    category_name = product.category or "General"
                    display_name = product.name

                    existing_item = (
                        db.query(ShoppingItem)
                        .filter(
                            ShoppingItem.list_id == active_list.id,
                            ShoppingItem.product_id == product.id
                        )
                        .first()
                    )

                    if existing_item:
                        existing_item.quantity += quantity
                        if selected_size:
                            existing_item.size = selected_size
                            existing_item.is_size_unresolved = is_unresolved
                        existing_item.category = category_name
                        db.commit()
                        if selected_size and selected_size != "__________":
                            msg = f"Updated {display_name} quantity to {existing_item.quantity} ({selected_size})."
                        else:
                            msg = f"Updated {display_name} quantity to {existing_item.quantity}."
                        messages.append(msg)
                    else:
                        new_item = ShoppingItem(
                            list_id=active_list.id,
                            product_id=product.id,
                            product_name=display_name,
                            category=category_name,
                            quantity=quantity,
                            unit=cmd_item.unit,
                            size=selected_size,
                            is_size_unresolved=is_unresolved
                        )
                        db.add(new_item)
                        db.commit()
                        if selected_size and selected_size != "__________":
                            msg = f"Added {quantity} {display_name} ({selected_size}) to your shopping list."
                        elif is_unresolved:
                            msg = f"Added {quantity} {display_name} to your shopping list. Please choose a size."
                        else:
                            msg = f"Added {quantity} {display_name} to your shopping list."
                        messages.append(msg)

                    item_results.append({
                        "item": raw_name,
                        "product_found": True,
                        "product_name": display_name,
                        "category": category_name,
                        "quantity": quantity,
                        "size": selected_size,
                        "is_size_unresolved": is_unresolved,
                        "size_reason": unresolved_reason,
                        "message": messages[-1]
                    })
                    any_success = True

                # ── CASE B: Product NOT in Supermarket Catalogue ────────────
                else:
                    unverified_name = raw_name.strip().capitalize()
                    not_found_msg = f"I couldn't find '{unverified_name}' in the supermarket catalogue."
                    messages.append(not_found_msg)

                    item_results.append({
                        "item": raw_name,
                        "product_found": False,
                        "error": "PRODUCT_NOT_IN_CATALOGUE",
                        "message": not_found_msg
                    })

            except Exception as e:
                db.rollback()
                logger.error(f"Error processing item '{raw_name}': {e}")
                messages.append(f"Failed to add '{raw_name}'.")

        final_msg = " ".join(messages)
        return CommandResponse(
            success=any_success,
            message=final_msg,
            parsed=parsed,
            action_taken="ADD_ITEMS" if any_success else "NONE",
            data={
                "summary": final_msg,
                "items": item_results,
                "error": "PRODUCT_NOT_IN_CATALOGUE" if not any_success else None
            }
        )

    def _handle_remove_item(self, db: Session, active_list: ShoppingList, parsed: ParsedCommand) -> CommandResponse:
        raw_name = parsed.item
        if not raw_name:
            return CommandResponse(
                success=False,
                message="No item specified to remove.",
                parsed=parsed,
                action_taken="NONE"
            )

        cleaned_name = normalize_product_query(raw_name)

        item_to_remove = (
            db.query(ShoppingItem)
            .filter(
                ShoppingItem.list_id == active_list.id,
                or_(
                    ShoppingItem.product_name.ilike(f"%{cleaned_name}%"),
                    ShoppingItem.product_name.ilike(f"%{raw_name}%")
                )
            )
            .first()
        )

        if item_to_remove:
            removed_name = item_to_remove.product_name
            db.delete(item_to_remove)
            db.commit()
            return CommandResponse(
                success=True,
                message=f"Removed {removed_name} from your shopping list.",
                parsed=parsed,
                action_taken="REMOVE_ITEM"
            )

        return CommandResponse(
            success=False,
            message=f"'{raw_name}' was not found on your shopping list.",
            parsed=parsed,
            action_taken="NONE"
        )

    def _handle_update_item(self, db: Session, user_id: str, active_list: ShoppingList, parsed: ParsedCommand) -> CommandResponse:
        raw_name = parsed.item
        requested_size = parsed.size
        requested_qty = parsed.quantity

        if not active_list.items:
            return CommandResponse(
                success=False,
                message="Your shopping list is empty.",
                parsed=parsed,
                action_taken="NONE"
            )

        target_item = None
        if raw_name:
            cleaned_name = normalize_product_query(raw_name)
            target_item = (
                db.query(ShoppingItem)
                .filter(
                    ShoppingItem.list_id == active_list.id,
                    or_(
                        ShoppingItem.product_name.ilike(f"%{cleaned_name}%"),
                        ShoppingItem.product_name.ilike(f"%{raw_name}%")
                    )
                )
                .first()
            )

        if not target_item:
            target_item = (
                db.query(ShoppingItem)
                .filter(ShoppingItem.list_id == active_list.id, ShoppingItem.is_size_unresolved == True)
                .first()
            )

        if not target_item and len(active_list.items) > 0:
            target_item = active_list.items[-1]

        if not target_item:
            return CommandResponse(
                success=False,
                message=f"Could not find '{raw_name or 'item'}' to update on your list.",
                parsed=parsed,
                action_taken="NONE"
            )

        # Check brochure size validity if updating size for a catalogue product
        if requested_size:
            product = None
            if target_item.product_id:
                product = db.query(Product).filter(Product.id == target_item.product_id).first()
            if not product:
                product = self.resolve_catalogue_product(db, target_item.product_name)

            if product and product.sizes:
                valid_sizes = [s.size_value.lower() for s in product.sizes]
                if valid_sizes and requested_size.lower() not in valid_sizes:
                    return CommandResponse(
                        success=False,
                        message=f"'{requested_size}' is not listed in the supermarket catalog for {product.name}.",
                        parsed=parsed,
                        action_taken="NONE"
                    )

        updated_fields = []
        if requested_size:
            target_item.size = requested_size
            target_item.is_size_unresolved = False
            updated_fields.append(f"to size {requested_size}")
        if requested_qty:
            target_item.quantity = requested_qty
            updated_fields.append(f"quantity to {requested_qty}")

        db.commit()
        desc = " and ".join(updated_fields) if updated_fields else "item"
        return CommandResponse(
            success=True,
            message=f"Updated {target_item.product_name} {desc}.",
            parsed=parsed,
            action_taken="UPDATE_ITEM"
        )

shopping_service = ShoppingService()
