from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Habit, CheckIn, Tombstone
from ..schemas import HabitIn, HabitOut
from ..security import current_user
from ..config import FREE_HABIT_LIMIT

router = APIRouter(prefix="/habits", tags=["habits"])

def local_now(h: Habit) -> datetime:
    return datetime.utcnow() + timedelta(minutes=h.tz_offset_min)

def enforce_streak(h: Habit, db: Session) -> None:
    """Kill the streak if yesterday (local) was missed and unshielded. HardMode rule."""
    now = local_now(h)
    yesterday = (now - timedelta(days=1)).date()
    if h.streak == 0 or h.created_at + timedelta(minutes=h.tz_offset_min) > datetime.combine(yesterday, h.deadline):
        return
    hit = db.query(CheckIn).filter(CheckIn.habit_id == h.id, CheckIn.day == yesterday).first()
    if not hit:
        db.add(Tombstone(user_id=h.user_id, habit_name=h.name,
                         days_survived=h.streak, died_on=yesterday))
        h.streak = 0; h.deaths += 1; db.commit()

@router.get("", response_model=list[HabitOut])
def list_habits(user: User = Depends(current_user), db: Session = Depends(get_db)):
    month = datetime.utcnow().strftime("%Y-%m")
    shield_ok = user.is_premium and user.shield_used_month != month
    out = []
    for h in [x for x in user.habits if x.active]:
        enforce_streak(h, db)
        today = local_now(h).date()
        yesterday = today - timedelta(days=1)
        checked = db.query(CheckIn).filter(CheckIn.habit_id == h.id, CheckIn.day == today).first() is not None
        missed_yest = db.query(CheckIn).filter(CheckIn.habit_id == h.id, CheckIn.day == yesterday).first() is None
        existed = h.created_at + timedelta(minutes=h.tz_offset_min) <= datetime.combine(yesterday, h.deadline)
        out.append(HabitOut(id=h.id, name=h.name, deadline=h.deadline, streak=h.streak,
                            best_streak=h.best_streak, deaths=h.deaths, checked_today=checked,
                            shieldable=shield_ok and missed_yest and existed))
    return out

@router.post("", response_model=HabitOut, status_code=201)
def create_habit(body: HabitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = sum(1 for x in user.habits if x.active)
    if not user.is_premium and n >= FREE_HABIT_LIMIT:
        raise HTTPException(402, "Free limit reached. Go premium for unlimited habits.")
    h = Habit(user_id=user.id, name=body.name, deadline=body.deadline, tz_offset_min=body.tz_offset_min)
    db.add(h); db.commit()
    return HabitOut(id=h.id, name=h.name, deadline=h.deadline, streak=0,
                    best_streak=0, deaths=0, checked_today=False)

@router.post("/{habit_id}/checkin", response_model=HabitOut)
def checkin(habit_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    h = db.get(Habit, habit_id)
    if not h or h.user_id != user.id: raise HTTPException(404, "Not found")
    enforce_streak(h, db)
    now = local_now(h); today = now.date()
    if now.time() > h.deadline:
        raise HTTPException(409, "Deadline passed. The streak is already at risk — no late check-ins.")
    if db.query(CheckIn).filter(CheckIn.habit_id == h.id, CheckIn.day == today).first():
        raise HTTPException(409, "Already checked in today")
    db.add(CheckIn(habit_id=h.id, day=today))
    h.streak += 1; h.best_streak = max(h.best_streak, h.streak)
    db.commit()
    return HabitOut(id=h.id, name=h.name, deadline=h.deadline, streak=h.streak,
                    best_streak=h.best_streak, deaths=h.deaths, checked_today=True)

@router.post("/{habit_id}/shield", response_model=HabitOut)
def shield_yesterday(habit_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Premium: retroactively save yesterday. One per calendar month."""
    if not user.is_premium: raise HTTPException(402, "Shields are premium only")
    month = datetime.utcnow().strftime("%Y-%m")
    if user.shield_used_month == month: raise HTTPException(409, "Shield already used this month")
    h = db.get(Habit, habit_id)
    if not h or h.user_id != user.id: raise HTTPException(404, "Not found")
    yesterday = (local_now(h) - timedelta(days=1)).date()
    if db.query(CheckIn).filter(CheckIn.habit_id == h.id, CheckIn.day == yesterday).first():
        raise HTTPException(409, "Yesterday was not missed")
    db.add(CheckIn(habit_id=h.id, day=yesterday, shielded=True))
    h.streak += 1
    user.shield_used_month = month
    db.commit()
    return HabitOut(id=h.id, name=h.name, deadline=h.deadline, streak=h.streak,
                    best_streak=h.best_streak, deaths=h.deaths, checked_today=False)

@router.delete("/{habit_id}", status_code=204)
def retire(habit_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    h = db.get(Habit, habit_id)
    if not h or h.user_id != user.id: raise HTTPException(404, "Not found")
    h.active = False; db.commit()


@router.get("/graveyard")
def graveyard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(Tombstone).filter(Tombstone.user_id == user.id)
            .order_by(Tombstone.died_on.desc()).limit(100).all())
    return [{"id": t.id, "habit_name": t.habit_name,
             "days_survived": t.days_survived, "died_on": str(t.died_on)} for t in rows]


@router.get("/{habit_id}/history")
def history(habit_id: str, days: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    h = db.get(Habit, habit_id)
    if not h or h.user_id != user.id: raise HTTPException(404, "Not found")
    today = local_now(h).date()
    start = today - timedelta(days=days - 1)
    rows = db.query(CheckIn).filter(CheckIn.habit_id == h.id, CheckIn.day >= start).all()
    done = {str(r.day): ("shielded" if r.shielded else "done") for r in rows}
    created_local = (h.created_at + timedelta(minutes=h.tz_offset_min)).date()
    out, d = [], start
    while d <= today:
        st = done.get(str(d)) or ("none" if d < created_local else "pending" if d == today else "missed")
        out.append({"day": str(d), "status": st}); d += timedelta(days=1)
    scored = [x for x in out if x["status"] in ("done", "shielded", "missed")]
    rate = round(100 * sum(1 for x in scored if x["status"] != "missed") / max(1, len(scored)))
    return {"habit": h.name, "days": out, "rate": rate,
            "streak": h.streak, "best": h.best_streak, "deaths": h.deaths}
