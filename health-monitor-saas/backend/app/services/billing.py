"""Monthly subscription billing.

With Stripe configured, customers pay through Stripe Checkout and the
subscription state is driven by Stripe webhooks. Without Stripe keys the app
uses *mock billing* so the sample project runs end-to-end locally.
"""

from datetime import UTC, datetime, timedelta

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Subscription, User
from app.plans import PLANS
from app.timeutil import utcnow


def _price_for(plan: str) -> str:
    s = get_settings()
    price = {"basic": s.stripe_price_basic, "pro": s.stripe_price_pro}.get(plan, "")
    if not price:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"No Stripe price configured for plan '{plan}'")
    return price


def _plan_for_price(price_id: str) -> str | None:
    s = get_settings()
    return {s.stripe_price_basic: "basic", s.stripe_price_pro: "pro"}.get(price_id)


def start_checkout(db: Session, user: User, plan: str) -> str:
    if plan not in PLANS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown plan '{plan}'")
    s = get_settings()
    sub = user.subscription

    if not s.stripe_enabled:
        sub.plan = plan
        sub.status = "active"
        sub.cancel_at_period_end = False
        sub.current_period_end = utcnow() + timedelta(days=30)
        db.commit()
        return f"{s.frontend_url}/billing?checkout=success&mock=1"

    if sub.is_active and sub.stripe_subscription_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already subscribed — change plans in the billing portal")

    stripe.api_key = s.stripe_secret_key
    if not sub.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email, name=user.full_name or None, metadata={"user_id": str(user.id)})
        sub.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=sub.stripe_customer_id,
        client_reference_id=str(user.id),
        line_items=[{"price": _price_for(plan), "quantity": 1}],
        subscription_data={"metadata": {"user_id": str(user.id), "plan": plan}},
        success_url=f"{s.frontend_url}/billing?checkout=success",
        cancel_url=f"{s.frontend_url}/billing?checkout=cancelled",
    )
    return session.url


def open_portal(user: User) -> str:
    s = get_settings()
    if not s.stripe_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Billing portal is unavailable in mock billing mode")
    if not user.subscription.stripe_customer_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No billing account yet — subscribe first")
    stripe.api_key = s.stripe_secret_key
    portal = stripe.billing_portal.Session.create(
        customer=user.subscription.stripe_customer_id, return_url=f"{s.frontend_url}/billing"
    )
    return portal.url


def cancel(db: Session, user: User) -> Subscription:
    """Cancel at the end of the current billing period."""
    s = get_settings()
    sub = user.subscription
    if not sub.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No active subscription to cancel")
    if s.stripe_enabled and sub.stripe_subscription_id:
        stripe.api_key = s.stripe_secret_key
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
    sub.cancel_at_period_end = True
    db.commit()
    return sub


# ---- Webhooks -----------------------------------------------------------------

def _ts(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value, UTC).replace(tzinfo=None) if value else None


def _apply_stripe_subscription(db: Session, obj: dict) -> None:
    sub = db.scalar(select(Subscription).where(Subscription.stripe_customer_id == obj["customer"]))
    if sub is None:
        user_id = (obj.get("metadata") or {}).get("user_id")
        sub = db.scalar(select(Subscription).where(Subscription.user_id == int(user_id))) if user_id else None
    if sub is None:
        return

    items = (obj.get("items") or {}).get("data") or []
    first_item = items[0] if items else {}
    price_id = (first_item.get("price") or {}).get("id", "")

    sub.stripe_customer_id = obj["customer"]
    sub.stripe_subscription_id = obj["id"]
    sub.status = obj["status"]
    sub.plan = _plan_for_price(price_id) or (obj.get("metadata") or {}).get("plan") or sub.plan
    sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    # Newer Stripe API versions report the period on the subscription item.
    sub.current_period_end = _ts(obj.get("current_period_end") or first_item.get("current_period_end"))


def handle_webhook(db: Session, payload: bytes, signature: str | None) -> str:
    s = get_settings()
    if not s.stripe_enabled or not s.stripe_webhook_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stripe webhooks are not configured")
    try:
        event = stripe.Webhook.construct_event(payload, signature or "", s.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature") from exc

    event = event.to_dict()
    etype, obj = event["type"], event["data"]["object"]

    if etype in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        _apply_stripe_subscription(db, obj)
    elif etype == "checkout.session.completed" and obj.get("client_reference_id"):
        sub = db.scalar(select(Subscription).where(Subscription.user_id == int(obj["client_reference_id"])))
        if sub is not None:
            sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
            sub.stripe_subscription_id = obj.get("subscription") or sub.stripe_subscription_id
    elif etype == "invoice.payment_failed":
        sub = db.scalar(select(Subscription).where(Subscription.stripe_customer_id == obj.get("customer")))
        if sub is not None:
            sub.status = "past_due"

    db.commit()
    return etype
