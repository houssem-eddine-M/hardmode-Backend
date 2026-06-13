from datetime import time, date
from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    deadline: time
    tz_offset_min: int = Field(ge=-840, le=840, default=0)

class HabitOut(BaseModel):
    id: str; name: str; deadline: time; streak: int
    best_streak: int; deaths: int; checked_today: bool; shieldable: bool = False
    class Config: from_attributes = True

class MeOut(BaseModel):
    email: EmailStr; is_premium: bool; habit_limit: int; shield_available: bool
