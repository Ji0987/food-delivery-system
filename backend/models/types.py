"""跨 SQLite/PostgreSQL 保持一致的共用欄位型別。"""

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import DateTime, Integer, Numeric
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine


MONEY_QUANTUM = Decimal("0.01")


class UTCDateTime(TypeDecorator[datetime]):
    """資料庫使用 UTC，應用層一律取得帶有 UTC 時區的 datetime。"""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        value = value.astimezone(UTC)
        if dialect.name == "sqlite":
            return value.replace(tzinfo=None)
        return value

    def process_result_value(
        self, value: datetime | None, _dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class MoneyAmount(TypeDecorator[Decimal]):
    """SQLite 存整數分、PostgreSQL 存 NUMERIC，應用層一律回傳 Decimal。"""

    impl = Numeric(10, 2, asdecimal=True)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Integer())
        return dialect.type_descriptor(Numeric(10, 2, asdecimal=True))

    def process_bind_param(
        self, value: Decimal | int | str | None, dialect: Dialect
    ) -> Decimal | int | None:
        if value is None:
            return None
        amount = Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        if dialect.name == "sqlite":
            return int(amount * 100)
        return amount

    def process_result_value(
        self, value: Decimal | int | None, dialect: Dialect
    ) -> Decimal | None:
        if value is None:
            return None
        if dialect.name == "sqlite":
            return (Decimal(value) / 100).quantize(MONEY_QUANTUM)
        return Decimal(value).quantize(MONEY_QUANTUM)
