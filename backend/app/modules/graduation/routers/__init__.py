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
    """Prepend W7 writes once while preserving the frozen path/name/permission identity."""
    from app.modules.graduation.routers import graduation_sensitive_router
    from app.modules.graduation.routers import graduation_review_w7_router

    target = graduation_sensitive_router.router
    marker = "_w7_formal_review_overlay_installed"
    if getattr(target, marker, False):
        return
    target.routes[0:0] = list(graduation_review_w7_router.router.routes)
    setattr(target, marker, True)


def _install_review_center_projection() -> None:
    """Attach the W7.3 read projection once under the existing sensitive graduation gate."""
    from app.modules.graduation.routers import graduation_review_center
    from app.modules.graduation.routers import graduation_sensitive_router

    target = graduation_sensitive_router.router
    marker = "_w73_review_center_projection_installed"
    if getattr(target, marker, False):
        return
    target.include_router(graduation_review_center.router)
    setattr(target, marker, True)


_install_w7_formal_review_overlay()
_install_review_center_projection()
