from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.database.models import ShoppingList, ShoppingItem, Product, ProductSize, PurchaseHistory
from app.schemas.command import ParsedCommand, IntentEnum, CommandResponse
from app.services.size_engine import size_decision_engine
from app.search.vector_service import vector_service
import logging

logger = logging.getLogger("uvicorn.error")

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
                # ── 1. Brochure/Catalog Semantic & Database Product Resolution ─────
                product = None
                vector_match = vector_service.search_similar_product(raw_name)
                if vector_match:
                    product = db.query(Product).filter(Product.id == vector_match["product_id"]).first()

                if not product:
                    product = db.query(Product).filter(Product.name.ilike(f"%{raw_name}%")).first()

                # ── CASE B: Product Does NOT Exist in Brochure Catalog ───────────────
                if not product:
                    not_found_msg = f"I couldn't find '{raw_name}' in this supermarket's catalog. Would you like to add it anyway?"
                    messages.append(not_found_msg)
                    
                    # Add as unverified item to shopping list
                    new_unverified = ShoppingItem(
                        list_id=active_list.id,
                        product_id=None,
                        product_name=raw_name.capitalize(),
                        category="Other",
                        quantity=quantity,
                        unit=cmd_item.unit,
                        size="__________",
                        is_size_unresolved=True,
                        status="PENDING"
                    )
                    db.add(new_unverified)
                    db.commit()
                    db.refresh(new_unverified)

                    item_results.append({
                        "item": raw_name.capitalize(),
                        "success": True,
                        "product_found": False,
                        "category": "Other",
                        "quantity": quantity,
                        "unit": cmd_item.unit,
                        "size": "__________",
                        "is_size_unresolved": True,
                        "item_id": new_unverified.id,
                        "message": not_found_msg
                    })
                    any_success = True
                    continue

                # ── CASE A: Product Exists in Brochure Catalog ───────────────────────
                product_name = product.name
                product_id = product.id
                product_category = product.category or "Other"

                # ── 2. Size Decision Engine (5 Brochure Rules) ──────────────────────
                size_result = size_decision_engine.evaluate_size_decision(
                    db=db,
                    user_id=user_id,
                    product=product,
                    explicit_size=explicit_size
                )

                # Check if item already in active list
                existing_item = (
                    db.query(ShoppingItem)
                    .filter(ShoppingItem.list_id == active_list.id, ShoppingItem.product_name.ilike(product_name))
                    .first()
                )

                if existing_item:
                    existing_item.quantity += quantity
                    if cmd_item.unit:
                        existing_item.unit = cmd_item.unit
                    if product_category:
                        existing_item.category = product_category
                    if not size_result.is_unresolved:
                        existing_item.size = size_result.size
                        existing_item.is_size_unresolved = False
                    db.commit()
                    db.refresh(existing_item)

                    unit_disp = f" {existing_item.unit}" if existing_item.unit else ""
                    if size_result.requires_user_clarification and size_result.clarification_message:
                        msg_text = size_result.clarification_message
                    else:
                        msg_text = f"Updated {product_name} quantity to {existing_item.quantity}{unit_disp}."
                    messages.append(msg_text)

                    item_results.append({
                        "item": product_name,
                        "success": True,
                        "product_found": True,
                        "category": product_category,
                        "quantity": existing_item.quantity,
                        "unit": existing_item.unit,
                        "size": existing_item.size,
                        "is_size_unresolved": existing_item.is_size_unresolved,
                        "available_sizes": size_result.available_sizes,
                        "item_id": existing_item.id,
                        "message": msg_text
                    })
                    any_success = True
                else:
                    new_item = ShoppingItem(
                        list_id=active_list.id,
                        product_id=product_id,
                        product_name=product_name,
                        category=product_category,
                        quantity=quantity,
                        unit=cmd_item.unit,
                        size=size_result.size,
                        is_size_unresolved=size_result.is_unresolved,
                        status="PENDING"
                    )
                    db.add(new_item)
                    db.commit()
                    db.refresh(new_item)

                    unit_disp = f" {cmd_item.unit}" if cmd_item.unit else ""
                    size_disp = f" — {size_result.size}" if size_result.size and size_result.size != "__________" else ""

                    if size_result.requires_user_clarification and size_result.clarification_message:
                        msg_text = size_result.clarification_message
                    elif "recent purchases" in size_result.reason:
                        msg_text = f"Added {product_name}{size_disp} based on your recent purchases."
                    else:
                        msg_text = f"Added {quantity}{unit_disp} {product_name}{size_disp} to your list."

                    messages.append(msg_text)

                    item_results.append({
                        "item": product_name,
                        "success": True,
                        "product_found": True,
                        "category": product_category,
                        "quantity": quantity,
                        "unit": cmd_item.unit,
                        "size": size_result.size,
                        "is_size_unresolved": size_result.is_unresolved,
                        "available_sizes": size_result.available_sizes,
                        "item_id": new_item.id,
                        "size_reason": size_result.reason,
                        "message": msg_text
                    })
                    any_success = True

            except Exception as e:
                logger.error(f"Error processing item '{raw_name}': {e}")
                messages.append(f"Could not process '{raw_name}'.")
                item_results.append({
                    "item": raw_name,
                    "success": False,
                    "error": str(e)
                })

        overall_message = " ".join(messages)
        first_id = item_results[0].get("item_id") if item_results else None
        first_reason = item_results[0].get("size_reason") if item_results else None

        return CommandResponse(
            success=any_success,
            message=overall_message,
            parsed=parsed,
            action_taken="ADD_ITEMS" if len(items_to_process) > 1 else "ADD_ITEM",
            data={
                "items": item_results,
                "item_id": first_id,
                "size_reason": first_reason
            }
        )

    def _handle_remove_item(self, db: Session, active_list: ShoppingList, parsed: ParsedCommand) -> CommandResponse:
        raw_name = parsed.item or ""
        # Resolve product against current shopping list
        items = (
            db.query(ShoppingItem)
            .filter(ShoppingItem.list_id == active_list.id, ShoppingItem.product_name.ilike(f"%{raw_name}%"))
            .all()
        )
        if not items:
            return CommandResponse(
                success=False,
                message=f"Could not find '{raw_name}' in your shopping list.",
                parsed=parsed,
                action_taken="NONE"
            )

        if len(items) > 1:
            matching_names = ", ".join(i.product_name for i in items)
            return CommandResponse(
                success=False,
                message=f"Multiple items match '{raw_name}' ({matching_names}). Which one would you like to remove?",
                parsed=parsed,
                action_taken="NONE",
                data={"candidates": [i.product_name for i in items]}
            )

        item = items[0]
        removed_name = item.product_name
        db.delete(item)
        db.commit()
        return CommandResponse(
            success=True,
            message=f"Removed {removed_name} from your list.",
            parsed=parsed,
            action_taken="REMOVE_ITEM"
        )

    def _handle_update_item(self, db: Session, user_id: str, active_list: ShoppingList, parsed: ParsedCommand) -> CommandResponse:
        raw_name = parsed.item
        new_size = parsed.size
        new_quantity = parsed.quantity

        target_item = None
        if raw_name:
            target_item = (
                db.query(ShoppingItem)
                .filter(ShoppingItem.list_id == active_list.id, ShoppingItem.product_name.ilike(f"%{raw_name}%"))
                .first()
            )

        if not target_item:
            target_item = (
                db.query(ShoppingItem)
                .filter(ShoppingItem.list_id == active_list.id, ShoppingItem.is_size_unresolved == True)
                .first()
            )

        if not target_item:
            return CommandResponse(
                success=False,
                message="No matching item found to update.",
                parsed=parsed,
                action_taken="NONE"
            )

        # ── Brochure Catalog Validation for Requested Size ──────────────────
        if new_size:
            product = None
            if target_item.product_id:
                product = db.query(Product).filter(Product.id == target_item.product_id).first()
            if not product:
                product = db.query(Product).filter(Product.name.ilike(f"%{target_item.product_name}%")).first()

            if product and product.sizes:
                avail_sizes = [s.size_value for s in product.sizes]
                matching_size = next((s for s in avail_sizes if s.lower() == new_size.strip().lower()), None)
                if matching_size:
                    target_item.size = matching_size
                    target_item.is_size_unresolved = False
                else:
                    sizes_str = ", ".join(avail_sizes)
                    return CommandResponse(
                        success=False,
                        message=f"'{new_size}' is not listed in the supermarket catalog for {product.name}. Available sizes: {sizes_str}.",
                        parsed=parsed,
                        action_taken="NONE",
                        data={"available_sizes": avail_sizes}
                    )
            else:
                target_item.size = new_size
                target_item.is_size_unresolved = False

        if new_quantity and new_quantity > 0:
            target_item.quantity = new_quantity

        db.commit()
        db.refresh(target_item)

        return CommandResponse(
            success=True,
            message=f"Updated {target_item.product_name} to size {target_item.size or ''}.",
            parsed=parsed,
            action_taken="UPDATE_ITEM"
        )

shopping_service = ShoppingService()
