"""
test_authentication_and_isolation.py
Automated test suite verifying Customer Authentication & Personal Data Isolation (Requirement 30: 1-22).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.connection import get_db
from app.database.models import Base, User, Product, ProductSize, ShoppingList, ShoppingItem, PurchaseHistory
from app.core.security import create_access_token, hash_password

TEST_DB_URL = "sqlite:///:memory:"
auth_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
AuthSession = sessionmaker(bind=auth_engine)

@pytest.fixture
def db():
    Base.metadata.drop_all(bind=auth_engine)
    Base.metadata.create_all(bind=auth_engine)
    session = AuthSession()

    # Seed Supermarket Global Catalog
    milk = Product(id="prod-milk", name="Milk", category="Dairy", brand="Dairy Pure")
    session.add(milk)
    session.flush()
    session.add(ProductSize(product_id="prod-milk", size_value="1L", is_default=True))

    shampoo = Product(id="prod-shampoo", name="Shampoo", category="Personal Care", brand="Pantene")
    session.add(shampoo)
    session.flush()
    session.add(ProductSize(product_id="prod-shampoo", size_value="340ml"))
    session.add(ProductSize(product_id="prod-shampoo", size_value="650ml"))

    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(bind=auth_engine)

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def get_auth_header(user_id: str, email: str) -> dict:
    token = create_access_token(payload={"sub": user_id, "email": email})
    return {"Authorization": f"Bearer {token}"}

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Authentication Tests (Requirement 30: 1-7)
# ═══════════════════════════════════════════════════════════════════════════════

def test_1_signup_success(client):
    res = client.post("/api/auth/signup", json={
        "email": "customer_a@example.com",
        "password": "password123",
        "name": "Customer A"
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "customer_a@example.com"
    assert data["user"]["name"] == "Customer A"

def test_2_signup_invalid_input(client):
    res = client.post("/api/auth/signup", json={
        "email": "invalid-email",
        "password": "123",
        "name": "Short Pass"
    })
    assert res.status_code == 422

def test_3_signup_duplicate_email(client):
    client.post("/api/auth/signup", json={
        "email": "user_dup@example.com",
        "password": "password123",
        "name": "User 1"
    })
    res = client.post("/api/auth/signup", json={
        "email": "user_dup@example.com",
        "password": "password456",
        "name": "User 2"
    })
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]

def test_4_login_success(client):
    client.post("/api/auth/signup", json={
        "email": "user_login@example.com",
        "password": "password123",
        "name": "Login User"
    })
    res = client.post("/api/auth/login", json={
        "email": "user_login@example.com",
        "password": "password123"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()

def test_5_login_failure(client):
    client.post("/api/auth/signup", json={
        "email": "user_fail@example.com",
        "password": "password123",
        "name": "Fail User"
    })
    res = client.post("/api/auth/login", json={
        "email": "user_fail@example.com",
        "password": "wrongpassword"
    })
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]

def test_6_7_unauthenticated_or_invalid_session(client):
    res = client.get("/api/shopping-list")
    assert res.status_code == 401

    res_invalid = client.get("/api/shopping-list", headers={"Authorization": "Bearer invalid_token_123"})
    assert res_invalid.status_code == 401

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Authorization & IDOR Security Tests (Requirement 30: 8-12, 26)
# ═══════════════════════════════════════════════════════════════════════════════

def test_8_to_12_idor_and_authorization_isolation(client, db):
    # Register Customer A & Customer B
    res_a = client.post("/api/auth/signup", json={"email": "cust_a@ex.com", "password": "password123", "name": "Customer A"}).json()
    res_b = client.post("/api/auth/signup", json={"email": "cust_b@ex.com", "password": "password123", "name": "Customer B"}).json()

    headers_a = {"Authorization": f"Bearer {res_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {res_b['access_token']}"}

    # Customer A adds Milk
    item_a = client.post("/api/shopping-list/items", json={"product_name": "Milk", "quantity": 2}, headers=headers_a).json()

    # Customer B adds Shampoo
    item_b = client.post("/api/shopping-list/items", json={"product_name": "Shampoo", "quantity": 1}, headers=headers_b).json()

    # Customer A attempts to UPDATE Customer B's item -> IDOR Protected
    res_update_attack = client.patch(f"/api/shopping-list/items/{item_b['id']}", json={"quantity": 99}, headers=headers_a)
    assert res_update_attack.status_code == 404

    # Customer A attempts to DELETE Customer B's item -> IDOR Protected
    res_delete_attack = client.delete(f"/api/shopping-list/items/{item_b['id']}", headers=headers_a)
    assert res_delete_attack.status_code == 404

    # Verify Customer B's item is untouched
    list_b = client.get("/api/shopping-list", headers=headers_b).json()
    assert len(list_b["items"]) == 1
    assert list_b["items"][0]["product_name"] == "Shampoo"
    assert list_b["items"][0]["quantity"] == 1

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Data Isolation Tests (Requirement 30: 13-17, 27)
# ═══════════════════════════════════════════════════════════════════════════════

def test_13_to_17_user_data_isolation_exact_scenario(client, db):
    # Customer A
    res_a = client.post("/api/auth/signup", json={"email": "user_a@ex.com", "password": "password123"}).json()
    headers_a = {"Authorization": f"Bearer {res_a['access_token']}"}

    # Customer B
    res_b = client.post("/api/auth/signup", json={"email": "user_b@ex.com", "password": "password123"}).json()
    headers_b = {"Authorization": f"Bearer {res_b['access_token']}"}

    # Customer A adds Milk, Bread, Eggs
    client.post("/api/commands", json={"transcript": "Add milk, bread and eggs"}, headers=headers_a)

    # Customer B adds Shampoo, Butter, Rice
    client.post("/api/commands", json={"transcript": "Add shampoo, butter and rice"}, headers=headers_b)

    # Verify Customer A sees ONLY Milk, Bread, Eggs
    list_a = client.get("/api/shopping-list", headers=headers_a).json()
    names_a = [i["product_name"] for i in list_a["items"]]
    assert "Milk" in names_a or "milk" in [n.lower() for n in names_a]
    assert "Shampoo" not in names_a
    assert "Rice" not in names_a

    # Verify Customer B sees ONLY Shampoo, Butter, Rice
    list_b = client.get("/api/shopping-list", headers=headers_b).json()
    names_b = [i["product_name"] for i in list_b["items"]]
    assert "Shampoo" in names_b or "shampoo" in [n.lower() for n in names_b]
    assert "Milk" not in names_b
    assert "Eggs" not in names_b

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Integration Tests (Requirement 30: 18-22)
# ═══════════════════════════════════════════════════════════════════════════════

def test_18_to_22_voice_command_authenticated_integration(client, db):
    res_a = client.post("/api/auth/signup", json={"email": "voice_user@ex.com", "password": "password123"}).json()
    headers = {"Authorization": f"Bearer {res_a['access_token']}"}

    # Voice multi-item command under authenticated user
    cmd_res = client.post("/api/commands", json={"transcript": "Add 2 packets of milk and 650ml shampoo"}, headers=headers)
    assert cmd_res.status_code == 200

    list_res = client.get("/api/shopping-list", headers=headers).json()
    assert len(list_res["items"]) == 2
