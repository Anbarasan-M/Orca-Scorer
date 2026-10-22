from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes import api_router
from app.core.config import settings
from app.db.session import get_db

app = FastAPI(
    title=settings.APP_NAME,
    description="Ball-by-ball cricket scoring.",
    version="0.1.0",
)

# Enable CORS for frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"message": "Welcome to Orca Scorer", "docs": "/docs"}


@app.get("/health/db", tags=["meta"])
def db_health(db: Session = Depends(get_db)) -> dict[str, object]:
    """Confirms the API can actually reach PostgreSQL."""
    try:
        version = db.execute(text("SELECT version()")).scalar_one()
        tables = db.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalar_one()
    except SQLAlchemyError as exc:
        return {"database": "unreachable", "error": str(exc.__cause__ or exc)}
    return {"database": "ok", "server": version, "public_tables": tables}
