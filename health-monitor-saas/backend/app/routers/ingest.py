"""Endpoint called by wrist devices (or their companion phone app/gateway)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import DB, AuthedDevice
from app.models import PulseReading, User
from app.schemas import IngestIn, IngestOut
from app.services.alerts import evaluate_readings
from app.timeutil import to_naive_utc, utcnow

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestOut)
def ingest(body: IngestIn, device: AuthedDevice, db: DB):
    user = db.get(User, device.user_id)
    if not (user.subscription and user.subscription.is_active):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Subscription inactive; data not accepted")

    # Devices retry on flaky connections, so ingest is idempotent per (device, recorded_at).
    samples = {to_naive_utc(s.recorded_at): s for s in body.readings}
    existing = set(
        db.scalars(
            select(PulseReading.recorded_at).where(
                PulseReading.device_id == device.id,
                PulseReading.recorded_at.in_(list(samples)),
            )
        )
    )

    new_rows = [
        PulseReading(
            device_id=device.id,
            user_id=user.id,
            recorded_at=ts,
            bpm=s.bpm,
            hrv_ms=s.hrv_ms,
            signal_quality=s.signal_quality,
            irregular_rhythm=s.irregular_rhythm,
        )
        for ts, s in samples.items()
        if ts not in existing
    ]
    db.add_all(new_rows)
    alerts = evaluate_readings(db, device, user, new_rows)
    device.last_seen_at = utcnow()
    db.commit()

    return IngestOut(
        accepted=len(new_rows),
        duplicates=len(body.readings) - len(new_rows),
        alerts_created=alerts,
    )
