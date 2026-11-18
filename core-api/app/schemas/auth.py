from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(examples=["admin@redridge.example"])
    # max_length stops someone sending a huge password to burn CPU in Argon2.
    password: str = Field(min_length=1, max_length=128, examples=["DemoPass123!"])


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
