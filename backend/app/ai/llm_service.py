import json
import re
import time
import logging
from typing import Optional, Dict, Any
from app.core.config import settings
from app.schemas.command import ParsedCommand, IntentEnum

logger = logging.getLogger("uvicorn.error")

SYSTEM_PROMPT = """You are a precise Voice Shopping Assistant NLU parser.
Extract structured user intent and shopping items from voice commands.
Return strictly valid JSON matching this schema:
{
  "intent": "ADD_ITEMS" | "ADD_ITEM" | "REMOVE_ITEM" | "UPDATE_ITEM" | "SEARCH_PRODUCT" | "SHOW_LIST" | "CLEAR_LIST" | "CONFIRM" | "CANCEL" | "UNKNOWN",
  "items": [
    {
      "item": "product name string",
      "quantity": integer (default 1),
      "unit": "unit string or null (e.g. bottles, packets, kg, pieces)",
      "size": "explicit size string or null (e.g. 650ml, 1L, 500g, 1kg)",
      "brand": "brand string or null"
    }
  ],
  "item": "single item product name string or null",
  "quantity": integer or null,
  "unit": "unit string or null",
  "size": "size string or null"
}

Rule details:
- ADD commands (single or multi-item):
  - "add milk" -> intent="ADD_ITEM", items: [{"item": "Milk", "quantity": 1}]
  - "Add 12 eggs, 1Kg butter, 3 milk packets" -> intent="ADD_ITEMS", items: [{"item": "Eggs", "quantity": 12, "unit": "pieces"}, {"item": "Butter", "quantity": 1, "unit": "kg", "size": "1kg"}, {"item": "Milk", "quantity": 3, "unit": "packets"}]
  - "buy 2 apples, 1kg rice and 3 packets of milk" -> intent="ADD_ITEMS", items: [{"item": "Apples", "quantity": 2}, {"item": "Rice", "quantity": 1, "unit": "kg", "size": "1kg"}, {"item": "Milk", "quantity": 3, "unit": "packets"}]
  - "add 250 gram of butter" -> intent="ADD_ITEM", items: [{"item": "Butter", "quantity": 1, "unit": "g", "size": "250g"}]
- REMOVE commands: "remove milk", "delete milk", "take milk off my list"
- UPDATE commands: "change milk quantity to two", "make shampoo 650ml", "650ml", "250g"
- Standalone size utterances ("650ml", "250g"): intent="UPDATE_ITEM", size="650ml", item=null.
- Do NOT output extra text or markdown outside the JSON block.
"""

NUMBER_MAP = {
    "one": 1, "a": 1, "an": 1, "single": 1,
    "two": 2, "couple": 2, "pair": 2,
    "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10
}

UNIT_NORM = {
    "gram": "g", "grams": "g", "g": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml",
    "l": "L", "liter": "L", "liters": "L",
    "oz": "oz", "lbs": "lbs", "pound": "lbs", "pounds": "lbs",
    "packet": "packets", "packets": "packets", "pack": "packs", "packs": "packs",
    "bottle": "bottles", "bottles": "bottles", "can": "cans", "cans": "cans",
    "bag": "bags", "bags": "bags", "piece": "pieces", "pieces": "pieces"
}

SIZE_REGEX = r'\b(\d+(?:\.\d+)?)\s*(ml|milliliter|milliliters|l|liter|liters|g|gram|grams|kg|kilogram|kilograms|oz|lbs|pound|pounds)\b'

