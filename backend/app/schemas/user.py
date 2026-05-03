from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: str
    username: str = Field(..., min_length=2)
    password: str
    display_name: Optional[str] = None
    team: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return (v or "").strip().lower()


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    display_name: Optional[str] = None
    role: str
    team: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    total_points: Optional[int] = None
    total_solves: Optional[int] = None
    current_streak: Optional[int] = None
    rank: Optional[int] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    team: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def _role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("operator", "admin"):
            raise ValueError("role must be 'operator' or 'admin'")
        return v

    @field_validator("team")
    @classmethod
    def _team(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("red", "blue"):
            raise ValueError("team must be 'red' or 'blue'")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
