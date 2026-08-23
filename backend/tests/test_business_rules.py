import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from app.database.models import Base, User, Product, ProductSize, ShoppingList, ShoppingItem, PurchaseHistory
from app.ai.llm_service import llm_service
from app.services.size_engine import size_decision_engine
from app.recommendations.co_purchase_engine import co_purchase_engine
from app.services.shopping_service import shopping_service
from app.schemas.command import IntentEnum

# In-memory SQLite DB for fast unit tests
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    # Create default user
    user = User(id="test-user-id", name="Test User")
    session.add(user)

    # Add Shampoo (3 sizes)
    shampoo = Product(id="prod-shampoo", name="Shampoo", category="Personal Care")
    session.add(shampoo)
    session.flush()

    for sz in ["340ml", "500ml", "650ml"]:
        session.add(ProductSize(product_id=shampoo.id, size_value=sz))

    # Add Milk (1 size)
    milk = Product(id="prod-milk", name="Milk", category="Dairy")
    session.add(milk)
    session.flush()
    session.add(ProductSize(product_id=milk.id, size_value="1L", is_default=True))

    # Add Bread & Jam (1 size each)
    bread = Product(id="prod-bread", name="Bread", category="Bakery")
    jam = Product(id="prod-jam", name="Jam", category="Pantry")
    session.add_all([bread, jam])
    session.flush()
    session.add(ProductSize(product_id=bread.id, size_value="500g"))
    session.add(ProductSize(product_id=jam.id, size_value="250g"))

    session.commit()
    yield session
    session.close()

# -----------------------------------------------------------------------------
# 1. COMMAND PARSER TESTS
# -----------------------------------------------------------------------------
def test_command_parser_semantic_phrases():
    parsed_add = llm_service.parse_command("I need two bottles of milk")
    assert parsed_add.intent == IntentEnum.ADD_ITEM
    assert parsed_add.item == "Milk"
    assert parsed_add.quantity == 2

    parsed_put = llm_service.parse_command("put milk on my list")
    assert parsed_put.intent == IntentEnum.ADD_ITEM
    assert "Milk" in parsed_put.item

    parsed_remove = llm_service.parse_command("take milk off my list")
    assert parsed_remove.intent == IntentEnum.REMOVE_ITEM
    assert "Milk" in parsed_remove.item

    parsed_update = llm_service.parse_command("make shampoo 650ml")
    assert parsed_update.intent == IntentEnum.UPDATE_ITEM
    assert parsed_update.size == "650ml"

def test_command_parser_full_word_units():
    parsed_butter = llm_service.parse_command("add 250 gram of butter")
    assert parsed_butter.intent == IntentEnum.ADD_ITEM
    assert parsed_butter.item == "Butter"
    assert parsed_butter.size == "250g"
    assert parsed_butter.quantity == 1

    parsed_speech_at = llm_service.parse_command("at 250 grams butter")
    assert parsed_speech_at.intent == IntentEnum.ADD_ITEM
    assert parsed_speech_at.item == "Butter"
    assert parsed_speech_at.size == "250g"
    assert parsed_speech_at.quantity == 1

# -----------------------------------------------------------------------------
# 2. SIZE DECISION ENGINE TESTS
# -----------------------------------------------------------------------------
def test_size_rule_1_explicit_size(db):
    shampoo = db.query(Product).filter_by(name="Shampoo").first()
    res = size_decision_engine.evaluate_size_decision(db, "test-user-id", shampoo, explicit_size="650ml")
    assert res.size == "650ml"
    assert res.is_unresolved is False

def test_size_rule_2_single_size_product(db):
    milk = db.query(Product).filter_by(name="Milk").first()
    res = size_decision_engine.evaluate_size_decision(db, "test-user-id", milk, explicit_size=None)
    assert res.size == "1L"
    assert res.is_unresolved is False

