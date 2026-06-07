from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from .database import engine, Base
from .auth import model as auth_model  # noqa: F401 - registers User with Base
from .athletes import model as athletes_model  # noqa: F401 - registers Athlete/Analysis with Base
from .auth.router import router as auth_router
from .users.controller import router as users_router
from .athletes.router import router as athletes_router
from .exceptions import register_exception_handlers
from .rate_limiting import limiter, rate_limit_custom_handler
from .logging import setup_logging

# Initialize logging
setup_logging()

app = FastAPI(
    title="Backend Auth Service",
    description="Capstone project backend authentication service",
    version="1.0.0",
    docs_url="/docs"
)

# Create database tables on startup
Base.metadata.create_all(bind=engine)

# Allow the React dev server to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:19006", "http://localhost:8081"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

media_dir = Path("media").resolve()
media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

# Set up rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_custom_handler)

# Register exception handlers
register_exception_handlers(app)

# Include Routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(athletes_router)

@app.get("/health")
@limiter.limit("5/minute")
def health_check(request: Request):
    return {"status": "ok"}
