"""毕业设计中心 API 路由。"""

# Alembic owns production DDL; import mirrors W7 evidence DDL into isolated pytest metadata.
from app.models import graduation_review_evidence as _w7_review_evidence  # noqa: F401
from app.modules.graduation.services.graduation_permission_extensions import (
    register_graduation_permission_extensions,
)
from app.modules.graduation.services.graduation_package9_guard import (
    install as install_graduation_package9_guard,
)
from app.modules.graduation.services.graduation_mentor_subject_guard import (
    install as install_graduation_mentor_subject_guard,
)
from app.modules.graduation.services.graduation_review_message_event_guard import (
    install as install_graduation_review_message_guard,
)

register_graduation_permission_extensions()
install_graduation_package9_guard()
install_graduation_mentor_subject_guard()
install_graduation_review_message_guard()


def _install_w7_formal_review_overlay() -> None:
    """W7 write routes prepend existing sensitive routes while preserving path/name/permission identity."""
    from app.modules.graduation.routers import graduation_sensitive_router
    from app.modules.graduation.routers import graduation_review_w7_router

    graduation_sensitive_router.router.routes[0:0] = list(graduation_review_w7_router.router.routes)


def _install_review_center_projection() -> None:
    """把 W7.3 纯读投影挂到现有敏感 Router，继承同一毕业设计安全门禁。"""
    from app.modules.graduation.routers import graduation_review_center
    from app.modules.graduation.routers import graduation_sensitive_router

    graduation_sensitive_router.router.include_router(graduation_review_center.router)


_install_w7_formal_review_overlay()
_install_review_center_projection()
