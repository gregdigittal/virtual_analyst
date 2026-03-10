"""Budget router package (REM-10: split from monolithic budgets.py into ≤400-line sub-routers)."""

from fastapi import APIRouter

from apps.api.app.deps import require_role, ROLES_CAN_WRITE
from apps.api.app.routers.budgets.analytics import router as analytics_router
from apps.api.app.routers.budgets.crud import router as crud_router
from apps.api.app.routers.budgets.periods import router as periods_router
from apps.api.app.routers.budgets.templates import (
    create_budget_from_template_impl,
    router as templates_router,
)

router = APIRouter(prefix="/budgets", tags=["budgets"], dependencies=[require_role(*ROLES_CAN_WRITE)])

# Order matters: static paths (/templates, /dashboard, /nl-query) before parameterized (/{budget_id})
router.include_router(templates_router)
router.include_router(analytics_router)
router.include_router(crud_router)
router.include_router(periods_router)

# Re-export for marketplace.py
__all__ = ["router", "create_budget_from_template_impl"]
