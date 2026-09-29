from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.config import get_settings
from app.deps import DB, CurrentUser
from app.models import Device, PulseReading
from app.plans import PLANS
from app.schemas import DailySummary, ReadingOut, SummaryOut
from app.timeutil import to_naive_utc, utcnow

router = APIRouter(prefix="/readings", tags=["readings"])


def _retention_floor(user) -> datetime:
    """Oldest data a customer may view, based on their plan (basic if none)."""
    plan = PLANS.get(user.subscription.plan or "basic", PLANS["basic"])
    return utcnow() - timedelta(days=plan.retention_days)


def _check_device(db, user, device_id: int | None) -> None:
    if device_id is not None:
        device = db.get(Device, device_id)
        if device is None or device.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")


@router.get("", response_model=list[ReadingOut])
def list_readings(
    user: CurrentUser,
    db: DB,
    device_id: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=2000, ge=1, le=10000),
):
    _check_device(db, user, device_id)
    end_ = to_naive_utc(end) if end else utcnow()
    start_ = to_naive_utc(start) if start else end_ - timedelta(hours=24)
    start_ = max(start_, _retention_floor(user))

    q = select(PulseReading).where(
        PulseReading.user_id == user.id,
        PulseReading.recorded_at >= start_,
        PulseReading.recorded_at <= end_,
    )
    if device_id is not None:
        q = q.where(PulseReading.device_id == device_id)
    # Newest `limit` samples, returned oldest-first for charting.
    rows = db.scalars(q.order_by(PulseReading.recorded_at.desc()).limit(limit)).all()
    return list(reversed(rows))


@router.get("/summary", response_model=SummaryOut)
def summary(user: CurrentUser, db: DB, days: int = Query(default=7, ge=1, le=365), device_id: int | None = None):
    _check_device(db, user, device_id)
    since = max(utcnow() - timedelta(days=days), _retention_floor(user))

    # Aggregates skip poor-contact samples, which would otherwise skew min/max.
    filters = [
        PulseReading.user_id == user.id,
        PulseReading.recorded_at >= since,
        or_(PulseReading.signal_quality.is_(None), PulseReading.signal_quality >= get_settings().min_signal_quality),
    ]
    if device_id is not None:
        filters.append(PulseReading.device_id == device_id)

    day = func.date(PulseReading.recorded_at)
    rows = db.execute(
        select(
            day,
            func.count(),
            func.avg(PulseReading.bpm),
            func.min(PulseReading.bpm),
            func.max(PulseReading.bpm),
            func.avg(PulseReading.hrv_ms),
        )
        .where(*filters)
        .group_by(day)
        .order_by(day)
    ).all()

    latest = db.scalars(select(PulseReading).where(*filters).order_by(PulseReading.recorded_at.desc()).limit(1)).first()

    return SummaryOut(
        days=[
            DailySummary(
                day=d if isinstance(d, date) else date.fromisoformat(d),
                readings=n,
                avg_bpm=round(float(avg), 1),
                min_bpm=lo,
                max_bpm=hi,
                avg_hrv_ms=round(float(hrv), 1) if hrv is not None else None,
            )
            for d, n, avg, lo, hi, hrv in rows
        ],
        latest=latest,
    )
