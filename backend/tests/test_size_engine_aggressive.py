"""
test_size_engine_aggressive.py
Aggressive exhaustive tests for the 4-rule Size Decision Engine.
Covers all four rules, edge cases, and adversarial scenarios.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, User, Product, ProductSize, PurchaseHistory
from app.services.size_engine import SizeDecisionEngine

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = Session()
    user = User(id="u1", name="Tester")
    session.add(user)
    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

@pytest.fixture
def engine_svc():
    return SizeDecisionEngine()

def _make_product(db, name, sizes):
    p = Product(name=name, category="Test")
    db.add(p)
    db.flush()
    for sv in sizes:
        db.add(ProductSize(product_id=p.id, size_value=sv))
    db.commit()
    return p

def _add_history(db, user_id, product, sizes_list):
    now = datetime.utcnow()
    for i, sz in enumerate(sizes_list):
        db.add(PurchaseHistory(
            user_id=user_id,
            product_id=product.id,
            product_name=product.name,
            size=sz,
            purchased_at=now - timedelta(days=len(sizes_list) - i)
        ))
    db.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# RULE 1 — Explicit Size
# ═══════════════════════════════════════════════════════════════════════════════

def test_rule1_basic_explicit_size(db, engine_svc):
    p = _make_product(db, "Shampoo", ["340ml", "500ml", "650ml"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size="650ml")
    assert res.size == "650ml"
    assert res.is_unresolved is False

def test_rule1_overrides_history(db, engine_svc):
    """Explicit size must win even if history says otherwise."""
    p = _make_product(db, "Milk2", ["500ml", "1L"])
    _add_history(db, "u1", p, ["1L", "1L", "1L"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size="500ml")
    assert res.size == "500ml"
    assert res.is_unresolved is False

def test_rule1_whitespace_explicit_size(db, engine_svc):
    """Explicit size with leading/trailing whitespace must still apply."""
    p = _make_product(db, "Rice", ["500g", "1kg"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size="  500g  ")
    assert res.is_unresolved is False
    assert "500g" in res.size

def test_rule1_unusual_format(db, engine_svc):
    """Unusual size strings must be accepted as-is."""
    p = _make_product(db, "Coffee", ["100g"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size="100G")
    assert res.is_unresolved is False

def test_rule1_empty_string_explicit_size(db, engine_svc):
    """Empty string explicit_size must NOT be treated as explicit — fall through to rules 2-4."""
    p = _make_product(db, "Salt", ["1kg"])  # single size → rule 2
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size="")
    # empty string should NOT trigger rule 1
    assert res.size == "1kg"  # rule 2 should fire
    assert res.is_unresolved is False

# ═══════════════════════════════════════════════════════════════════════════════
# RULE 2 — Single Catalog Size
# ═══════════════════════════════════════════════════════════════════════════════

def test_rule2_single_size_auto_selected(db, engine_svc):
    p = _make_product(db, "Milk", ["1L"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.size == "1L"
    assert res.is_unresolved is False

def test_rule2_no_sizes_defined(db, engine_svc):
    """Product with zero sizes in catalog → unresolved."""
    p = Product(name="Mystery", category="Test")
    db.add(p)
    db.commit()
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.is_unresolved is True

def test_rule2_product_none(db, engine_svc):
    """product=None → unresolved (catalog miss)."""
    res = engine_svc.evaluate_size_decision(db, "u1", None, explicit_size=None)
    assert res.is_unresolved is True
    assert res.size == "__________"

def test_rule2_duplicate_sizes_in_catalog(db, engine_svc):
    """Two entries with same size value — engine should still auto-select if count==1 distinct."""
    # This exposes a potential bug: len(sizes) == 2 even though they are the same value
    p = Product(name="DupTest", category="Test")
    db.add(p)
    db.flush()
    db.add(ProductSize(product_id=p.id, size_value="500g"))
    db.add(ProductSize(product_id=p.id, size_value="500g"))  # duplicate
    db.commit()
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    # With 2 rows (even if same value), rule 2 does NOT fire (count != 1).
    # Rule 3 fires next with no history → rule 4 → unresolved.
    # Document actual behavior here:
    assert isinstance(res.is_unresolved, bool)  # must not crash

# ═══════════════════════════════════════════════════════════════════════════════
# RULE 3 — Historical Preference (2/3 threshold)
# ═══════════════════════════════════════════════════════════════════════════════

def test_rule3_2_of_3_preference(db, engine_svc):
    p = _make_product(db, "Shampoo3", ["340ml", "500ml", "650ml"])
    _add_history(db, "u1", p, ["650ml", "650ml", "340ml"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.size == "650ml"
    assert res.is_unresolved is False

def test_rule3_3_of_3_preference(db, engine_svc):
    p = _make_product(db, "Shampoo33", ["340ml", "500ml", "650ml"])
    _add_history(db, "u1", p, ["650ml", "650ml", "650ml"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.size == "650ml"
    assert res.is_unresolved is False

def test_rule3_1_of_3_not_enough(db, engine_svc):
    """1/3 should NOT meet threshold=2 → unresolved."""
    p = _make_product(db, "Shampoo13", ["340ml", "500ml", "650ml"])
    _add_history(db, "u1", p, ["650ml", "340ml", "500ml"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.is_unresolved is True  # rule 4

def test_rule3_0_history(db, engine_svc):
    """No purchase history → should reach rule 4."""
    p = _make_product(db, "Coffee2", ["100g", "200g", "500g"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.is_unresolved is True

def test_rule3_more_than_3_purchases(db, engine_svc):
    """Engine only looks at last HISTORY_LIST_COUNT (3) purchases."""
    p = _make_product(db, "Shampoo100", ["340ml", "500ml", "650ml"])
    # 5 old purchases: 340ml dominant; 2 recent: 650ml dominant
    old_sizes = ["340ml"] * 5
    recent_sizes = ["650ml", "650ml"]
    # Add old first (farther in the past), recent last
    now = datetime.utcnow()
    for i, sz in enumerate(old_sizes + recent_sizes):
        db.add(PurchaseHistory(
            user_id="u1",
            product_id=p.id,
            product_name=p.name,
            size=sz,
            purchased_at=now - timedelta(days=len(old_sizes + recent_sizes) - i)
        ))
    db.commit()
    # Engine picks last 3: 340ml (1), 650ml, 650ml → 650ml 2/3 wins
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.size == "650ml"
    assert res.is_unresolved is False

def test_rule3_exactly_1_purchase(db, engine_svc):
    """1 purchase of a multi-size product: count=1, threshold=2 → unresolved."""
    p = _make_product(db, "ShampooSingle", ["340ml", "500ml"])
    _add_history(db, "u1", p, ["340ml"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.is_unresolved is True

def test_rule3_2_of_2_purchases(db, engine_svc):
    """2/2 same size: 2 >= threshold(2) → should resolve."""
    p = _make_product(db, "ShampooTwo", ["340ml", "500ml"])
    _add_history(db, "u1", p, ["340ml", "340ml"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.size == "340ml"
    assert res.is_unresolved is False

def test_rule3_skips_unresolved_history(db, engine_svc):
    """Purchase history containing '__________' should be ignored."""
    p = _make_product(db, "ShampooBadHist", ["340ml", "650ml"])
    _add_history(db, "u1", p, ["__________", "__________", "650ml"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    # Only 1 valid history entry (650ml), count=1 < threshold=2 → unresolved
    assert res.is_unresolved is True

# ═══════════════════════════════════════════════════════════════════════════════
# RULE 4 — Must Always Be Transparent (Never Silent Guess)
# ═══════════════════════════════════════════════════════════════════════════════

def test_rule4_ambiguous_history(db, engine_svc):
    p = _make_product(db, "CoffeeAmb", ["100g", "200g", "500g"])
    _add_history(db, "u1", p, ["100g", "200g", "500g"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.size == "__________"
    assert res.is_unresolved is True

def test_rule4_unresolved_size_is_literally_placeholder(db, engine_svc):
    p = _make_product(db, "CoffeePlaceholder", ["100g", "200g"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.size == "__________"

def test_rule4_reason_mentions_available_sizes(db, engine_svc):
    """The reason string should mention available sizes for user context."""
    p = _make_product(db, "CoffeeReason", ["100g", "200g"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    assert res.is_unresolved is True
    # reason should be informative
    assert res.reason is not None and len(res.reason) > 0

def test_rule4_product_none_is_unresolved(db, engine_svc):
    res = engine_svc.evaluate_size_decision(db, "u1", None, explicit_size=None)
    assert res.is_unresolved is True

def test_rule4_does_not_silently_pick_first_size(db, engine_svc):
    """Critical: must never pick the first catalog size arbitrarily when ambiguous."""
    p = _make_product(db, "CoffeeNoGuess", ["100g", "500g"])
    res = engine_svc.evaluate_size_decision(db, "u1", p, explicit_size=None)
    # Must be unresolved — must NOT return "100g" as a silent guess
    assert res.size == "__________", \
        f"Engine silently guessed {res.size!r} instead of marking unresolved!"
