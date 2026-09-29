import hashlib
import hmac
import json
import time

import pytest

from app.config import get_settings
from app.models import Subscription

SECRET = "whsec_test"


@pytest.fixture
def stripe_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "stripe_secret_key", "sk_test_dummy")
    monkeypatch.setattr(s, "stripe_webhook_secret", SECRET)
    monkeypatch.setattr(s, "stripe_price_basic", "price_basic")
    monkeypatch.setattr(s, "stripe_price_pro", "price_pro")


def post_event(client, event: dict, secret: str = SECRET):
    payload = json.dumps(event)
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"},
    )


def subscription_event(etype: str, status: str, price: str, user_id: int = 1) -> dict:
    return {
        "id": "evt_1",
        "object": "event",
        "type": etype,
        "data": {
            "object": {
                "id": "sub_123",
                "object": "subscription",
                "customer": "cus_123",
                "status": status,
                "cancel_at_period_end": False,
                "metadata": {"user_id": str(user_id)},
                "items": {"data": [{"price": {"id": price}, "current_period_end": int(time.time()) + 30 * 86400}]},
            }
        },
    }


def test_webhook_rejects_bad_signature(client, stripe_on):
    r = post_event(client, subscription_event("customer.subscription.created", "active", "price_pro"), secret="wrong")
    assert r.status_code == 400


def test_webhook_drives_subscription_lifecycle(client, auth, stripe_on):
    r = post_event(client, subscription_event("customer.subscription.created", "active", "price_pro"))
    assert r.status_code == 200, r.text
    with client.session_factory() as db:
        sub = db.query(Subscription).one()
        assert (sub.plan, sub.status, sub.stripe_customer_id) == ("pro", "active", "cus_123")
        assert sub.current_period_end is not None

    post_event(client, subscription_event("customer.subscription.deleted", "canceled", "price_pro"))
    me = client.get("/api/v1/auth/me", headers=auth).json()
    assert me["subscription"]["status"] == "canceled"
    assert me["subscription"]["is_active"] is False
