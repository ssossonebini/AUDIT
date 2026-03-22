from fastapi import APIRouter

from app.api.routes import audit, fss

router = APIRouter()
router.include_router(audit.router, prefix="/audit", tags=["audit"])
router.include_router(fss.router, prefix="/fss", tags=["fss"])
