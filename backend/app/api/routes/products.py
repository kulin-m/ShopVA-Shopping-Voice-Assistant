from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.connection import get_db
from app.database.models import Product, ProductSize
from app.schemas.product import ProductSchema, ProductSizeSchema

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/search", response_model=List[ProductSchema])
def search_products(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    products = (
        db.query(Product)
        .filter(Product.name.ilike(f"%{q}%") | Product.category.ilike(f"%{q}%"))
        .limit(10)
        .all()
    )
    return products

@router.get("/{product_id}/sizes", response_model=List[ProductSizeSchema])
def get_product_sizes(product_id: str, db: Session = Depends(get_db)):
    sizes = db.query(ProductSize).filter(ProductSize.product_id == product_id).all()
    return sizes
