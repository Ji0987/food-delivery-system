"""註冊與登入 API。"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.dependencies import DatabaseSession, ensure_restaurant_is_active
from backend.models.enums import UserRole
from backend.models.user import User
from backend.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
)
from backend.security import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(payload: UserRegister, db: DatabaseSession) -> User:
    if payload.role is UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Admin accounts cannot be created through public registration.",
        )

    normalized_email = str(payload.email).strip().lower()
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="此 Email 已被註冊",
        )

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password.get_secret_value()),
        role=payload.role,
        name=payload.name.strip(),
        phone=payload.phone,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="此 Email 已被註冊",
        ) from error
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DatabaseSession) -> TokenResponse:
    normalized_email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    password = payload.password.get_secret_value()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email 或密碼錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="帳號已停用",
        )
    ensure_restaurant_is_active(db, user)
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        user=UserResponse.model_validate(user),
    )
