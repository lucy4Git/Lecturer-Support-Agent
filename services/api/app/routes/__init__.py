from .assignments import router as assignments_router
from .auth import router as auth_router
from .bulk_uploads import router as bulk_uploads_router
from .conversations import router as conversations_router
from .completion import router as completion_router
from .documents import router as documents_router
from .department_operations import router as department_operations_router
from .external_access import router as external_access_router
from .health import router as health_router
from .organisation import router as organisation_router
from .operations import router as operations_router
from .reviews import router as reviews_router
from .teaching_contexts import router as teaching_contexts_router
from .teaching_outputs import router as teaching_outputs_router
from .users import router as users_router
from .workspace import router as workspace_router

__all__ = [
    "assignments_router",
    "auth_router",
    "bulk_uploads_router",
    "conversations_router",
    "completion_router",
    "documents_router",
    "department_operations_router",
    "external_access_router",
    "health_router",
    "organisation_router",
    "operations_router",
    "reviews_router",
    "teaching_contexts_router",
    "teaching_outputs_router",
    "users_router",
    "workspace_router",
    "ai_governance_router",
    "settings_router",
    "audit_router",
    "analytics_router",
]

from .analytics import analytics_router, audit_router, settings_router, ai_governance_router
