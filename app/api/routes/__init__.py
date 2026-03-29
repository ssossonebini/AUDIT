from fastapi import APIRouter

from app.api.routes import audit, fss, fss_case, pcaob, esma, kasb, audit_news

router = APIRouter()
router.include_router(audit.router,       prefix="/audit",       tags=["audit"])
router.include_router(fss.router,         prefix="/fss",         tags=["fss"])
router.include_router(fss_case.router,    prefix="/fss-case",    tags=["fss-case"])
router.include_router(pcaob.router,       prefix="/pcaob",       tags=["pcaob"])
router.include_router(esma.router,        prefix="/esma",        tags=["esma"])
router.include_router(kasb.router,        prefix="/kasb",        tags=["kasb"])
router.include_router(audit_news.router,  prefix="/audit-news",  tags=["audit-news"])
