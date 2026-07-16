"""模型共用時間函式。"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
