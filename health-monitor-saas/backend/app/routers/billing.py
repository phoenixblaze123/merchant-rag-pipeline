from fastapi import APIRouter, Header, Request

from app.config import get_settings
from app.deps import DB, CurrentUser
from app.plans import PLANS
from app.schemas import CheckoutIn, PlanOut, RedirectOut, SubscriptionOut
from app.services import billing

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanOut])
def list_plans():
    return [PlanOut(**{**p.__dict__, "features": list(p.features)}) for p in PLANS.values()]


@router.get("/config")
def billing_config():
    return {"mode": "stripe" if get_settings().stripe_enabled else "mock"}


@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(user: CurrentUser):
    return user.subscription


@router.post("/checkout", response_model=RedirectOut)
def checkout(body: CheckoutIn, user: CurrentUser, db: DB):
    return RedirectOut(url=billing.start_checkout(db, user, body.plan))


@router.post("/portal", response_model=RedirectOut)
def portal(user: CurrentUser):
    return RedirectOut(url=billing.open_portal(user))


@router.post("/cancel", response_model=SubscriptionOut)
def cancel(user: CurrentUser, db: DB):
    return billing.cancel(db, user)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: DB, stripe_signature: str | None = Header(default=None)):
    event_type = billing.handle_webhook(db, await request.body(), stripe_signature)
    return {"received": event_type}
