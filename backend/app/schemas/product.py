from pydantic import BaseModel
from typing import Optional, List

class ProductSizeSchema(BaseModel):
    id: str
    size_value: str
    unit: Optional[str] = None
    is_default: bool = False

    class Config:
        from_attributes = True

class ProductSchema(BaseModel):
    id: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    sizes: List[ProductSizeSchema] = []

    class Config:
        from_attributes = True
