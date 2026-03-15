"""AFS router package (REM-12: split from monolithic afs.py)."""

from fastapi import APIRouter

from apps.api.app.deps import ROLES_CAN_WRITE, require_role
from apps.api.app.routers.afs.analytics import router as analytics_router
from apps.api.app.routers.afs.consolidation import router as consolidation_router
from apps.api.app.routers.afs.disclosure import router as disclosure_router
from apps.api.app.routers.afs.engagements import router as engagements_router
from apps.api.app.routers.afs.frameworks import router as frameworks_router
from apps.api.app.routers.afs.ingestion import router as ingestion_router
from apps.api.app.routers.afs.outputs import router as outputs_router
from apps.api.app.routers.afs.review import router as review_router
from apps.api.app.routers.afs.tax import router as tax_router

router = APIRouter(prefix="/afs", tags=["afs"], dependencies=[require_role(*ROLES_CAN_WRITE)])

# Static paths before parameterized paths
router.include_router(frameworks_router)
router.include_router(engagements_router)
router.include_router(ingestion_router)
router.include_router(disclosure_router)
router.include_router(review_router)
router.include_router(tax_router)
router.include_router(consolidation_router)
router.include_router(outputs_router)
router.include_router(analytics_router)
