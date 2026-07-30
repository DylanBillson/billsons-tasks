from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionLocal


router = APIRouter(
    tags=[
        "health",
    ],
)


@router.get(
    "/health",
    include_in_schema=False,
)
def health_check() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(
            text("SELECT 1"),
        )

    return {
        "status": "healthy",
    }