from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

app = FastAPI(title=settings.APP_NAME)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to Orca Scorer"}


@app.get("/health/db")
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
