from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from enum import Enum

class IntentEnum(str, Enum):
    ADD_ITEM = "ADD_ITEM"
    ADD_ITEMS = "ADD_ITEMS"
    REMOVE_ITEM = "REMOVE_ITEM"
    UPDATE_ITEM = "UPDATE_ITEM"
    SEARCH_PRODUCT = "SEARCH_PRODUCT"
    SHOW_LIST = "SHOW_LIST"
    CLEAR_LIST = "CLEAR_LIST"
    CONFIRM = "CONFIRM"
    CANCEL = "CANCEL"
    UNKNOWN = "UNKNOWN"

class CommandItem(BaseModel):
    item: Optional[str] = Field(None, description="Item or product name extracted from transcript")
    product_query: Optional[str] = Field(None, description="Product query extracted from transcript")
    quantity: Optional[int] = Field(1, description="Numerical quantity requested")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g. bottles, packs, kg, packets)")
    size: Optional[str] = Field(None, description="Explicit product size requested (e.g. 650ml, 1L, 1kg)")
    brand: Optional[str] = Field(None, description="Specific brand requested")

    def get_name(self) -> str:
        return self.product_query or self.item or ""

class ParsedCommand(BaseModel):
    intent: IntentEnum = Field(..., description="Normalized intent extracted from natural language command")
    items: List[CommandItem] = Field(default_factory=list, description="List of items extracted from transcript")
    item: Optional[str] = Field(None, description="Single item or product name extracted from transcript")
    quantity: Optional[int] = Field(1, description="Numerical quantity requested")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g. bottles, packs, kg)")
    size: Optional[str] = Field(None, description="Explicit product size requested (e.g. 650ml, 1L)")
    brand: Optional[str] = Field(None, description="Specific brand requested")
    raw_transcript: Optional[str] = Field(None, description="Original user text transcript")

    def get_items(self) -> List[CommandItem]:
        """Normalizes both single-item and multi-item commands into a list of CommandItem objects."""
        if self.items and len(self.items) > 0:
            for it in self.items:
                if not it.item and it.product_query:
                    it.item = it.product_query
            return self.items
        if self.item:
            return [CommandItem(
                item=self.item,
                product_query=self.item,
                quantity=self.quantity if self.quantity is not None else 1,
                unit=self.unit,
                size=self.size,
                brand=self.brand
            )]
        return []

class CommandRequest(BaseModel):
    transcript: str = Field(..., description="User voice speech transcript")
    user_id: Optional[str] = Field("default-user-id", description="Target user ID")

class CommandResponse(BaseModel):
    success: bool
    message: str
    parsed: ParsedCommand
    action_taken: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
