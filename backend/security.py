"""密碼雜湊與 JWT 工具。"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from jwt import InvalidTokenError

from backend.config import get_settings
from backend.models.enums import UserRole


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("密碼 UTF-8 編碼後不可超過 72 bytes")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, role: UserRole) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.require_jwt_secret(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.require_jwt_secret(),
        algorithms=[settings.jwt_algorithm],
    )


__all__ = [
    "InvalidTokenError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
