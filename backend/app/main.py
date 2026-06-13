from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from .database import Base, engine
from .routers import auth, habits, billing

Base.metadata.create_all(engine)

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app = FastAPI(title="HardMode API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router)
app.include_router(habits.router)
app.include_router(billing.router)

@app.get("/health")
def health(): return {"ok": True}
