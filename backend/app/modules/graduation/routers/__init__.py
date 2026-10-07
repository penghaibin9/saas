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
from app.modules.graduation.services.graduation_release_hardening import (
    install as install_graduation_release_hardening,
)

register_graduation_permission_extensions()
install_graduation_package9_guard()
install_graduation_mentor_subject_guard()
install_graduation_review_message_guard()


# Release hardening is intentionally installed last so legacy overlays cannot
# replace its object-scope, concurrency, evidence and pagination guards.
install_graduation_release_hardening()
