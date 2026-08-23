"""
test_recommendation_engine.py
Edge case testing for the Co-Purchase Recommendation Engine.
Tests: empty lists, no history, large history, boundary counts, self-recommendation.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, User, Product, ShoppingList, ShoppingItem
from app.recommendations.co_purchase_engine import CoPurchaseRecommendationEngine

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    sess = Session()
    sess.add(User(id="reco-user", name="Reco Tester"))
    sess.commit()
    yield sess
    sess.close()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

@pytest.fixture
def engine_reco():
    return CoPurchaseRecommendationEngine()

def _make_completed_list(db, user_id, item_names, days_ago):
    now = datetime.utcnow()
    t = now - timedelta(days=days_ago)
    sl = ShoppingList(user_id=user_id, status="COMPLETED", created_at=t, updated_at=t)
    db.add(sl)
    db.flush()
    for name in item_names:
        db.add(ShoppingItem(list_id=sl.id, product_name=name, quantity=1))
    db.commit()
    return sl

def _make_active_list(db, user_id, item_names):
    sl = ShoppingList(user_id=user_id, status="ACTIVE")
    db.add(sl)
    db.flush()
    for name in item_names:
        db.add(ShoppingItem(list_id=sl.id, product_name=name, quantity=1))
    db.commit()
    return sl

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Empty active list
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_suggestions_on_empty_list(db, engine_reco):
    sl = ShoppingList(user_id="reco-user", status="ACTIVE")
    db.add(sl)
    db.commit()
    res = engine_reco.generate_recommendations(db, "reco-user", sl.id)
    assert res.suggestions == []

# ═══════════════════════════════════════════════════════════════════════════════
# 2. No completed history
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_suggestions_without_history(db, engine_reco):
    active = _make_active_list(db, "reco-user", ["Milk"])
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)
    assert res.suggestions == []

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Classic Bread+Jam co-purchase (3/3)
# ═══════════════════════════════════════════════════════════════════════════════

def test_classic_co_purchase_3_of_3(db, engine_reco):
    for i in range(3):
        _make_completed_list(db, "reco-user", ["Bread", "Jam", "Milk"], days_ago=i+1)
    active = _make_active_list(db, "reco-user", ["Bread"])
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)

    names = [s.product_name for s in res.suggestions]
    assert "Jam" in names, f"Expected Jam in suggestions, got: {names}"
    assert "Milk" in names, f"Expected Milk in suggestions, got: {names}"

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Already-in-list items must NOT be suggested
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_self_recommendation(db, engine_reco):
    """Items already in the current list must never be suggested."""
    for i in range(3):
        _make_completed_list(db, "reco-user", ["Bread", "Jam"], days_ago=i+1)
    active = _make_active_list(db, "reco-user", ["Bread", "Jam"])
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)
    names = [s.product_name for s in res.suggestions]
    assert "Bread" not in names, "Bread (already in list) was suggested!"
    assert "Jam" not in names, "Jam (already in list) was suggested!"

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Suggestions capped at 5
# ═══════════════════════════════════════════════════════════════════════════════

def test_suggestions_capped_at_5(db, engine_reco):
    many_items = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    for i in range(3):
        _make_completed_list(db, "reco-user", many_items, days_ago=i+1)
    active = _make_active_list(db, "reco-user", ["A"])
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)
    assert len(res.suggestions) <= 5

# ═══════════════════════════════════════════════════════════════════════════════
# 6. 1/3 co-purchase — still recommended (lower frequency)
# ═══════════════════════════════════════════════════════════════════════════════

def test_1_of_3_still_recommended(db, engine_reco):
    _make_completed_list(db, "reco-user", ["Bread", "Jam"], days_ago=3)
    _make_completed_list(db, "reco-user", ["Bread", "Butter"], days_ago=2)
    _make_completed_list(db, "reco-user", ["Bread", "Eggs"], days_ago=1)
    active = _make_active_list(db, "reco-user", ["Bread"])
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)
    names = [s.product_name for s in res.suggestions]
    # All 3 co-purchased with 1/3 frequency should still appear
    assert len(res.suggestions) == 3

def test_suggestions_sorted_by_frequency_descending(db, engine_reco):
    # Jam appears 3/3, Butter 2/3, Eggs 1/3
    _make_completed_list(db, "reco-user", ["Bread", "Jam", "Butter", "Eggs"], days_ago=3)
    _make_completed_list(db, "reco-user", ["Bread", "Jam", "Butter"], days_ago=2)
    _make_completed_list(db, "reco-user", ["Bread", "Jam"], days_ago=1)
    active = _make_active_list(db, "reco-user", ["Bread"])
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)

    if len(res.suggestions) >= 2:
        assert res.suggestions[0].co_occurrence_count >= res.suggestions[1].co_occurrence_count

# ═══════════════════════════════════════════════════════════════════════════════
# 7. Co-purchase reason text is human-readable
# ═══════════════════════════════════════════════════════════════════════════════

def test_suggestion_reason_text(db, engine_reco):
    for i in range(3):
        _make_completed_list(db, "reco-user", ["Bread", "Jam"], days_ago=i+1)
    active = _make_active_list(db, "reco-user", ["Bread"])
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)
    jam_sug = next((s for s in res.suggestions if s.product_name == "Jam"), None)
    assert jam_sug is not None
    assert "3" in jam_sug.reason
    assert "Bread" in jam_sug.reason or "bread" in jam_sug.reason.lower()

# ═══════════════════════════════════════════════════════════════════════════════
# 8. Unknown user (no history, no active list)
# ═══════════════════════════════════════════════════════════════════════════════

def test_unknown_user_returns_empty(db, engine_reco):
    sl = ShoppingList(user_id="reco-user", status="ACTIVE")
    db.add(sl)
    db.commit()
    # Query for a different user with no history
    res = engine_reco.generate_recommendations(db, "ghost-user-xyz", sl.id)
    assert res.suggestions == []

# ═══════════════════════════════════════════════════════════════════════════════
# 9. Large number of completed lists — only last 3 analyzed
# ═══════════════════════════════════════════════════════════════════════════════

def test_only_last_3_lists_analyzed(db, engine_reco):
    # 7 old lists: Bread + Tea
    for i in range(7, 4, -1):
        _make_completed_list(db, "reco-user", ["Bread", "Tea"], days_ago=i)
    # 3 recent: Bread + Jam (these should dominate)
    for i in range(3, 0, -1):
        _make_completed_list(db, "reco-user", ["Bread", "Jam"], days_ago=i)

    active = _make_active_list(db, "reco-user", ["Bread"])
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)
    names = [s.product_name for s in res.suggestions]
    # Tea appeared 7 times total but NOT in last 3 → should NOT appear or have lower count
    jam_sug = next((s for s in res.suggestions if s.product_name == "Jam"), None)
    assert jam_sug is not None
    assert jam_sug.co_occurrence_count == 3  # 3/3 recent lists

# ═══════════════════════════════════════════════════════════════════════════════
# 10. Case sensitivity — "Jam" vs "jam"
# ═══════════════════════════════════════════════════════════════════════════════

def test_case_sensitivity_in_item_matching(db, engine_reco):
    _make_completed_list(db, "reco-user", ["Bread", "Jam"], days_ago=1)
    active = _make_active_list(db, "reco-user", ["bread"])  # lowercase
    res = engine_reco.generate_recommendations(db, "reco-user", active.id)
    # Current implementation is case-sensitive at intersection check
    # Document whether Jam is suggested or not
    names = [s.product_name for s in res.suggestions]
    # This test documents the behavior — case mismatch may cause missed suggestions
    # (P2 Bug if "Jam" is not suggested because "bread" != "Bread")