class LLMCommandService:
    def __init__(self):
        self.groq_client = None
        self.groq_auth_failed = False
        self._init_groq_client()

    def _init_groq_client(self):
        api_key = settings.GROQ_API_KEY.strip() if (settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip()) else ""
        if api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=api_key)
                self.groq_auth_failed = False
                logger.info("Initialized Groq LLM client.")
                logger.info("Groq API key configured: yes")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")
                self.groq_client = None
        else:
            self.groq_client = None
            logger.info("Groq API key configured: no")

    def test_groq_connection(self) -> Dict[str, Any]:
        """Diagnostic helper verifying Groq authentication status without logging secrets."""
        api_key = settings.GROQ_API_KEY.strip() if (settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip()) else ""
        if not api_key:
            return {
                "groq_configured": False,
                "groq_model": settings.GROQ_MODEL,
                "groq_authenticated": False,
                "detail": "GROQ_API_KEY is not set in environment variables."
            }

        try:
            if not self.groq_client:
                from groq import Groq
                self.groq_client = Groq(api_key=api_key)

            # Test connection with a lightweight call
            response = self.groq_client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2
            )
            self.groq_auth_failed = False
            return {
                "groq_configured": True,
                "groq_model": settings.GROQ_MODEL,
                "groq_authenticated": True,
                "detail": "Groq authentication verified successfully."
            }
        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "Invalid API Key" in err_msg or "Unauthorized" in err_msg:
                self.groq_auth_failed = True
                logger.error("Groq API authentication failed (401 Unauthorized). Please check your GROQ_API_KEY.")
                return {
                    "groq_configured": True,
                    "groq_model": settings.GROQ_MODEL,
                    "groq_authenticated": False,
                    "detail": "401 Unauthorized: Invalid GROQ_API_KEY provided."
                }
            return {
                "groq_configured": True,
                "groq_model": settings.GROQ_MODEL,
                "groq_authenticated": False,
                "detail": f"Groq connection error: {err_msg}"
            }

    def parse_command(self, transcript: str) -> ParsedCommand:
        text = transcript.strip().lower()
        if not text:
            return ParsedCommand(intent=IntentEnum.UNKNOWN, raw_transcript=transcript)

        # Attempt Groq LLM parsing if client configured and auth has not explicitly failed
        if self.groq_client and not getattr(self, 'groq_auth_failed', False):
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = self.groq_client.chat.completions.create(
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

                    # Normalize items array if present in JSON
                    if "items" in data and isinstance(data["items"], list):
                        for item_dict in data["items"]:
                            if isinstance(item_dict, dict) and item_dict.get("item"):
                                item_dict["item"] = item_dict["item"].strip().capitalize()

                    parsed = ParsedCommand(**data)
                    parsed.raw_transcript = transcript

                    # Single-item post-processing normalization
                    if parsed.item:
                        parsed.item = parsed.item.strip().capitalize()
                        item_as_size = re.search(SIZE_REGEX, parsed.item, flags=re.IGNORECASE)
                        if item_as_size and item_as_size.group(0).lower() == parsed.item.lower():
                            val = item_as_size.group(1)
                            raw_u = item_as_size.group(2).lower()
                            parsed.size = f"{val}{UNIT_NORM.get(raw_u, raw_u)}"
                            parsed.item = None
                            parsed.intent = IntentEnum.UPDATE_ITEM

                    # Handle standalone size where LLM returned item as null or size
                    size_match_groq = re.search(SIZE_REGEX, text, flags=re.IGNORECASE)
                    _action_kw = r'\b(?:add|include|buy|i need|put|get|want|at|remove|delete|drop|erase|change|update|make|set|take)\b'
                    _has_action = bool(re.search(_action_kw, text, flags=re.IGNORECASE))
                    if size_match_groq and not _has_action and len(text.split()) <= 2:
                        parsed.intent = IntentEnum.UPDATE_ITEM
                        parsed.size = f"{size_match_groq.group(1)}{UNIT_NORM.get(size_match_groq.group(2).lower(), size_match_groq.group(2))}"
                        if parsed.item and re.search(SIZE_REGEX, parsed.item, flags=re.IGNORECASE):
                            parsed.item = None

                    # Synchronize items array and single-item fields for 100% backward compatibility
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
                        from app.schemas.command import CommandItem
                        parsed.items = [CommandItem(
                            item=parsed.item,
                            product_query=parsed.item,
                            quantity=parsed.quantity,
                            unit=parsed.unit,
                            size=parsed.size,
                            brand=parsed.brand
                        )]

                    # If transcript starts with an ADD keyword (e.g. "at 250g butter", "add 650ml shampoo")
                    if re.match(r'^\s*(?:add|include|buy|i need|put|get|want|at)\b', text, flags=re.IGNORECASE):
                        if not parsed.item and not (parsed.items and len(parsed.items) > 0):
                            return self._fallback_rule_parser(transcript)
                        if parsed.intent == IntentEnum.UPDATE_ITEM:
                            parsed.intent = IntentEnum.ADD_ITEMS if (parsed.items and len(parsed.items) > 1) else IntentEnum.ADD_ITEM

                    return parsed
                except Exception as e:
                    err_str = str(e)
                    if "401" in err_str or "Invalid API Key" in err_str or "Unauthorized" in err_str:
                        self.groq_auth_failed = True
                        logger.error("Groq API authentication error (401 Unauthorized): Invalid GROQ_API_KEY. Falling back to deterministic rule parser.")
                        break
                    elif attempt < max_retries - 1:
                        logger.warning(f"Groq API call failed (attempt {attempt+1}/{max_retries}): {e}. Retrying...")
                        time.sleep(0.5)
                    else:
                        logger.error(f"Groq API call failed after {max_retries} attempts: {e}. Falling back to deterministic rule parser.")

        return self._fallback_rule_parser(transcript)

    def _fallback_rule_parser(self, transcript: str) -> ParsedCommand:
        text = transcript.strip().lower()

        # Check for CLEAR / SHOW
        if any(kw in text for kw in ["clear list", "clear my list", "delete all items"]):
            return ParsedCommand(intent=IntentEnum.CLEAR_LIST, raw_transcript=transcript)
        if any(kw in text for kw in ["show list", "show my list", "view list", "what is on my list"]):
            return ParsedCommand(intent=IntentEnum.SHOW_LIST, raw_transcript=transcript)

        # Extract size match for single item / standalone size check
        size_match = re.search(SIZE_REGEX, text, flags=re.IGNORECASE)
        extracted_size = None
        if size_match:
            val = size_match.group(1)
            raw_u = size_match.group(2).lower()
            norm_u = UNIT_NORM.get(raw_u, raw_u)
            extracted_size = f"{val}{norm_u}"

        text_without_size = re.sub(SIZE_REGEX, '', text, flags=re.IGNORECASE) if size_match else text

        # Check for REMOVE ("remove", "delete", "take ... off", "drop", "erase")
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

        # Standalone size utterance (e.g., "650ml", "250g")
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

        # Multi-item or Single-item ADD parsing
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
        from app.schemas.command import CommandItem
        single_item = CommandItem(item=item_clean, quantity=1, size=extracted_size)
        return ParsedCommand(
            intent=IntentEnum.ADD_ITEM,
            items=[single_item],
            item=item_clean,
            quantity=1,
            size=extracted_size,
            raw_transcript=transcript
        )

    def _parse_segment_to_item(self, segment: str):
        from app.schemas.command import CommandItem
        seg_text = segment.strip().lower()
        if not seg_text:
            return None

        extracted_size = None
        size_number = None
        size_match = re.search(SIZE_REGEX, seg_text, flags=re.IGNORECASE)
        if size_match:
            size_number = size_match.group(1)
            raw_u = size_match.group(2).lower()
            extracted_size = f"{size_number}{UNIT_NORM.get(raw_u, raw_u)}"

        extracted_qty = 1
        qty_match = re.search(r'\b(\d+)\b', seg_text)
        if qty_match:
            matched_num_str = qty_match.group(1)
            if size_number and matched_num_str == size_number:
                extracted_qty = 1
            else:
                try:
                    extracted_qty = int(matched_num_str)
                except ValueError:
                    extracted_qty = 1

        text_no_size = re.sub(SIZE_REGEX, '', seg_text, flags=re.IGNORECASE) if size_match else seg_text

        unit_match = re.search(
            r'\b(packets?|packs?|bottles?|cans?|bags?|pieces?|kg|kilograms?|g|grams?|ml|liters?|l)\b',
            text_no_size,
            flags=re.IGNORECASE
        )
        extracted_unit = None
        if unit_match:
            u_raw = unit_match.group(1).lower()
            extracted_unit = UNIT_NORM.get(u_raw, u_raw)

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

        if "egg" in cleaned_item.lower() and quantity > 1 and not extracted_unit:
            extracted_unit = "pieces"

        return CommandItem(
            item=cleaned_item,
            quantity=quantity,
            unit=extracted_unit,
            size=extracted_size
        )

    def _clean_item_name(self, text: str) -> str:
        cleaned = re.sub(SIZE_REGEX, '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*(?:at|add|include|buy|i need|put|get|want|please)\b\s*', '', cleaned, flags=re.IGNORECASE)

        stop_words = [
            "on my list", "to my list", "from my list", "off my list", "off", "please",
            "quantity to", "to be", "bottles of", "packs of", "cans of", "bags of", "packets of", "packet of",
            "bottles", "packs", "cans", "bags", "packets", "packet", "pieces", "piece",
            "gram of", "grams of", "g of", "kg of", "ml of", "l of", "of",
            "a", "an", "the", "some", "my"
        ] + list(NUMBER_MAP.keys())

        for sw in stop_words:
            cleaned = re.sub(r'\b' + re.escape(sw) + r'\b', '', cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r'\b\d+\b', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned.capitalize() if cleaned else text.strip().capitalize()

llm_service = LLMCommandService()
