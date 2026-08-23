from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ShoppingItemBase(BaseModel):
    product_name: str
    category: Optional[str] = None
    quantity: int = 1
    unit: Optional[str] = None
    size: Optional[str] = None

class ShoppingItemCreate(ShoppingItemBase):
    product_id: Optional[str] = None
    is_size_unresolved: bool = False

class ShoppingItemUpdate(BaseModel):
    category: Optional[str] = None
    quantity: Optional[int] = None
    unit: Optional[str] = None
    size: Optional[str] = None
    is_size_unresolved: Optional[bool] = None
    status: Optional[str] = None

class ShoppingItemResponse(ShoppingItemBase):
    id: str
    list_id: str
    product_id: Optional[str] = None
    category: Optional[str] = "Other"
    is_size_unresolved: bool = False
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ShoppingListResponse(BaseModel):
    id: str
    user_id: str
    status: str
    items: List[ShoppingItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
