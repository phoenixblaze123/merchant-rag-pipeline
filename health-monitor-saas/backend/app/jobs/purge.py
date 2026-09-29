"""Delete pulse readings older than each customer's plan retention window.

Run daily, e.g. ``python -m app.jobs.purge`` from cron / a scheduled container.
"""

from datetime import timedelta

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import PulseReading, Subscription
from app.plans import PLANS
from app.timeutil import utcnow


def purge_expired_readings(db) -> int:
    removed = 0
    for user_id, plan_code in db.execute(select(Subscription.user_id, Subscription.plan)).all():
        plan = PLANS.get(plan_code or "basic", PLANS["basic"])
        cutoff = utcnow() - timedelta(days=plan.retention_days)
        result = db.execute(
            delete(PulseReading).where(PulseReading.user_id == user_id, PulseReading.recorded_at < cutoff)
        )
        removed += result.rowcount or 0
    db.commit()
    return removed


if __name__ == "__main__":
    with SessionLocal() as session:
        print(f"Purged {purge_expired_readings(session)} expired readings")
