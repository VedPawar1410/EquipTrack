from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator


def _assume_utc(value: datetime) -> datetime:
    """Timestamp columns are TIMESTAMPTZ. A client sending "2026-11-16" (no timezone) gets UTC midnight."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# Use for every timestamp the API accepts, so naive values never reach a TIMESTAMPTZ column.
UTCDatetime = Annotated[datetime, AfterValidator(_assume_utc)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