def test_size_rule_3_clear_historical_preference_2_of_3(db):
    shampoo = db.query(Product).filter_by(name="Shampoo").first()

    # Seed 3 purchases: 650ml, 650ml, 340ml
    now = datetime.utcnow()
    db.add(PurchaseHistory(user_id="test-user-id", product_id=shampoo.id, product_name="Shampoo", size="650ml", purchased_at=now - timedelta(days=3)))
    db.add(PurchaseHistory(user_id="test-user-id", product_id=shampoo.id, product_name="Shampoo", size="650ml", purchased_at=now - timedelta(days=2)))
    db.add(PurchaseHistory(user_id="test-user-id", product_id=shampoo.id, product_name="Shampoo", size="340ml", purchased_at=now - timedelta(days=1)))
    db.commit()

    res = size_decision_engine.evaluate_size_decision(db, "test-user-id", shampoo, explicit_size=None)
    assert res.size == "650ml"
    assert res.is_unresolved is False

def test_size_rule_4_no_clear_historical_preference(db):
    shampoo = db.query(Product).filter_by(name="Shampoo").first()

    # Seed 3 different sizes: 650ml, 340ml, 500ml
    now = datetime.utcnow()
    db.add(PurchaseHistory(user_id="test-user-id", product_id=shampoo.id, product_name="Shampoo", size="650ml", purchased_at=now - timedelta(days=3)))
    db.add(PurchaseHistory(user_id="test-user-id", product_id=shampoo.id, product_name="Shampoo", size="340ml", purchased_at=now - timedelta(days=2)))
    db.add(PurchaseHistory(user_id="test-user-id", product_id=shampoo.id, product_name="Shampoo", size="500ml", purchased_at=now - timedelta(days=1)))
    db.commit()

    res = size_decision_engine.evaluate_size_decision(db, "test-user-id", shampoo, explicit_size=None)
    assert res.size == "__________"
    assert res.is_unresolved is True

# -----------------------------------------------------------------------------
# 3. CO-PURCHASE RECOMMENDATION TESTS
# -----------------------------------------------------------------------------
def test_co_purchase_recommendations(db):
    # Create 3 past completed lists containing Bread & Jam
    now = datetime.utcnow()
    for i in range(3):
        sl = ShoppingList(user_id="test-user-id", status="COMPLETED", created_at=now - timedelta(days=i+1))
        db.add(sl)
        db.flush()
        db.add(ShoppingItem(list_id=sl.id, product_name="Bread", quantity=1))
        db.add(ShoppingItem(list_id=sl.id, product_name="Jam", quantity=1))
    db.commit()

    # Create active list and add Bread
    active_list = ShoppingList(user_id="test-user-id", status="ACTIVE")
    db.add(active_list)
    db.flush()
    db.add(ShoppingItem(list_id=active_list.id, product_name="Bread", quantity=1))
    db.commit()

    recs = co_purchase_engine.generate_recommendations(db, "test-user-id", active_list.id)
    assert len(recs.suggestions) > 0
    top_sug = recs.suggestions[0]
    assert top_sug.product_name == "Jam"
    assert "3 of your last 3" in top_sug.reason

# -----------------------------------------------------------------------------
# 4. UNRESOLVED SIZE RESOLUTION TEST
# -----------------------------------------------------------------------------
def test_resolving_unresolved_size_item(db):
    shampoo = db.query(Product).filter_by(name="Shampoo").first()
    active_list = shopping_service.get_or_create_active_list(db, "test-user-id")

    # Add Shampoo with no history -> becomes unresolved "__________"
    item = ShoppingItem(
        list_id=active_list.id,
        product_id=shampoo.id,
        product_name="Shampoo",
        quantity=1,
        size="__________",
        is_size_unresolved=True
    )
    db.add(item)
    db.commit()

    # Process voice command "650ml"
    parsed = llm_service.parse_command("650ml")
    resp = shopping_service.process_command(db, "test-user-id", parsed)

    assert resp.success is True
    db.refresh(item)
    assert item.size == "650ml"
    assert item.is_size_unresolved is False
