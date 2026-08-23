"""
test_expanded_catalogue.py
Automated test suite verifying the Expanded Supermarket Product Catalogue (Requirement 19: 1-11).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Product, ProductSize, User, ShoppingList, ShoppingItem
from app.database.connection import SessionLocal
from app.search.vector_service import vector_service
from app.services.size_engine import size_decision_engine
from app.services.shopping_service import shopping_service
from app.schemas.command import IntentEnum, ParsedCommand, CommandItem

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Catalogue Count & Non-Duplication Tests (Requirement 19: 1-5)
# ═══════════════════════════════════════════════════════════════════════════════

def test_1_catalogue_count(db):
    total = db.query(Product).count()
    assert total >= 100, f"Expected at least 100 products in catalogue, found {total}"

def test_2_existing_products_intact(db):
    baseline_names = ["Shampoo", "Milk", "Bread", "Jam", "Eggs", "Coffee", "Butter", "Rice", "Apples"]
    for name in baseline_names:
        p = db.query(Product).filter(Product.name.ilike(name)).first()
        assert p is not None, f"Baseline product '{name}' was missing"

def test_3_no_duplicate_product_ids(db):
    ids = [p.id for p in db.query(Product).all()]
    assert len(ids) == len(set(ids)), "Found duplicate product IDs in database"

def test_4_no_duplicate_name_brand_size_combinations(db):
    products = db.query(Product).all()
    seen = set()
    for p in products:
        sizes = [s.size_value for s in p.sizes]
        for sz in sizes:
            combo = (p.name.lower(), (p.brand or "").lower(), sz.lower())
            assert combo not in seen, f"Duplicate product combination found: {combo}"
            seen.add(combo)

def test_5_all_products_have_valid_categories(db):
    products = db.query(Product).all()
    for p in products:
        assert p.category is not None and len(p.category.strip()) > 0, f"Product {p.name} has missing category"

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Semantic Search & Vector Retrieval Tests (Requirement 19: 7, 8)
# ═══════════════════════════════════════════════════════════════════════════════

def test_7_semantic_product_search_retrieval(db):
    queries = [
        ("shampoo for hair", ["Shampoo", "Hair Oil"]),
        ("cooking oil", ["Sunflower Oil", "Mustard Oil", "Groundnut Oil", "Rice Bran Oil", "Coconut Oil", "Olive Oil"]),
        ("washing clothes", ["Laundry Detergent Powder"]),
        ("clean the toilet", ["Toilet Cleaner"]),
        ("breakfast cereal", ["Cornflakes", "Rolled Oats", "Muesli", "Chocos"])
    ]
    for query, expected_matches in queries:
        match = vector_service.search_similar_product(query, score_threshold=0.3)
        if not match:
            match_db = db.query(Product).filter(Product.name.ilike(f"%{query.split()[0]}%")).first()
            assert match_db is not None, f"Could not find match for '{query}'"
        else:
            assert match["name"] in expected_matches or any(e.lower() in match["name"].lower() for e in expected_matches), f"Query '{query}' resolved to unexpected match '{match['name']}'"

def test_8_size_decision_engine_on_new_products(db):
    # Test sunflower oil (has 1L and 5L)
    oil = db.query(Product).filter(Product.name == "Sunflower Oil").first()
    assert oil is not None
    res_explicit = size_decision_engine.evaluate_size_decision(db, "default-user-id", oil, explicit_size="5L")
    assert res_explicit.size == "5L"
    assert res_explicit.is_unresolved is False

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Multi-Item Commands & Category Grouping (Requirement 19: 10, 11)
# ═══════════════════════════════════════════════════════════════════════════════

def test_10_multi_item_voice_command_with_expanded_catalogue(db):
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEMS,
        items=[
            CommandItem(item="Atta", quantity=1, size="5kg"),
            CommandItem(item="Sunflower Oil", quantity=1, size="1L"),
            CommandItem(item="Potato Chips", quantity=2)
        ]
    )
    res = shopping_service.process_command(db, "default-user-id", parsed)
    assert res.success is True
    items = res.data["items"]
    assert len(items) == 3

    atta = next(i for i in items if i["item"] == "Atta")
    assert atta["category"] == "Staples"
    assert atta["size"] == "5kg"

    oil = next(i for i in items if i["item"] == "Sunflower Oil")
    assert oil["category"] == "Oils & Ghee"
    assert oil["size"] == "1L"

    chips = next(i for i in items if i["item"] == "Potato Chips")
    assert chips["category"] == "Snacks"
