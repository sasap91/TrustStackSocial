"""
Health check endpoints
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models import HealthResponse
from ..dependencies import get_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health_check(db: Session = Depends(get_database)):
    """Health check endpoint"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        timestamp=datetime.utcnow()
    )
