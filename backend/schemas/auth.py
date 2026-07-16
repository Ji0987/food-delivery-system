"""認證請求與回應 schema。"""

from datetime import datetime
from pydantic import EmailStr, Field, SecretStr, field_validator

from backend.models.enums import UserRole
from backend.schemas.common import ORMModel


class UserRegister(ORMModel):
    email: EmailStr
    password: SecretStr
    role: UserRole
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("role")
    @classmethod
    def reject_admin_public_registration(cls, value: UserRole) -> UserRole:
        if value is UserRole.ADMIN:
            raise ValueError(
                "Admin accounts cannot be created through public registration."
            )
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if len(password) < 8:
            raise ValueError("密碼至少需要 8 個字元")
        if len(password.encode("utf-8")) > 72:
            raise ValueError("密碼 UTF-8 編碼後不可超過 72 bytes")
        return value


class LoginRequest(ORMModel):
    email: EmailStr
    password: SecretStr


class UserResponse(ORMModel):
    id: int
    email: EmailStr
    role: UserRole
    name: str
    phone: str | None
    is_active: bool
    created_at: datetime


class TokenResponse(ORMModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
