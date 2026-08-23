import re
import json
import logging
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.schemas.command import ParsedCommand, IntentEnum, CommandItem

logger = logging.getLogger("uvicorn.error")

NUMBER_MAP = {
    "one": 1, "a": 1, "an": 1, "single": 1,
    "two": 2, "couple": 2, "pair": 2,
    "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10
}

UNIT_MAPPING = {
    "gram": "g", "grams": "g", "g": "g",
    "kilogram": "kg", "kilograms": "kg", "kg": "kg",
    "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml", "ml": "ml",
    "litre": "L", "litres": "L", "liter": "L", "liters": "L", "l": "L",
    "oz": "oz", "lbs": "lbs", "pound": "lbs", "pounds": "lbs",
    "packet": "packets", "packets": "packets", "pack": "packs", "packs": "packs",
    "bottle": "bottles", "bottles": "bottles",
    "can": "cans", "cans": "cans",
    "bag": "bags", "bags": "bags",
    "piece": "pieces", "pieces": "pieces", "pc": "pcs", "pcs": "pcs",
    "egg": "pieces", "eggs": "pieces"
}

def normalize_unit(unit_str: Optional[str]) -> Optional[str]:
    """Centralized unit normalization without modifying numeric values."""
    if not unit_str:
        return None
    u = unit_str.strip().lower()
    return UNIT_MAPPING.get(u, u)

SIZE_REGEX = r'\b(\d+(?:\.\d+)?)\s*(ml|milliliter|milliliters|millilitre|millilitres|l|liter|liters|litre|litres|g|gram|grams|kg|kilogram|kilograms|oz|lbs|pound|pounds)\b'
QTY_UNIT_REGEX = r'\b(\d+)\s*(bottles?|packs?|packets?|cans?|bags?|pieces?|pcs|eggs?)\b'

SYSTEM_PROMPT = """
You are the natural language parser for 'ShopVA', a Smart Voice Shopping Assistant.
Your task is to parse spoken user shopping commands into strict JSON matching this schema:

{
  "intent": "ADD_ITEM" | "ADD_ITEMS" | "REMOVE_ITEM" | "UPDATE_ITEM" | "SHOW_LIST" | "CLEAR_LIST",
  "item": "product name string or null",
  "quantity": integer (default 1),
  "unit": "packaging unit or null (e.g. bottle, packet, pcs)",
  "size": "explicit package size string or null (e.g. 500g, 1.5kg, 650ml, 1L)",
  "items": [
    {
      "item": "product name",
      "quantity": integer,
      "unit": "string or null",
      "size": "string or null"
    }
  ]
}

RULES:
1. QUANTITY vs SIZE SEPARATION:
   - "Add 500g honey" -> quantity=1, size="500g", unit=null
   - "Add 2 bottles of 500ml shampoo" -> quantity=2, unit="bottle", size="500ml"
   - "Add 12 eggs" -> quantity=12, unit="pieces", size=null
   - "Add 1.5kg rice" -> quantity=1, size="1.5kg", unit=null
2. Preserve exact numeric values. NEVER convert 500g to 5g or 1000g to 10g.
3. Output ONLY valid JSON matching the schema.
"""

