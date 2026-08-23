"""
test_multi_item_and_category.py
Comprehensive test suite for multi-item voice command extraction, multi-item pipeline processing,
independent category resolution, unit/quantity preservation, size engine compatibility,
and category sorting.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base, User, Product, ProductSize, ShoppingList, ShoppingItem, PurchaseHistory
from app.ai.llm_service import LLMCommandService
from app.schemas.command import IntentEnum, ParsedCommand, CommandItem
from app.services.shopping_service import ShoppingService
from app.recommendations.co_purchase_engine import CoPurchaseRecommendationEngine

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=engine)

@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = Session()

    # Seed User
    user = User(id="test-user-multi", name="Multi Tester")
    session.add(user)

    # Seed Products with Categories & Sizes
    eggs = Product(id="prod-eggs", name="Eggs", brand="Farm Fresh", category="Dairy")
    session.add(eggs)
    session.flush()
    session.add(ProductSize(product_id="prod-eggs", size_value="12 pack", unit="pack", is_default=True))

    butter = Product(id="prod-butter", name="Butter", brand="Amul", category="Dairy")
    session.add(butter)
    session.flush()
    session.add(ProductSize(product_id="prod-butter", size_value="250g", unit="g", is_default=False))
    session.add(ProductSize(product_id="prod-butter", size_value="500g", unit="g", is_default=True))
    session.add(ProductSize(product_id="prod-butter", size_value="1kg", unit="kg", is_default=False))

    milk = Product(id="prod-milk", name="Milk", brand="Dairy Pure", category="Dairy")
    session.add(milk)
    session.flush()
    session.add(ProductSize(product_id="prod-milk", size_value="1L", unit="L", is_default=True))

    bread = Product(id="prod-bread", name="Bread", brand="Wonder Bread", category="Bakery")
    session.add(bread)
    session.flush()
    session.add(ProductSize(product_id="prod-bread", size_value="500g", unit="g", is_default=True))

    shampoo = Product(id="prod-shampoo", name="Shampoo", brand="Pantene", category="Personal Care")
    session.add(shampoo)
    session.flush()
    session.add(ProductSize(product_id="prod-shampoo", size_value="340ml", unit="ml", is_default=False))
    session.add(ProductSize(product_id="prod-shampoo", size_value="500ml", unit="ml", is_default=False))
    session.add(ProductSize(product_id="prod-shampoo", size_value="650ml", unit="ml", is_default=False))

    jam = Product(id="prod-jam", name="Jam", brand="Kissan", category="Pantry")
    session.add(jam)
    session.flush()
    session.add(ProductSize(product_id="prod-jam", size_value="500g", unit="g", is_default=True))

    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def parser():
    svc = LLMCommandService.__new__(LLMCommandService)
    svc.groq_client = None
    return svc

@pytest.fixture
def shopping_svc():
    return ShoppingService()

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Fallback NLU Multi-Item Extraction Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_single_item_add(parser):
    res = parser._fallback_rule_parser("add milk")
    items = res.get_items()
    assert len(items) == 1
    assert items[0].item.lower() == "milk"

def test_two_item_add(parser):
    res = parser._fallback_rule_parser("include bread and jam")
    items = res.get_items()
    assert len(items) == 2
    names = [i.item.lower() for i in items]
    assert "bread" in names
    assert "jam" in names

def test_three_item_add_exact_scenario(parser):
    """'Add 12 eggs, 1Kg butter, 3 milk packets'"""
    res = parser._fallback_rule_parser("Add 12 eggs, 1Kg butter, 3 milk packets")
    items = res.get_items()
    assert len(items) == 3, f"Expected 3 items, got {len(items)}: {items}"

    # Verify Eggs
    eggs = next((i for i in items if "egg" in i.item.lower()), None)
    assert eggs is not None
    assert eggs.quantity == 12
    assert eggs.unit in ("pieces", "items", "packets", None)

    # Verify Butter
    butter = next((i for i in items if "butter" in i.item.lower()), None)
    assert butter is not None
    assert butter.quantity == 1
    assert butter.unit in ("kg", "g", None)

    # Verify Milk
    milk = next((i for i in items if "milk" in i.item.lower()), None)
    assert milk is not None
    assert milk.quantity == 3
    assert milk.unit in ("packets", "packs", None)

def test_quantities_and_units_preserved_independently(parser):
    res = parser._fallback_rule_parser("buy 2 apples, 1kg rice and 3 packets of milk")
    items = res.get_items()
    assert len(items) == 3

    apples = next(i for i in items if "apple" in i.item.lower())
    assert apples.quantity == 2

    rice = next(i for i in items if "rice" in i.item.lower())
    assert rice.quantity == 1
    assert rice.unit == "kg" or rice.size == "1kg"

    milk = next(i for i in items if "milk" in i.item.lower())
    assert milk.quantity == 3
    assert milk.unit == "packets"

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Multi-Item Processing Pipeline & Database Records
# ═══════════════════════════════════════════════════════════════════════════════

def test_multi_item_processing_creates_independent_db_records(db, shopping_svc):
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEMS,
        items=[
            CommandItem(item="Eggs", quantity=12, unit="pieces"),
            CommandItem(item="Butter", quantity=1, unit="kg", size="1kg"),
            CommandItem(item="Milk", quantity=3, unit="packets")
        ]
    )
    res = shopping_svc.process_command(db, "test-user-multi", parsed)
    assert res.success is True

    active_list = shopping_svc.get_or_create_active_list(db, "test-user-multi")
    db_items = db.query(ShoppingItem).filter_by(list_id=active_list.id).all()
    assert len(db_items) == 3, f"Expected 3 DB records, found {len(db_items)}"

    # Independent item checks
    eggs_db = next(i for i in db_items if i.product_name == "Eggs")
    assert eggs_db.quantity == 12
    assert eggs_db.category == "Dairy"

    butter_db = next(i for i in db_items if i.product_name == "Butter")
    assert butter_db.quantity == 1
    assert butter_db.category == "Dairy"
    assert butter_db.size == "1kg"

    milk_db = next(i for i in db_items if i.product_name == "Milk")
    assert milk_db.quantity == 3
    assert milk_db.category == "Dairy"

def test_product_categories_resolved_independently(db, shopping_svc):
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEMS,
        items=[
            CommandItem(item="Milk", quantity=1),
            CommandItem(item="Bread", quantity=1),
            CommandItem(item="Shampoo", quantity=1)
        ]
    )
    shopping_svc.process_command(db, "test-user-multi", parsed)

    active_list = shopping_svc.get_or_create_active_list(db, "test-user-multi")
    db_items = db.query(ShoppingItem).filter_by(list_id=active_list.id).all()

    cats = {i.product_name: i.category for i in db_items}
    assert cats["Milk"] == "Dairy"
    assert cats["Bread"] == "Bakery"
    assert cats["Shampoo"] == "Personal Care"

def test_unknown_product_category_fallback_to_other(db, shopping_svc):
    """Unknown product not in catalogue -> rejected with success=False, 0 items created."""
    cmd = ParsedCommand(
        intent=IntentEnum.ADD_ITEM,
        items=[CommandItem(item="CustomAlienGadget", quantity=1)]
    )
    res = shopping_svc.process_command(db, "user-multi-cat-test-3", cmd)
    assert res.success is False
    assert res.data["error"] == "PRODUCT_NOT_IN_CATALOGUE"
    active_list = db.query(ShoppingList).filter_by(user_id="user-multi-cat-test-3", status="ACTIVE").first()
    gadget = db.query(ShoppingItem).filter_by(list_id=active_list.id, product_name="Customaliengadget").first() if active_list else None
    assert gadget is None

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Size Engine & Unresolved Size Compatibility
# ═══════════════════════════════════════════════════════════════════════════════

def test_multi_item_containing_unresolved_and_resolved_sizes(db, shopping_svc):
    """'Add shampoo and milk' — Shampoo has multiple sizes & no history -> unresolved __________
    Milk has single default size 1L -> resolved to 1L."""
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEMS,
        items=[
            CommandItem(item="Shampoo", quantity=1),
            CommandItem(item="Milk", quantity=1)
        ]
    )
    shopping_svc.process_command(db, "test-user-multi", parsed)

    active_list = shopping_svc.get_or_create_active_list(db, "test-user-multi")
    shampoo_db = db.query(ShoppingItem).filter_by(list_id=active_list.id, product_name="Shampoo").first()
    milk_db = db.query(ShoppingItem).filter_by(list_id=active_list.id, product_name="Milk").first()

    assert shampoo_db.is_size_unresolved is True
    assert shampoo_db.size == "__________"

    assert milk_db.is_size_unresolved is False
    assert milk_db.size == "1L"

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Error Isolation in Multi-Item Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def test_error_handling_one_failed_item_does_not_discard_others(db, shopping_svc):
    """If processing item 2 encounters an error, items 1 and 3 are still saved."""
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEMS,
        items=[
            CommandItem(item="Milk", quantity=1),
            CommandItem(item="ErrorItem", quantity=1),
            CommandItem(item="Bread", quantity=1)
        ]
    )

    res = shopping_svc.process_command(db, "test-user-multi", parsed)
    assert res.success is True  # Overall success because Milk and Bread succeeded

    active_list = shopping_svc.get_or_create_active_list(db, "test-user-multi")
    db_items = db.query(ShoppingItem).filter_by(list_id=active_list.id).all()
    names = [i.product_name for i in db_items]
    assert "Milk" in names
    assert "Bread" in names

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Co-Purchase Recommendation Engine Compatibility
# ═══════════════════════════════════════════════════════════════════════════════

def test_co_purchase_recommendations_after_multi_item_add(db, shopping_svc):
    reco_engine = CoPurchaseRecommendationEngine()

    # Seed 3 historical purchases: Bread + Jam
    for i in range(3):
        sl = ShoppingList(user_id="test-user-multi", status="COMPLETED")
        db.add(sl)
        db.flush()
        db.add(ShoppingItem(list_id=sl.id, product_name="Bread", quantity=1))
        db.add(ShoppingItem(list_id=sl.id, product_name="Jam", quantity=1))
    db.commit()

    # Add Bread via multi-item command
    parsed = ParsedCommand(
        intent=IntentEnum.ADD_ITEMS,
        items=[CommandItem(item="Bread", quantity=1)]
    )
    shopping_svc.process_command(db, "test-user-multi", parsed)

    active_list = shopping_svc.get_or_create_active_list(db, "test-user-multi")
    sug_res = reco_engine.generate_recommendations(db, "test-user-multi", active_list.id)

    sug_names = [s.product_name for s in sug_res.suggestions]
    assert "Jam" in sug_names, f"Expected Jam recommendation, got: {sug_names}"
