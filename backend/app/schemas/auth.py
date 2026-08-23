from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class UserSignUp(BaseModel):
    email: str = Field(..., description="Customer email address")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")
    name: Optional[str] = Field("Customer", description="Customer full name")

class UserLogin(BaseModel):
    email: str = Field(..., description="Customer email address")
    password: str = Field(..., description="Password")

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
