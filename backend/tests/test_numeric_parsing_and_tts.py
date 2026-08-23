import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.ai.llm_service import llm_service, normalize_unit
from app.schemas.command import IntentEnum

def test_unit_normalization():
    assert normalize_unit("grams") == "g"
    assert normalize_unit("gram") == "g"
    assert normalize_unit("kilograms") == "kg"
    assert normalize_unit("kg") == "kg"
    assert normalize_unit("millilitres") == "ml"
    assert normalize_unit("milliliters") == "ml"
    assert normalize_unit("litres") == "L"
    assert normalize_unit("pieces") in ("pieces", "pcs")
    assert normalize_unit("bottles") in ("bottle", "bottles")
    assert normalize_unit("packets") in ("packet", "packets")

def test_numeric_preservation_500g_honey():
    cmd = llm_service.parse_command("Add 500g of honey")
    assert cmd.intent == IntentEnum.ADD_ITEM
    assert cmd.size == "500g"
    assert cmd.quantity == 1
    assert "5g" not in (cmd.size or "")

def test_numeric_preservation_1kg_butter():
    cmd = llm_service.parse_command("Add 1kg butter")
    assert cmd.intent == IntentEnum.ADD_ITEM
    assert cmd.size == "1kg"
    assert cmd.quantity == 1

def test_numeric_preservation_250ml_milk():
    cmd = llm_service.parse_command("Add 250ml milk")
    assert cmd.intent == IntentEnum.ADD_ITEM
    assert cmd.size == "250ml"
    assert cmd.quantity == 1

def test_decimal_numeric_preservation():
    cmd1 = llm_service.parse_command("Add 1.5kg rice")
    assert cmd1.size == "1.5kg"

    cmd2 = llm_service.parse_command("Add 0.5kg flour")
    assert cmd2.size == "0.5kg"

    cmd3 = llm_service.parse_command("Add 2.5L water")
    assert cmd3.size == "2.5L"

def test_quantity_vs_size_separation():
    cmd = llm_service.parse_command("Add 2 bottles of 500ml shampoo")
    assert cmd.quantity == 2
    assert cmd.unit in ("bottle", "bottles")
    assert cmd.size == "500ml"

def test_multi_item_quantity_preservation():
    cmd = llm_service.parse_command("Add 12 eggs, 3 packets of biscuits")
    assert len(cmd.items) == 2
    eggs_item = next(i for i in cmd.items if "egg" in i.item.lower())
    assert eggs_item.quantity == 12
    assert eggs_item.unit in ("pieces", "pcs", "eggs")

    biscuit_item = next(i for i in cmd.items if "biscuit" in i.item.lower())
    assert biscuit_item.quantity == 3

def test_no_underscore_in_messages():
    from app.database.connection import SessionLocal, init_db
    from app.services.shopping_service import shopping_service
    from app.schemas.command import ParsedCommand, IntentEnum, CommandItem

    init_db()
    db = SessionLocal()
    try:
        cmd = ParsedCommand(
            intent=IntentEnum.ADD_ITEM,
            item="honey",
            quantity=1,
            items=[CommandItem(item="honey", quantity=1)]
        )
        res = shopping_service.process_command(db, "test-tts-user-unique-99", cmd)
        assert res.success is True
        assert "_" not in res.message
        assert "underscore" not in res.message.lower()
        assert "null" not in res.message.lower()
    finally:
        db.close()
