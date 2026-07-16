"""SQLAlchemy 引擎與資料庫工作階段。"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import get_settings


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _build_engine(database_url: str) -> Engine:
    normalized_url = _normalize_database_url(database_url)
    options: dict[str, object] = {"pool_pre_ping": True}

    if normalized_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in normalized_url:
            options["poolclass"] = StaticPool

    db_engine = create_engine(normalized_url, **options)

    if normalized_url.startswith("sqlite"):

        @event.listens_for(db_engine, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection: object, _connection_record: object
        ) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return db_engine


engine = _build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 資料庫相依性。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
