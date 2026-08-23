from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database.connection import get_db
from app.database.models import ShoppingList, ShoppingItem, PurchaseHistory, Product, User
from app.schemas.shopping import ShoppingItemCreate, ShoppingItemUpdate, ShoppingItemResponse, ShoppingListResponse
from app.services.shopping_service import shopping_service
from app.services.size_engine import size_decision_engine
from app.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/shopping-list", tags=["Shopping List"])

class SizeUpdateRequest(BaseModel):
    size: str

@router.get("", response_model=ShoppingListResponse)
def get_active_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the authenticated user's active shopping list."""
    active_list = shopping_service.get_or_create_active_list(db, current_user.id)
    return active_list

@router.post("/items", response_model=ShoppingItemResponse)
def add_item_manual(
    item_in: ShoppingItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually adds an item to the authenticated user's active list."""
    active_list = shopping_service.get_or_create_active_list(db, current_user.id)

    product = None
    if item_in.product_id:
        product = db.query(Product).filter(Product.id == item_in.product_id).first()

    if not product:
        product = db.query(Product).filter(Product.name.ilike(f"%{item_in.product_name}%")).first()

    size = item_in.size
    is_unresolved = item_in.is_size_unresolved

    if not size:
        size_res = size_decision_engine.evaluate_size_decision(db, current_user.id, product, explicit_size=None)
        size = size_res.size
        is_unresolved = size_res.is_unresolved

    category = item_in.category or (product.category if product and product.category else "Other")

    item = ShoppingItem(
        list_id=active_list.id,
        product_id=product.id if product else item_in.product_id,
        product_name=product.name if product else item_in.product_name,
        category=category,
        quantity=item_in.quantity,
        unit=item_in.unit,
        size=size,
        is_size_unresolved=is_unresolved,
        status="PENDING"
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.patch("/items/{item_id}", response_model=ShoppingItemResponse)
def update_item(
    item_id: str,
    item_in: ShoppingItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates an item in the authenticated user's active list (IDOR Protected)."""
    item = (
        db.query(ShoppingItem)
        .join(ShoppingList)
        .filter(ShoppingItem.id == item_id, ShoppingList.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping item not found or unauthorized")

    if item_in.quantity is not None:
        item.quantity = item_in.quantity
    if item_in.unit is not None:
        item.unit = item_in.unit
    if item_in.size is not None:
        item.size = item_in.size
        item.is_size_unresolved = False
    if item_in.is_size_unresolved is not None:
        item.is_size_unresolved = item_in.is_size_unresolved
    if item_in.status is not None:
        item.status = item_in.status

    db.commit()
    db.refresh(item)
    return item

@router.patch("/items/{item_id}/size", response_model=ShoppingItemResponse)
def resolve_item_size(
    item_id: str,
    req: SizeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resolves item size for an item in the authenticated user's active list (IDOR Protected)."""
    item = (
        db.query(ShoppingItem)
        .join(ShoppingList)
        .filter(ShoppingItem.id == item_id, ShoppingList.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping item not found or unauthorized")

    item.size = req.size
    item.is_size_unresolved = False
    db.commit()
    db.refresh(item)
    return item

@router.delete("/items/{item_id}")
def delete_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes an item from the authenticated user's active list (IDOR Protected)."""
    item = (
        db.query(ShoppingItem)
        .join(ShoppingList)
        .filter(ShoppingItem.id == item_id, ShoppingList.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping item not found or unauthorized")

    db.delete(item)
    db.commit()
    return {"success": True, "message": "Item deleted"}

@router.post("/checkout")
def checkout_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marks current list as COMPLETED and records items into authenticated user's PurchaseHistory."""
    active_list = shopping_service.get_or_create_active_list(db, current_user.id)
    if not active_list.items:
        return {"success": False, "message": "List is empty"}

    for item in active_list.items:
        history_record = PurchaseHistory(
            user_id=current_user.id,
            list_id=active_list.id,
            product_id=item.product_id,
            product_name=item.product_name,
            size=item.size if not item.is_size_unresolved else None
        )
        db.add(history_record)

    active_list.status = "COMPLETED"
    db.commit()

    # Create new active list for authenticated user
    new_list = ShoppingList(user_id=current_user.id, status="ACTIVE")
    db.add(new_list)
    db.commit()

    return {"success": True, "message": "Checkout complete! Recorded purchase history."}
