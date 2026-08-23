"""
test_api_endpoints.py
FastAPI endpoint reliability tests — invalid inputs, boundary values,
concurrency, and HTTP-level contract verification.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import threading
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, User, Product, ProductSize, ShoppingList, ShoppingItem
from app.database.connection import get_db
from app.main import app

# ── isolated in-memory DB ────────────────────────────────────────────────────
from sqlalchemy.pool import StaticPool
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestSession()
    user = User(id="default-user-id", name="Default User")
    db.add(user)
    shampoo = Product(id="prod-shampoo", name="Shampoo", category="Personal Care")
    db.add(shampoo)
    db.flush()
    for sz in ["340ml", "500ml", "650ml"]:
        db.add(ProductSize(product_id="prod-shampoo", size_value=sz))
    milk = Product(id="prod-milk", name="Milk", category="Dairy")
    db.add(milk)
    db.flush()
    db.add(ProductSize(product_id="prod-milk", size_value="1L", is_default=True))
    db.commit()
    db.close()
    yield
    db_clean = TestSession()
    db_clean.close()
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

# ── health / root ─────────────────────────────────────────────────────────────

def test_root_responds():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"

def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] in ["ok", "healthy"]

# ── /api/commands — valid inputs ──────────────────────────────────────────────

def test_command_add_shampoo_valid():
    r = client.post("/api/commands", json={"transcript": "add shampoo", "user_id": "default-user-id"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True

def test_command_add_with_size():
    r = client.post("/api/commands", json={"transcript": "add 650ml shampoo", "user_id": "default-user-id"})
    assert r.status_code == 200

def test_command_add_milk():
    r = client.post("/api/commands", json={"transcript": "add milk", "user_id": "default-user-id"})
    assert r.status_code == 200

# ── /api/commands — invalid / edge inputs ─────────────────────────────────────

def test_command_empty_transcript():
    """Empty transcript must be rejected, not crash."""
    r = client.post("/api/commands", json={"transcript": "", "user_id": "default-user-id"})
    # Must not be 500; expect 400 or a graceful success=False
    assert r.status_code in (400, 422, 200)
    if r.status_code == 200:
        assert r.json()["success"] is False

def test_command_whitespace_only_transcript():
    r = client.post("/api/commands", json={"transcript": "   ", "user_id": "default-user-id"})
    assert r.status_code != 500

def test_command_missing_transcript_field():
    r = client.post("/api/commands", json={"user_id": "default-user-id"})
    assert r.status_code == 422  # pydantic validation error

def test_command_null_transcript():
    r = client.post("/api/commands", json={"transcript": None, "user_id": "default-user-id"})
    assert r.status_code == 422

def test_command_very_long_transcript():
    """System must not crash on 10,000-character input."""
    long_text = "add shampoo " * 833  # ≈10,000 chars
    r = client.post("/api/commands", json={"transcript": long_text, "user_id": "default-user-id"})
    assert r.status_code != 500

def test_command_unicode_transcript():
    r = client.post("/api/commands", json={"transcript": "add शैम्पू", "user_id": "default-user-id"})
    assert r.status_code != 500

def test_command_emoji_transcript():
    r = client.post("/api/commands", json={"transcript": "add 🧴 shampoo 🛒", "user_id": "default-user-id"})
    assert r.status_code != 500

def test_command_special_chars_transcript():
    r = client.post("/api/commands", json={"transcript": "add <shampoo>; DROP TABLE products;--", "user_id": "default-user-id"})
    assert r.status_code != 500

def test_command_missing_user_id_uses_default():
    r = client.post("/api/commands", json={"transcript": "add milk"})
    assert r.status_code == 200

def test_command_unknown_user_id():
    """Non-existent user_id — should handle gracefully or create user."""
    r = client.post("/api/commands", json={"transcript": "add milk", "user_id": "nonexistent-user-xyz"})
    assert r.status_code != 500

def test_command_invalid_json_body():
    r = client.post("/api/commands", content=b"not-json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422

def test_command_unrecognized_intent():
    """Completely random text should return UNKNOWN intent, not crash."""
    r = client.post("/api/commands", json={"transcript": "xyzzy frobble quux", "user_id": "default-user-id"})
    assert r.status_code != 500

# ── /api/shopping-list ─────────────────────────────────────────────────────────

def test_get_shopping_list():
    r = client.get("/api/shopping-list?user_id=default-user-id")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "id" in body

def test_get_shopping_list_unknown_user():
    """Unknown user triggers list creation, must not 500."""
    r = client.get("/api/shopping-list?user_id=brand-new-user-xyz")
    assert r.status_code != 500

# ── /api/shopping-list/items ──────────────────────────────────────────────────

def test_add_item_manually_valid():
    r = client.post(
        "/api/shopping-list/items?user_id=default-user-id",
        json={"product_name": "Shampoo", "quantity": 2}
    )
    assert r.status_code == 200
    assert r.json()["product_name"] == "Shampoo"

def test_add_item_negative_quantity():
    """Negative quantity must be rejected OR stored without crash."""
    r = client.post(
        "/api/shopping-list/items?user_id=default-user-id",
        json={"product_name": "Shampoo", "quantity": -5}
    )
    # Should not be 500
    assert r.status_code != 500

def test_add_item_zero_quantity():
    r = client.post(
        "/api/shopping-list/items?user_id=default-user-id",
        json={"product_name": "Shampoo", "quantity": 0}
    )
    assert r.status_code != 500

def test_add_item_extremely_large_quantity():
    r = client.post(
        "/api/shopping-list/items?user_id=default-user-id",
        json={"product_name": "Shampoo", "quantity": 9999999}
    )
    assert r.status_code != 500

def test_add_item_missing_product_name():
    r = client.post(
        "/api/shopping-list/items?user_id=default-user-id",
        json={"quantity": 1}
    )
    assert r.status_code == 422

def test_add_item_empty_product_name():
    r = client.post(
        "/api/shopping-list/items?user_id=default-user-id",
        json={"product_name": "", "quantity": 1}
    )
    # Should not be 500
    assert r.status_code != 500

def test_update_nonexistent_item():
    r = client.patch(
        "/api/shopping-list/items/00000000-0000-0000-0000-000000000000",
        json={"quantity": 5}
    )
    assert r.status_code == 404

def test_delete_nonexistent_item():
    r = client.delete("/api/shopping-list/items/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404

def test_resolve_size_nonexistent_item():
    r = client.patch(
        "/api/shopping-list/items/00000000-0000-0000-0000-000000000000/size",
        json={"size": "650ml"}
    )
    assert r.status_code == 404

def test_resolve_size_empty_size():
    """Resolve size endpoint with empty string should not crash."""
    # First add an item
    add = client.post(
        "/api/shopping-list/items?user_id=default-user-id",
        json={"product_name": "Shampoo", "quantity": 1}
    )
    item_id = add.json()["id"]
    r = client.patch(f"/api/shopping-list/items/{item_id}/size", json={"size": ""})
    assert r.status_code != 500

# ── checkout ──────────────────────────────────────────────────────────────────

def test_checkout_empty_list():
    """Checkout on empty list should return graceful failure, not crash."""
    # Clear list first
    r_list = client.get("/api/shopping-list?user_id=default-user-id")
    list_id = r_list.json()["id"]
    for item in r_list.json()["items"]:
        client.delete(f"/api/shopping-list/items/{item['id']}")

    r = client.post("/api/shopping-list/checkout?user_id=default-user-id")
    assert r.status_code != 500
    body = r.json()
    assert body.get("success") is False or "empty" in body.get("message", "").lower()

def test_checkout_with_items():
    client.post("/api/commands", json={"transcript": "add milk", "user_id": "default-user-id"})
    r = client.post("/api/shopping-list/checkout?user_id=default-user-id")
    assert r.status_code == 200
    assert r.json()["success"] is True

# ── suggestions ───────────────────────────────────────────────────────────────

def test_suggestions_endpoint():
    r = client.get("/api/suggestions?user_id=default-user-id")
    assert r.status_code == 200
    assert "suggestions" in r.json()

def test_suggestions_unknown_user():
    r = client.get("/api/suggestions?user_id=ghost-user-xyz")
    assert r.status_code != 500

# ── concurrent requests ───────────────────────────────────────────────────────

def test_concurrent_add_same_item():
    """5 concurrent ADD shampoo commands — must not duplicate inconsistently or crash."""
    errors = []
    results = []

    def send_add():
        try:
            r = client.post("/api/commands", json={"transcript": "add shampoo", "user_id": "default-user-id"})
            results.append(r.status_code)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=send_add) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(errors) == 0, f"Thread errors: {errors}"
    assert all(s != 500 for s in results), f"Some 500s: {results}"

def test_concurrent_add_different_items():
    """10 concurrent ADD requests for different items — race condition check."""
    items = ["milk", "bread", "coffee", "eggs", "jam", "sugar", "butter", "rice", "salt", "tea"]
    errors = []

    def send(item_name):
        try:
            r = client.post("/api/commands", json={
                "transcript": f"add {item_name}",
                "user_id": "default-user-id"
            })
            assert r.status_code != 500
        except Exception as e:
            errors.append(f"{item_name}: {e}")

    threads = [threading.Thread(target=send, args=(i,)) for i in items]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(errors) == 0, f"Errors: {errors}"

def test_concurrent_mixed_operations():
    """Mixed ADD / REMOVE / UPDATE — no crash, no 500."""
    commands = [
        "add shampoo",
        "add milk",
        "remove shampoo",
        "add 650ml shampoo",
        "show my list",
    ]
    errors = []

    def send(cmd):
        try:
            r = client.post("/api/commands", json={"transcript": cmd, "user_id": "default-user-id"})
            assert r.status_code != 500
        except Exception as e:
            errors.append(f"{cmd}: {e}")

    threads = [threading.Thread(target=send, args=(c,)) for c in commands]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(errors) == 0, f"Errors: {errors}"
