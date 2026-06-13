from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import RegisterIn, TokenOut, MeOut
from ..security import hash_pw, verify_pw, make_token, current_user
from ..config import FREE_HABIT_LIMIT
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    u = User(email=body.email.lower(), password_hash=hash_pw(body.password))
    db.add(u); db.commit()
    return TokenOut(access_token=make_token(u.id))

@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == form.username.lower()).first()
    if not u or not verify_pw(form.password, u.password_hash):
        raise HTTPException(401, "Bad credentials")
    return TokenOut(access_token=make_token(u.id))

@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user)):
    month = datetime.utcnow().strftime("%Y-%m")
    return MeOut(
        email=user.email, is_premium=user.is_premium,
        habit_limit=10_000 if user.is_premium else FREE_HABIT_LIMIT,
        shield_available=user.is_premium and user.shield_used_month != month,
    )



@router.delete("/me", status_code=204)
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(user); db.commit()
