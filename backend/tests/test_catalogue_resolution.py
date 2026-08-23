import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal, init_db
from app.database.models import User, Product, ProductSize, ShoppingList, ShoppingItem
from app.services.shopping_service import shopping_service, normalize_product_query
from app.schemas.command import ParsedCommand, IntentEnum, CommandItem
from scripts.import_products import seed_database

@pytest.fixture(scope="module")
def db_session():
    init_db()
    seed_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_product_query_normalization():
    assert normalize_product_query("500 grams of butter") == "butter"
    assert normalize_product_query("add 2 bottles of shampoo") == "shampoo"
    assert normalize_product_query("buy 1kg rice") == "rice"
    assert normalize_product_query("AMUL BUTTER") == "amul butter"

def test_catalogue_resolution_butter(db_session: Session):
    prod = shopping_service.resolve_catalogue_product(db_session, "butter")
    assert prod is not None
    assert "butter" in prod.name.lower()
    assert prod.category in ("Dairy", "Dairy & Bakery", "Dairy & Refrigerated", "Breakfast & Dairy")

def test_catalogue_resolution_honey(db_session: Session):
    prod = shopping_service.resolve_catalogue_product(db_session, "honey")
    assert prod is not None
    assert "honey" in prod.name.lower()

def test_catalogue_resolution_milk(db_session: Session):
    prod = shopping_service.resolve_catalogue_product(db_session, "milk")
    assert prod is not None
    assert "milk" in prod.name.lower()

def test_catalogue_resolution_bread(db_session: Session):
    prod = shopping_service.resolve_catalogue_product(db_session, "bread")
    assert prod is not None
    assert "bread" in prod.name.lower()

def test_catalogue_resolution_shampoo(db_session: Session):
    prod = shopping_service.resolve_catalogue_product(db_session, "shampoo")
    assert prod is not None
    assert "shampoo" in prod.name.lower()

def test_add_item_separate_size_resolution(db_session: Session):
    user_id = "test-user-cat-res-unique-101"
    cmd = ParsedCommand(
        intent=IntentEnum.ADD_ITEM,
        item="butter",
        quantity=1,
        size="500g",
        items=[CommandItem(item="butter", quantity=1, size="500g")]
    )
    res = shopping_service.process_command(db_session, user_id, cmd)
    assert res.success is True
    assert "Butter" in res.message or "butter" in res.message.lower()

    active_list = db_session.query(ShoppingList).filter_by(user_id=user_id, status="ACTIVE").first()
    assert active_list is not None
    item = db_session.query(ShoppingItem).filter_by(list_id=active_list.id).first()
    assert item is not None
    assert item.category in ("Dairy", "Dairy & Bakery", "Dairy & Refrigerated", "Breakfast & Dairy")

def test_unknown_product_graceful_fallback(db_session: Session):
    user_id = "test-user-cat-res-unique-202"
    prod = shopping_service.resolve_catalogue_product(db_session, "unknown_unregistered_exotic_item_xyz")
    assert prod is None

    cmd = ParsedCommand(
        intent=IntentEnum.ADD_ITEM,
        item="unknown_unregistered_exotic_item_xyz",
        quantity=1,
        items=[CommandItem(item="unknown_unregistered_exotic_item_xyz", quantity=1)]
    )
    res = shopping_service.process_command(db_session, user_id, cmd)
    assert res.success is True
    assert ("couldn't find" in res.message.lower() or "added" in res.message.lower() or "updated" in res.message.lower())
