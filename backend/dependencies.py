"""FastAPI 認證與角色相依性。"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.enums import UserRole
from backend.models.menu import Restaurant
from backend.models.user import User
from backend.security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_db)]


def ensure_restaurant_is_active(db: Session, user: User) -> None:
    """拒絕已被停權餐廳的登入與既有 token 操作。"""

    if user.role is not UserRole.RESTAURANT:
        return
    restaurant = db.scalar(
        select(Restaurant).where(Restaurant.owner_user_id == user.id)
    )
    if restaurant is not None and not restaurant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="餐廳已停權",
        )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DatabaseSession,
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效或已過期的登入憑證",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise credentials_error
    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isdigit():
            raise credentials_error
        user_id = int(subject)
    except (InvalidTokenError, RuntimeError) as error:
        raise credentials_error from error

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    ensure_restaurant_is_active(db, user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> Callable[[CurrentUser], User]:
    allowed_roles = set(roles)

    def dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="目前角色無權執行此操作",
            )
        return current_user

    return dependency
