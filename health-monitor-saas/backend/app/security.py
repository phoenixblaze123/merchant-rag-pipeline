import hashlib
import secrets
from datetime import timedelta

import bcrypt
import jwt

from app.config import get_settings
from app.timeutil import utcnow

DEVICE_KEY_PREFIX = "hm_"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    s = get_settings()
    now = utcnow()
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def generate_device_key() -> tuple[str, str, str]:
    """Return ``(plaintext_key, display_prefix, sha256_hash)``.

    Only the hash is stored; the plaintext is shown to the customer once.
    """
    key = DEVICE_KEY_PREFIX + secrets.token_urlsafe(32)
    return key, key[:10], hash_device_key(key)


def hash_device_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
