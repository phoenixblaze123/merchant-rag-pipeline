from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import DB, CurrentUser
from app.models import Alert
from app.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(user: CurrentUser, db: DB, unacknowledged_only: bool = False, limit: int = Query(50, ge=1, le=500)):
    q = select(Alert).where(Alert.user_id == user.id)
    if unacknowledged_only:
        q = q.where(Alert.acknowledged.is_(False))
    return db.scalars(q.order_by(Alert.reading_time.desc()).limit(limit)).all()


@router.post("/{alert_id}/ack", response_model=AlertOut)
def acknowledge(alert_id: int, user: CurrentUser, db: DB):
    alert = db.get(Alert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    alert.acknowledged = True
    db.commit()
    return alert
