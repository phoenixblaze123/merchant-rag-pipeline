from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Device, User
from app.security import decode_access_token, hash_device_key

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_subscriber(user: CurrentUser) -> User:
    if not (user.subscription and user.subscription.is_active):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "An active subscription is required")
    return user


Subscriber = Annotated[User, Depends(require_subscriber)]


def get_device_from_key(db: DB, x_device_key: Annotated[str, Header()]) -> Device:
    device = db.scalar(select(Device).where(Device.api_key_hash == hash_device_key(x_device_key)))
    if device is None or not device.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown or revoked device key")
    return device


AuthedDevice = Annotated[Device, Depends(get_device_from_key)]
