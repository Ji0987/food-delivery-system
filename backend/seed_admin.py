"""Create the initial administrator account outside the public HTTP API."""

import os
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import SessionLocal, engine
from backend.models import Base
from backend.models.enums import UserRole
from backend.models.user import User
from backend.security import hash_password


class AdminSeedError(ValueError):
    """Raised when an initial administrator cannot be safely provisioned."""


def create_initial_admin(
    db: Session,
    *,
    email: str,
    password: str,
    name: str,
    phone: str | None = None,
) -> User:
    """Create an administrator with a hashed password, or return an existing admin."""

    normalized_email = email.strip().lower()
    if not normalized_email:
        raise AdminSeedError("INITIAL_ADMIN_EMAIL must not be blank.")
    if not password:
        raise AdminSeedError("INITIAL_ADMIN_PASSWORD must not be blank.")
    if not name.strip():
        raise AdminSeedError("INITIAL_ADMIN_NAME must not be blank.")

    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        if existing_user.role is UserRole.ADMIN:
            return existing_user
        raise AdminSeedError("The initial admin email is already used by another role.")

    admin = User(
        email=normalized_email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        name=name.strip(),
        phone=phone.strip() if phone else None,
    )
    db.add(admin)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise AdminSeedError("The initial admin email is already in use.") from error
    db.refresh(admin)
    return admin


def _required_environment_value(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise AdminSeedError(f"{name} must be set to seed the initial admin.")
    return value


def main() -> int:
    """Seed the initial admin from environment variables without exposing an API."""

    try:
        email = _required_environment_value("INITIAL_ADMIN_EMAIL")
        password = _required_environment_value("INITIAL_ADMIN_PASSWORD")
        name = _required_environment_value("INITIAL_ADMIN_NAME")
        phone = os.environ.get("INITIAL_ADMIN_PHONE")

        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            admin = create_initial_admin(
                db,
                email=email,
                password=password,
                name=name,
                phone=phone,
            )
    except AdminSeedError as error:
        print(f"Initial admin was not created: {error}", file=sys.stderr)
        return 1

    print(f"Initial admin is ready: {admin.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
