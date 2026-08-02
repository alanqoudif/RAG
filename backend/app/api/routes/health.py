from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.logging_config import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
def health() -> dict:
    """Liveness probe: process is up. No dependency checks."""
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response, db: Session = Depends(get_db)) -> dict:
    """Readiness probe: platform database is reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.error("readiness_check_failed", dependency="database")
        response.status_code = 503
        return {"status": "not_ready", "database": "unreachable"}
    return {"status": "ready", "database": "ok"}
