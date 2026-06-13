"""RevenueCat webhook: flips users premium on purchase, off on expiration.
Set the same secret in RC dashboard (Authorization header) and in .env."""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..security import current_user
from ..config import RC_WEBHOOK_SECRET

router = APIRouter(prefix="/billing", tags=["billing"])

PREMIUM_ON = {"INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION", "PRODUCT_CHANGE"}
PREMIUM_OFF = {"EXPIRATION", "CANCELLATION_EXPIRED", "BILLING_ISSUE_EXPIRED"}

@router.post("/link")
def link_rc_user(rc_app_user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.rc_app_user_id = rc_app_user_id; db.commit()
    return {"linked": True}

@router.post("/revenuecat-webhook")
async def rc_webhook(req: Request, authorization: str = Header(""), db: Session = Depends(get_db)):
    if RC_WEBHOOK_SECRET and authorization != f"Bearer {RC_WEBHOOK_SECRET}":
        raise HTTPException(401, "Bad webhook auth")
    event = (await req.json()).get("event", {})
    rc_id, etype = event.get("app_user_id"), event.get("type", "")
    user = db.query(User).filter(User.rc_app_user_id == rc_id).first()
    if not user: return {"ignored": True}
    if etype in PREMIUM_ON: user.is_premium = True
    elif etype in PREMIUM_OFF: user.is_premium = False
    db.commit()
    return {"ok": True}
