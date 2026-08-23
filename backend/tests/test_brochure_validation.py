"""
test_brochure_validation.py
Automated test suite verifying Brochure-Based Product & Size Validation (Part 28 requirements 1-20).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base, User, Product, ProductSize, ShoppingList, ShoppingItem, PurchaseHistory
from app.schemas.command import IntentEnum, ParsedCommand, CommandItem
from app.services.shopping_service import shopping_service
from app.services.size_engine import size_decision_engine
from app.recommendations.co_purchase_engine import co_purchase_engine

TEST_DB_URL = "sqlite:///:memory:"
brochure_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
BrochureSession = sessionmaker(bind=brochure_engine)

@pytest.fixture
def db():
    Base.metadata.drop_all(bind=brochure_engine)
    Base.metadata.create_all(bind=brochure_engine)
    session = BrochureSession()

    # Seed Primary User
    user = User(id="user-brochure-test", name="Brochure Tester")
    session.add(user)

    # Catalog Product 1: Milk (Dairy) - 1 size only (1L)
    milk = Product(id="prod-milk", name="Milk", category="Dairy", brand="Dairy Pure")
    session.add(milk)
    session.flush()
    session.add(ProductSize(product_id="prod-milk", size_value="1L", is_default=True))

    # Catalog Product 2: Shampoo (Personal Care) - 3 sizes (340ml, 500ml, 650ml)
    shampoo = Product(id="prod-shampoo", name="Shampoo", category="Personal Care", brand="Pantene")
    session.add(shampoo)
    session.flush()
    session.add(ProductSize(product_id="prod-shampoo", size_value="340ml"))
    session.add(ProductSize(product_id="prod-shampoo", size_value="500ml"))
    session.add(ProductSize(product_id="prod-shampoo", size_value="650ml"))

    # Catalog Product 3: Bread (Bakery) - 1 size (500g)
    bread = Product(id="prod-bread", name="Bread", category="Bakery")
    session.add(bread)
    session.flush()
    session.add(ProductSize(product_id="prod-bread", size_value="500g"))

    # Catalog Product 4: Butter (Dairy) - sizes (250g, 500g)
    butter = Product(id="prod-butter", name="Butter", category="Dairy")
    session.add(butter)
    session.flush()
    session.add(ProductSize(product_id="prod-butter", size_value="250g"))
    session.add(ProductSize(product_id="prod-butter", size_value="500g"))

    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(bind=brochure_engine)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Product Existence & Non-Existence Tests (Part 28: 1, 2)
# ═══════════════════════════════════════════════════════════════════════════════

def test_1_product_exists_in_brochure(db):
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEM,
        items=[CommandItem(item="Milk", quantity=1)]
    )
    res = shopping_service.process_command(db, "user-brochure-test", parsed)
    assert res.success is True
    item = res.data["items"][0]
    assert item["product_found"] is True
    assert item["item"] == "Milk"
    assert item["category"] == "Dairy"

def test_2_product_does_not_exist_in_brochure(db):
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEM,
        items=[CommandItem(item="Dragon Fruit", quantity=1)]
    )
    res = shopping_service.process_command(db, "user-brochure-test", parsed)
    assert res.success is True
    item = res.data["items"][0]
    assert item["product_found"] is False
    assert "couldn't find 'Dragon Fruit' in this supermarket's catalog" in item["message"]

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Brochure Size Decision Rules (Part 28: 4, 5, 6, 7, 8, 9, 10, 11, 12)
# ═══════════════════════════════════════════════════════════════════════════════

def test_4_single_size_in_brochure(db):
    """Rule 2: Milk has 1 size (1L) in brochure -> auto-selected."""
    shampoo = db.query(Product).filter_by(name="Milk").first()
    res = size_decision_engine.evaluate_size_decision(db, "user-brochure-test", shampoo)
    assert res.size == "1L"
    assert res.is_unresolved is False

def test_6_user_explicitly_specifies_valid_brochure_size(db):
    """Rule 1 (Valid): Shampoo 650ml exists in brochure."""
    shampoo = db.query(Product).filter_by(name="Shampoo").first()
    res = size_decision_engine.evaluate_size_decision(db, "user-brochure-test", shampoo, explicit_size="650ml")
    assert res.size == "650ml"
    assert res.is_unresolved is False

def test_7_user_explicitly_specifies_invalid_brochure_size(db):
    """Rule 1 (Invalid): Shampoo 1000ml is NOT in brochure -> asks user with available sizes."""
    shampoo = db.query(Product).filter_by(name="Shampoo").first()
    res = size_decision_engine.evaluate_size_decision(db, "user-brochure-test", shampoo, explicit_size="1000ml")
    assert res.is_unresolved is True
    assert res.requires_user_clarification is True
    assert "1000ml' Shampoo is not listed in the supermarket catalog" in res.clarification_message
    assert "340ml, 500ml, 650ml" in res.clarification_message

def test_10_user_preferred_size_exists_in_brochure(db):
    """Rule 3: Preferred size 650ml exists in brochure -> auto-selected."""
    shampoo = db.query(Product).filter_by(name="Shampoo").first()
    # Seed 3 historical purchases: 650ml, 650ml, 340ml
    for s in ["650ml", "650ml", "340ml"]:
        sl = ShoppingList(user_id="user-brochure-test", status="COMPLETED")
        db.add(sl)
        db.flush()
        db.add(PurchaseHistory(user_id="user-brochure-test", list_id=sl.id, product_name="Shampoo", size=s))
    db.commit()

    res = size_decision_engine.evaluate_size_decision(db, "user-brochure-test", shampoo)
    assert res.size == "650ml"
    assert res.is_unresolved is False
    assert "Historical preference" in res.reason

def test_11_user_preferred_size_not_in_brochure(db):
    """Rule 4: Preferred size 1L in history, but brochure ONLY has 340ml, 500ml, 650ml -> asks user."""
    shampoo = db.query(Product).filter_by(name="Shampoo").first()
    # Seed 3 historical purchases of 1L
    for s in ["1L", "1L", "1L"]:
        sl = ShoppingList(user_id="user-brochure-test", status="COMPLETED")
        db.add(sl)
        db.flush()
        db.add(PurchaseHistory(user_id="user-brochure-test", list_id=sl.id, product_name="Shampoo", size=s))
    db.commit()

    res = size_decision_engine.evaluate_size_decision(db, "user-brochure-test", shampoo)
    assert res.is_unresolved is True
    assert res.requires_user_clarification is True
    assert "usually buy 1L Shampoo, but 1L isn't available in this supermarket catalog" in res.clarification_message

def test_12_no_clear_size_preference(db):
    """Rule 5: No historical preference -> unresolved with available brochure options."""
    shampoo = db.query(Product).filter_by(name="Shampoo").first()
    res = size_decision_engine.evaluate_size_decision(db, "user-brochure-test", shampoo)
    assert res.size == "__________"
    assert res.is_unresolved is True
    assert "340ml, 500ml, 650ml" in res.clarification_message

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Multi-Item & Partial Success (Part 28: 13, 14)
# ═══════════════════════════════════════════════════════════════════════════════

def test_13_14_multi_item_and_partial_success(db):
    """'Add milk, butter and dragon fruit' -> Milk & Butter succeeded, Dragon Fruit not found."""
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEMS,
        items=[
            CommandItem(item="Milk", quantity=1),
            CommandItem(item="Butter", quantity=1),
            CommandItem(item="Dragon Fruit", quantity=1)
        ]
    )
    res = shopping_service.process_command(db, "user-brochure-test", parsed)
    assert res.success is True

    items = res.data["items"]
    assert len(items) == 3

    milk = next(i for i in items if i["item"] == "Milk")
    assert milk["product_found"] is True

    butter = next(i for i in items if i["item"] == "Butter")
    assert butter["product_found"] is True

    dragon = next(i for i in items if i["item"].lower() == "dragon fruit")
    assert dragon["product_found"] is False

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Remove & Update Item Validation (Part 28: 15, 16)
# ═══════════════════════════════════════════════════════════════════════════════

def test_15_remove_item_from_list(db):
    active_list = shopping_service.get_or_create_active_list(db, "user-brochure-test")
    db.add(ShoppingItem(list_id=active_list.id, product_name="Milk", quantity=1))
    db.commit()

    parsed = ParsedCommand(intent=IntentEnum.REMOVE_ITEM, item="Milk")
    res = shopping_service.process_command(db, "user-brochure-test", parsed)
    assert res.success is True
    assert "Removed Milk" in res.message

def test_16_update_size_valid_vs_invalid_brochure(db):
    active_list = shopping_service.get_or_create_active_list(db, "user-brochure-test")
    db.add(ShoppingItem(list_id=active_list.id, product_name="Shampoo", size="__________", is_size_unresolved=True))
    db.commit()

    # Invalid brochure size: 999ml
    parsed_invalid = ParsedCommand(intent=IntentEnum.UPDATE_ITEM, item="Shampoo", size="999ml")
    res_invalid = shopping_service.process_command(db, "user-brochure-test", parsed_invalid)
    assert res_invalid.success is False
    assert "not listed in the supermarket catalog" in res_invalid.message

    # Valid brochure size: 650ml
    parsed_valid = ParsedCommand(intent=IntentEnum.UPDATE_ITEM, item="Shampoo", size="650ml")
    res_valid = shopping_service.process_command(db, "user-brochure-test", parsed_valid)
    assert res_valid.success is True
    assert "Updated Shampoo to size 650ml" in res_valid.message

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Smart Suggestions Brochure Validation (Part 28: 19, 20)
# ═══════════════════════════════════════════════════════════════════════════════

def test_19_20_smart_suggestions_brochure_validation(db):
    # Seed purchase history: Bread + Jam (Jam is NOT in brochure) and Bread + Milk (Milk IS in brochure)
    for _ in range(3):
        sl = ShoppingList(user_id="user-brochure-test", status="COMPLETED")
        db.add(sl)
        db.flush()
        db.add(ShoppingItem(list_id=sl.id, product_name="Bread"))
        db.add(ShoppingItem(list_id=sl.id, product_name="Jam"))
        db.add(ShoppingItem(list_id=sl.id, product_name="Milk"))
    db.commit()

    active_list = shopping_service.get_or_create_active_list(db, "user-brochure-test")
    db.add(ShoppingItem(list_id=active_list.id, product_name="Bread"))
    db.commit()

    sug_res = co_purchase_engine.generate_recommendations(db, "user-brochure-test", active_list.id)
    sug_names = [s.product_name for s in sug_res.suggestions]

    # Milk is in brochure -> recommended
    assert "Milk" in sug_names
    # Jam is NOT in brochure -> suppressed!
    assert "Jam" not in sug_names
