from fastapi import APIRouter

from app.api.routes import audit, fss, pcaob, sec

router = APIRouter()
router.include_router(audit.router, prefix="/audit", tags=["audit"])
router.include_router(fss.router, prefix="/fss", tags=["fss"])
router.include_router(pcaob.router, prefix="/pcaob", tags=["pcaob"])
router.include_router(sec.router, prefix="/sec", tags=["sec"])
