import uuid
from datetime import datetime, date, time
from sqlalchemy import String, Boolean, Integer, Date, Time, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def uid() -> str: return uuid.uuid4().hex

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    shield_used_month: Mapped[str | None] = mapped_column(String(7), nullable=True)  # "2026-06"
    rc_app_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    habits: Mapped[list["Habit"]] = relationship(back_populates="user", cascade="all,delete")

class Habit(Base):
    __tablename__ = "habits"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    deadline: Mapped[time] = mapped_column(Time)            # daily check-in deadline (user local time)
    tz_offset_min: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0) # times the streak was killed
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped["User"] = relationship(back_populates="habits")
    checkins: Mapped[list["CheckIn"]] = relationship(back_populates="habit", cascade="all,delete")

class CheckIn(Base):
    __tablename__ = "checkins"
    __table_args__ = (UniqueConstraint("habit_id", "day", name="one_per_day"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    habit_id: Mapped[str] = mapped_column(ForeignKey("habits.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    shielded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    habit: Mapped["Habit"] = relationship(back_populates="checkins")

class Tombstone(Base):
    __tablename__ = "tombstones"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    habit_name: Mapped[str] = mapped_column(String(80))
    days_survived: Mapped[int] = mapped_column(Integer)
    died_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
