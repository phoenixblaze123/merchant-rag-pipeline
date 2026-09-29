"""Turns incoming pulse samples into customer alerts."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Alert, Device, PulseReading, User
from app.plans import PLANS


def _classify(reading: PulseReading, user: User, rhythm_alerts: bool) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if reading.irregular_rhythm and rhythm_alerts:
        found.append(("irregular_rhythm", f"Irregular pulse rhythm detected ({reading.bpm} bpm)"))
    if reading.bpm > user.hr_high_threshold:
        found.append(("high_hr", f"Heart rate {reading.bpm} bpm is above your {user.hr_high_threshold} bpm limit"))
    elif reading.bpm < user.hr_low_threshold:
        found.append(("low_hr", f"Heart rate {reading.bpm} bpm is below your {user.hr_low_threshold} bpm limit"))
    return found


def evaluate_readings(db: Session, device: Device, user: User, readings: list[PulseReading]) -> int:
    """Create alerts for out-of-range samples, with a per-kind cooldown.

    Samples with poor sensor contact (low ``signal_quality``) are ignored —
    wrist PPG is noisy when the band is loose or the wearer is moving.
    """
    s = get_settings()
    cooldown = timedelta(minutes=s.alert_cooldown_minutes)
    plan = PLANS.get(user.subscription.plan or "basic", PLANS["basic"])

    last_seen: dict[str, datetime] = dict(
        db.execute(
            select(Alert.kind, func.max(Alert.reading_time))
            .where(Alert.device_id == device.id)
            .group_by(Alert.kind)
        ).all()
    )

    created = 0
    for r in sorted(readings, key=lambda r: r.recorded_at):
        if r.signal_quality is not None and r.signal_quality < s.min_signal_quality:
            continue
        for kind, message in _classify(r, user, plan.irregular_rhythm_alerts):
            prev = last_seen.get(kind)
            if prev is not None and abs(r.recorded_at - prev) < cooldown:
                continue
            db.add(
                Alert(
                    user_id=user.id,
                    device_id=device.id,
                    kind=kind,
                    bpm=r.bpm,
                    message=message,
                    reading_time=r.recorded_at,
                )
            )
            last_seen[kind] = r.recorded_at
            created += 1
    return created
