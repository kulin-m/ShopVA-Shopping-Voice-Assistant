"""
test_nlp_rule_parser.py
Exhaustive unit tests for the rule-based fallback NLU parser.
Tests: intents, quantities, sizes, unit normalization, adversarial inputs.
Does NOT call Groq API — patches Groq client to None to force fallback path.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import patch
from app.ai.llm_service import LLMCommandService
from app.schemas.command import IntentEnum

# ── Always use fallback (no Groq) ─────────────────────────────────────────────
@pytest.fixture
def parser():
    """A parser instance with Groq client explicitly disabled."""
    svc = LLMCommandService.__new__(LLMCommandService)
    svc.groq_client = None  # force fallback
    return svc

# ═══════════════════════════════════════════════════════════════════════════════
# 1. ADD INTENT VARIATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript,expected_item_fragment", [
    ("add shampoo",              "Shampoo"),
    ("Add Shampoo",              "Shampoo"),
    ("ADD SHAMPOO",              "Shampoo"),
    ("buy shampoo",              "Shampoo"),
    ("get shampoo",              "Shampoo"),
    ("i need shampoo",           "Shampoo"),
    ("put shampoo on my list",   "Shampoo"),
    ("include shampoo",          "Shampoo"),
    ("want shampoo",             "Shampoo"),
    ("at shampoo",               "Shampoo"),
])
def test_add_intent_variations(parser, transcript, expected_item_fragment):
    result = parser._fallback_rule_parser(transcript)
    assert result.intent == IntentEnum.ADD_ITEM, f"Failed: {transcript!r}"
    assert expected_item_fragment.lower() in result.item.lower(), f"Item mismatch for {transcript!r}: got {result.item!r}"

# ═══════════════════════════════════════════════════════════════════════════════
# 2. REMOVE INTENT VARIATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript", [
    "remove shampoo",
    "Remove Shampoo",
    "delete shampoo",
    "drop shampoo",
    "erase shampoo",
    "take shampoo off",
    "shampoo off my list",
])
def test_remove_intent_variations(parser, transcript):
    result = parser._fallback_rule_parser(transcript)
    assert result.intent == IntentEnum.REMOVE_ITEM, f"Failed: {transcript!r} → {result.intent}"

# ═══════════════════════════════════════════════════════════════════════════════
# 3. UPDATE INTENT VARIATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript", [
    "change shampoo to 650ml",
    "make shampoo 650ml",
    "update shampoo to 650ml",
    "set shampoo 650ml",
])
def test_update_intent_variations(parser, transcript):
    result = parser._fallback_rule_parser(transcript)
    assert result.intent == IntentEnum.UPDATE_ITEM, f"Failed: {transcript!r}"

# ═══════════════════════════════════════════════════════════════════════════════
# 4. QUANTITY EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript,expected_qty", [
    ("add 2 shampoos",              2),
    ("add two shampoos",            2),
    ("add three shampoos",          3),
    ("add 10 shampoos",             10),
    ("add one shampoo",             1),
    ("add a shampoo",               1),
    ("buy five units of milk",      5),
    ("i need two bottles of milk",  2),
    ("add single shampoo",          1),
])
def test_quantity_extraction(parser, transcript, expected_qty):
    result = parser._fallback_rule_parser(transcript)
    assert result.quantity == expected_qty, f"Failed: {transcript!r} → qty={result.quantity}, want {expected_qty}"

# ═══════════════════════════════════════════════════════════════════════════════
# 5. SIZE UNIT NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript,expected_size", [
    ("add 650ml shampoo",               "650ml"),
    ("add 650 ml shampoo",              "650ml"),
    ("add 650ML shampoo",               "650ml"),
    ("add 1L milk",                     "1L"),
    ("add 1 liter milk",                "1L"),
    ("add 1 liters milk",               "1L"),
    ("add 250g butter",                 "250g"),
    ("add 250 gram butter",             "250g"),
    ("add 250 grams butter",            "250g"),
    ("add 1kg rice",                    "1kg"),
    ("add 1 kilogram rice",             "1kg"),
    ("add 500 grams of rice",           "500g"),
    ("give me 500 grams of rice",       "500g"),
    ("add 100g coffee",                 "100g"),
])
def test_size_normalization(parser, transcript, expected_size):
    result = parser._fallback_rule_parser(transcript)
    assert result.size == expected_size, f"Failed: {transcript!r} → size={result.size!r}, want {expected_size!r}"

# ═══════════════════════════════════════════════════════════════════════════════
# 6. STANDALONE SIZE → UPDATE_ITEM
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript,expected_size", [
    ("650ml",    "650ml"),
    ("250g",     "250g"),
    ("1L",       "1L"),
    ("1kg",      "1kg"),
    ("500g",     "500g"),
])
def test_standalone_size_becomes_update_intent(parser, transcript, expected_size):
    result = parser._fallback_rule_parser(transcript)
    assert result.intent == IntentEnum.UPDATE_ITEM, f"Failed: {transcript!r} → {result.intent}"
    assert result.size == expected_size, f"Failed: {transcript!r} → size={result.size!r}"
    assert result.item is None, f"Failed: item should be None for standalone size, got {result.item!r}"

# ═══════════════════════════════════════════════════════════════════════════════
# 7. CLEAR LIST
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript", [
    "clear list",
    "clear my list",
    "delete all items",
])
def test_clear_list_intent(parser, transcript):
    result = parser._fallback_rule_parser(transcript)
    assert result.intent == IntentEnum.CLEAR_LIST

# ═══════════════════════════════════════════════════════════════════════════════
# 8. SHOW LIST
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript", [
    "show list",
    "show my list",
    "view list",
    "what is on my list",
])
def test_show_list_intent(parser, transcript):
    result = parser._fallback_rule_parser(transcript)
    assert result.intent == IntentEnum.SHOW_LIST

# ═══════════════════════════════════════════════════════════════════════════════
# 9. PARSER MUST NEVER CRASH (Adversarial / Fuzz)
# ═══════════════════════════════════════════════════════════════════════════════

ADVERSARIAL_INPUTS = [
    "",
    " ",
    "\n",
    "\t",
    "!@#$%^&*()",
    "😀🛒🧴",
    "a" * 10_000,
    "1 2 3 4 5 6 7 8 9 10",
    "add add add add add add",
    "remove remove remove",
    "650ml 1L 250g 1kg",
    "add",
    "add add",
    "ADD",
    "get the usual one",
    "the bigger shampoo please",
    "maybe add some milk",
    "can you get me shampoo",
    "don't forget shampoo",
    "I think I need some shampoo",
    "shampoo shampoo shampoo",
    "add 999999999 shampoos",
    "add -1 shampoo",
    "add 0 shampoo",
    "add NaN shampoo",
    "add shampoo shampoo shampoo",
    "add shampoo and milk and bread",
    "add 650ml and 250g shampoo",
    "remove add shampoo",
    "add <script>alert(1)</script>",
    "'; DROP TABLE shopping_items; --",
    "add shampoo\x00null",
    "add \x01\x02\x03",
    "   add    shampoo   ",
    "add   650  ml  shampoo",
]

@pytest.mark.parametrize("transcript", ADVERSARIAL_INPUTS)
def test_parser_never_crashes(parser, transcript):
    """The fallback parser must never raise an exception regardless of input."""
    try:
        result = parser._fallback_rule_parser(transcript)
        # Must return a valid ParsedCommand with a valid intent
        assert result.intent in IntentEnum.__members__.values()
    except Exception as e:
        pytest.fail(f"Parser CRASHED on input {transcript!r}: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 10. ITEM NAME EXTRACTION ACCURACY
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript,expected_item", [
    ("add shampoo",              "Shampoo"),
    ("buy milk",                 "Milk"),
    ("add 650ml shampoo",        "Shampoo"),
    ("add 250 gram of butter",   "Butter"),
    ("add 1kg rice",             "Rice"),
    ("add three bottles of milk","Milk"),
    ("buy five units of milk",   "Milk"),
])
def test_item_name_extraction(parser, transcript, expected_item):
    result = parser._fallback_rule_parser(transcript)
    assert result.item is not None
    assert expected_item.lower() in result.item.lower(), \
        f"Item mismatch: {transcript!r} → {result.item!r}, expected fragment {expected_item!r}"

# ═══════════════════════════════════════════════════════════════════════════════
# 11. SIZE + QUANTITY COMBINATION
# ═══════════════════════════════════════════════════════════════════════════════

def test_two_packs_of_250g_butter(parser):
    """'add two 250g butter' → qty=2, size=250g"""
    result = parser._fallback_rule_parser("add two 250g butter")
    assert result.quantity == 2
    assert result.size == "250g"
    assert result.intent == IntentEnum.ADD_ITEM

def test_three_bottles_650ml_shampoo(parser):
    result = parser._fallback_rule_parser("add three 650ml bottles of shampoo")
    assert result.quantity == 3
    assert result.size == "650ml"

# ═══════════════════════════════════════════════════════════════════════════════
# 12. PARSE_COMMAND WRAPPER — NEVER CRASHES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("transcript", ADVERSARIAL_INPUTS[:20])
def test_parse_command_wrapper_never_crashes(parser, transcript):
    """The top-level parse_command (with no Groq client) must never raise."""
    try:
        result = parser.parse_command(transcript)
        assert result.intent in IntentEnum.__members__.values()
    except Exception as e:
        pytest.fail(f"parse_command CRASHED on {transcript!r}: {e}")
