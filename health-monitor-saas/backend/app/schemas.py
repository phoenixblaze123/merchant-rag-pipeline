from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.timeutil import as_aware_utc

# Timestamps are stored as naive UTC; expose them with an explicit UTC offset.
UTCDatetime = Annotated[datetime, AfterValidator(as_aware_utc)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth / users ---------------------------------------------------------

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SubscriptionOut(ORMModel):
    plan: str | None
    status: str
    is_active: bool
    cancel_at_period_end: bool
    current_period_end: UTCDatetime | None


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    hr_low_threshold: int
    hr_high_threshold: int
    created_at: UTCDatetime
    subscription: SubscriptionOut | None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    hr_low_threshold: int | None = Field(default=None, ge=25, le=100)
    hr_high_threshold: int | None = Field(default=None, ge=80, le=220)



# ---- Billing ----------------------------------------------------------------

class PlanOut(BaseModel):
    code: str
    name: str
    price_cents: int
    max_devices: int
    retention_days: int
    features: list[str]


class CheckoutIn(BaseModel):
    plan: str


class RedirectOut(BaseModel):
    url: str


# ---- Devices ----------------------------------------------------------------

class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    model: str = Field(default="generic-wrist-ppg", max_length=100)


class DeviceOut(ORMModel):
    id: int
    name: str
    model: str
    api_key_prefix: str
    is_active: bool
    created_at: UTCDatetime
    last_seen_at: UTCDatetime | None


class DeviceWithKeyOut(DeviceOut):
    api_key: str = Field(description="Shown only once. Configure it on the device.")


# ---- Ingest -----------------------------------------------------------------

class PulseSampleIn(BaseModel):
    recorded_at: datetime
    bpm: int = Field(ge=20, le=250)
    hrv_ms: float | None = Field(default=None, ge=0, le=500)
    signal_quality: float | None = Field(default=None, ge=0, le=1)
    irregular_rhythm: bool = False


class IngestIn(BaseModel):
    readings: list[PulseSampleIn] = Field(min_length=1, max_length=1000)


class IngestOut(BaseModel):
    accepted: int
    duplicates: int
    alerts_created: int


# ---- Readings / analytics ---------------------------------------------------

class ReadingOut(ORMModel):
    id: int
    device_id: int
    recorded_at: UTCDatetime
    bpm: int
    hrv_ms: float | None
    signal_quality: float | None
    irregular_rhythm: bool


class DailySummary(BaseModel):
    day: date
    readings: int
    avg_bpm: float
    min_bpm: int
    max_bpm: int
    avg_hrv_ms: float | None


class SummaryOut(BaseModel):
    days: list[DailySummary]
    latest: ReadingOut | None


class AlertOut(ORMModel):
    id: int
    device_id: int
    kind: str
    bpm: int
    message: str
    reading_time: UTCDatetime
    created_at: UTCDatetime
    acknowledged: bool
