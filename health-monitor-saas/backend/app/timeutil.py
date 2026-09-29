from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current time as naive UTC (the storage convention for this app)."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_naive_utc(value: datetime) -> datetime:
    """Normalise an incoming datetime to naive UTC; naive input is assumed UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def as_aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
