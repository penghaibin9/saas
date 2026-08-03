"""兼容模块：心理敏感审计已迁入 affairs_mental_service。"""

from app.services.affairs_mental_service import _sensitive_view_audit as strict_sensitive_view_audit

def install() -> None:
    return None
