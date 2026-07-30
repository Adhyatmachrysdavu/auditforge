"""Skema Pydantic untuk autentikasi & pengguna."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool


class UserCreate(BaseModel):
    email: str
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: str  # nama peran: admin | auditor | analyst
