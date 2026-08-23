from pydantic import BaseModel
from typing import List, Optional

class SuggestionItem(BaseModel):
    product_id: Optional[str] = None
    product_name: str
    suggested_size: Optional[str] = None
    reason: str
    frequency_text: str
    co_occurrence_count: int
    total_lists_analyzed: int

class SuggestionResponse(BaseModel):
    suggestions: List[SuggestionItem] = []
