from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import DB, CurrentUser, Subscriber
from app.models import Device
from app.plans import PLANS
from app.schemas import DeviceIn, DeviceOut, DeviceWithKeyOut
from app.security import generate_device_key

router = APIRouter(prefix="/devices", tags=["devices"])


def _owned_device(db, user, device_id: int) -> Device:
    device = db.get(Device, device_id)
    if device is None or device.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return device


@router.get("", response_model=list[DeviceOut])
def list_devices(user: CurrentUser, db: DB):
    return db.scalars(select(Device).where(Device.user_id == user.id).order_by(Device.created_at)).all()


@router.post("", response_model=DeviceWithKeyOut, status_code=status.HTTP_201_CREATED)
def register_device(body: DeviceIn, user: Subscriber, db: DB):
    plan = PLANS[user.subscription.plan]
    active = db.scalar(select(func.count()).where(Device.user_id == user.id, Device.is_active))
    if active >= plan.max_devices:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"The {plan.name} plan allows {plan.max_devices} device(s). Upgrade or remove a device.",
        )
    key, prefix, key_hash = generate_device_key()
    device = Device(user_id=user.id, name=body.name, model=body.model, api_key_prefix=prefix, api_key_hash=key_hash)
    db.add(device)
    db.commit()
    return DeviceWithKeyOut(**DeviceOut.model_validate(device).model_dump(), api_key=key)


@router.post("/{device_id}/rotate-key", response_model=DeviceWithKeyOut)
def rotate_key(device_id: int, user: Subscriber, db: DB):
    device = _owned_device(db, user, device_id)
    if not device.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Device has been removed")
    key, device.api_key_prefix, device.api_key_hash = generate_device_key()
    db.commit()
    return DeviceWithKeyOut(**DeviceOut.model_validate(device).model_dump(), api_key=key)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_device(device_id: int, user: CurrentUser, db: DB):
    """Revoke the device's key. Its historical readings are kept."""
    device = _owned_device(db, user, device_id)
    device.is_active = False
    db.commit()
