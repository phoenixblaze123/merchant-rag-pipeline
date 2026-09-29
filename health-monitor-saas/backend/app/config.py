"""Application settings, loaded from environment variables (prefix ``HM_``)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HM_", extra="ignore")

    app_name: str = "PulseCloud Health Monitor"
    database_url: str = "sqlite:///./health_monitor.db"

    jwt_secret: str = "dev-only-insecure-secret-change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # Stripe. When ``stripe_secret_key`` is empty the app runs in "mock billing"
    # mode: checkout activates the subscription immediately, no payment taken.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_basic: str = ""
    stripe_price_pro: str = ""

    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Alerting
    alert_cooldown_minutes: int = 15
    min_signal_quality: float = 0.5

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