class LLMCommandService:
    def __init__(self):
        self.groq_client = None
        self.groq_auth_failed = False
        if settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip():
            try:
                from groq import Groq
                cleaned_key = settings.GROQ_API_KEY.strip()
                self.groq_client = Groq(api_key=cleaned_key)
                logger.info("[LLM SERVICE] Initialized Groq client with model: %s", settings.GROQ_MODEL)
            except Exception as e:
                logger.error("[LLM SERVICE] Failed to initialize Groq client: %s", e)

    def parse_command(self, transcript: str) -> ParsedCommand:
        text = transcript.strip()
        if not text:
            return ParsedCommand(intent=IntentEnum.ADD_ITEM, raw_transcript=transcript)

        groq_failed = getattr(self, "groq_auth_failed", False)
        groq_client = getattr(self, "groq_client", None)

        # Attempt LLM processing if Groq is available and authenticated
        if groq_client and not groq_failed:
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = groq_client.chat.completions.create(
                        model=settings.GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": text}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.0
                    )
                    raw_json = response.choices[0].message.content
                    data = json.loads(raw_json)

                    # Capitalize item names
                    if "items" in data and isinstance(data["items"], list):
                        for item_dict in data["items"]:
                            if isinstance(item_dict, dict) and item_dict.get("item"):
                                item_dict["item"] = item_dict["item"].strip().capitalize()

                    parsed = ParsedCommand(**data)
                    parsed.raw_transcript = transcript

                    # Single-item synchronization
                    if parsed.item:
                        parsed.item = parsed.item.strip().capitalize()

                    if parsed.items and len(parsed.items) > 0:
                        first = parsed.items[0]
                        if not parsed.item:
                            parsed.item = first.item
                        if parsed.quantity is None:
                            parsed.quantity = first.quantity if first.quantity is not None else 1
                        if not parsed.unit:
                            parsed.unit = first.unit
                        if not parsed.size:
                            parsed.size = first.size
                    elif parsed.item:
                        if parsed.quantity is None:
                            parsed.quantity = 1
                        parsed.items = [CommandItem(
                            item=parsed.item,
                            product_query=parsed.item,
                            quantity=parsed.quantity,
                            unit=parsed.unit,
                            size=parsed.size
                        )]

                    # Deterministic Post-Validation against Transcript
                    return self._validate_and_reconcile_numerics(transcript, parsed)

                except Exception as e:
                    err_str = str(e)
                    if "401" in err_str or "Invalid API Key" in err_str or "Unauthorized" in err_str:
                        self.groq_auth_failed = True
                        logger.error("[LLM SERVICE] Groq API authentication failed (401). Disabling Groq API.")
                        break
                    logger.warning("[LLM SERVICE] Groq API attempt %d failed: %s", attempt + 1, e)

        # Fallback to deterministic rule parser
        return self._fallback_rule_parser(transcript)

    def _validate_and_reconcile_numerics(self, transcript: str, parsed: ParsedCommand) -> ParsedCommand:
        """
        Deterministic post-validation of LLM structured output against original transcript.
        Guarantees exact numeric preservation (e.g. 500g is never truncated to 5g).
        """
        seg_text = transcript.strip().lower()

        # Check for explicit package size (e.g. 500g, 1.5kg, 250ml, 1L)
        size_match = re.search(SIZE_REGEX, seg_text, flags=re.IGNORECASE)
        if size_match:
            val_str = size_match.group(1)
            raw_unit = size_match.group(2).lower()
            norm_u = normalize_unit(raw_unit)
            exact_size = f"{val_str}{norm_u}"

            parsed.size = exact_size
            if parsed.items:
                for item in parsed.items:
                    item.size = exact_size

        # Check for explicit item count/quantity (e.g. 2 bottles, 12 eggs, 3 packets)
        qty_unit_match = re.search(QTY_UNIT_REGEX, seg_text, flags=re.IGNORECASE)
        if qty_unit_match:
            qty_val = int(qty_unit_match.group(1))
            unit_val = normalize_unit(qty_unit_match.group(2))
            parsed.quantity = qty_val
            parsed.unit = unit_val
            if parsed.items:
                for item in parsed.items:
                    item.quantity = qty_val
                    item.unit = unit_val

        return parsed

    def _fallback_rule_parser(self, transcript: str) -> ParsedCommand:
        text = transcript.strip().lower()

        # Check for CLEAR / SHOW
        if any(kw in text for kw in ["clear list", "clear my list", "delete all items"]):
            return ParsedCommand(intent=IntentEnum.CLEAR_LIST, raw_transcript=transcript)
        if any(kw in text for kw in ["show list", "show my list", "view list", "what is on my list"]):
            return ParsedCommand(intent=IntentEnum.SHOW_LIST, raw_transcript=transcript)

        # Extract explicit size
        size_match = re.search(SIZE_REGEX, text, flags=re.IGNORECASE)
        extracted_size = None
        if size_match:
            val = size_match.group(1)
            raw_u = size_match.group(2).lower()
            norm_u = normalize_unit(raw_u)
            extracted_size = f"{val}{norm_u}"

        text_without_size = re.sub(SIZE_REGEX, '', text, flags=re.IGNORECASE) if size_match else text

        # Check for REMOVE
        remove_match = (
            re.search(r'\b(?:remove|delete|drop|erase)\b\s+(.*)', text) or
            re.search(r'\btake\b\s+(.*?)\s+\boff\b', text) or
            re.search(r'(.*?)\s+\boff my list\b', text)
        )
        if remove_match:
            item_raw = remove_match.group(1)
            item_clean = self._clean_item_name(item_raw)
            return ParsedCommand(
                intent=IntentEnum.REMOVE_ITEM,
                item=item_clean,
                quantity=1,
                size=extracted_size,
                raw_transcript=transcript
            )

        # Check for UPDATE
        update_match = re.search(r'\b(?:change|update|make|set)\b\s+(.*)', text)
        if update_match:
            item_raw = update_match.group(1)
            item_clean = self._clean_item_name(item_raw)
            return ParsedCommand(
                intent=IntentEnum.UPDATE_ITEM,
                item=item_clean,
                quantity=1,
                size=extracted_size,
                raw_transcript=transcript
            )

        # Standalone size utterance (e.g. "650ml", "500g")
        ACTION_KEYWORDS = r'\b(?:add|include|buy|i need|put|get|want|at|remove|delete|drop|erase|change|update|make|set|take)\b'
        has_action_keyword = bool(re.search(ACTION_KEYWORDS, text, flags=re.IGNORECASE))
        text_without_size_stripped = text_without_size.strip()
        if extracted_size and not has_action_keyword and len(text_without_size_stripped.split()) <= 1:
            return ParsedCommand(
                intent=IntentEnum.UPDATE_ITEM,
                item=None,
                size=extracted_size,
                raw_transcript=transcript
            )

        # ADD Intent parsing
        add_prefix_match = re.search(r'^\s*(?:add|include|buy|i need|put|get|want|at)\b\s*(.*)', text, flags=re.IGNORECASE)
        text_to_split = add_prefix_match.group(1) if add_prefix_match else text

        raw_segments = re.split(r'\s*(?:,|\band\b|;)\s*', text_to_split)
        extracted_items = []
        for seg in raw_segments:
            cmd_item = self._parse_segment_to_item(seg)
            if cmd_item and cmd_item.item:
                extracted_items.append(cmd_item)

        if extracted_items:
            first = extracted_items[0]
            intent = IntentEnum.ADD_ITEMS if len(extracted_items) > 1 else IntentEnum.ADD_ITEM
            return ParsedCommand(
                intent=intent,
                items=extracted_items,
                item=first.item,
                quantity=first.quantity,
                unit=first.unit,
                size=first.size,
                raw_transcript=transcript
            )

        # Fallback single item
        item_clean = self._clean_item_name(text)
        single_item = CommandItem(item=item_clean, quantity=1, size=extracted_size)
        return ParsedCommand(
            intent=IntentEnum.ADD_ITEM,
            items=[single_item],
            item=item_clean,
            quantity=1,
            size=extracted_size,
            raw_transcript=transcript
        )

    def _parse_segment_to_item(self, segment: str) -> Optional[CommandItem]:
        seg_text = segment.strip().lower()
        if not seg_text:
            return None

        extracted_size = None
        size_match = re.search(SIZE_REGEX, seg_text, flags=re.IGNORECASE)
        if size_match:
            val_str = size_match.group(1)
            raw_u = size_match.group(2).lower()
            norm_u = normalize_unit(raw_u)
            extracted_size = f"{val_str}{norm_u}"

        text_no_size = re.sub(SIZE_REGEX, '', seg_text, flags=re.IGNORECASE) if size_match else seg_text

        # Extract packaging unit
        unit_match = re.search(
            r'\b(packets?|packs?|bottles?|cans?|bags?|pieces?|pcs|eggs?)\b',
            text_no_size,
            flags=re.IGNORECASE
        )
        extracted_unit = None
        if unit_match:
            u_raw = unit_match.group(1).lower()
            extracted_unit = normalize_unit(u_raw)

        # Extract quantity
        quantity = 1
        for word, val in NUMBER_MAP.items():
            if re.search(r'\b' + word + r'\b', text_no_size, flags=re.IGNORECASE):
                quantity = val
                break

        digit_qty = re.search(r'\b(\d+)\b', text_no_size)
        if digit_qty:
            quantity = int(digit_qty.group(1))

        cleaned_item = self._clean_item_name(seg_text)
        if not cleaned_item or cleaned_item.lower() in ("and", ",", ";"):
            return None

        return CommandItem(
            item=cleaned_item,
            quantity=quantity,
            unit=extracted_unit,
            size=extracted_size
        )

    def _clean_item_name(self, text: str) -> str:
        cleaned = re.sub(SIZE_REGEX, '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*(?:at|add|include|buy|i need|put|get|want|please)\b\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|a|an)\b\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(?:bottles?|packs?|packets?|cans?|bags?|pieces?|pcs)\s+of\b', '', cleaned, flags=re.IGNORECASE)

        stop_words = ["on my list", "to my list", "from my list", "off my list", "off", "please", "of", "the", "some", "my"]
        for sw in stop_words:
            cleaned = re.sub(r'\b' + re.escape(sw) + r'\b', '', cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned.capitalize() if cleaned else ""

llm_service = LLMCommandService()
