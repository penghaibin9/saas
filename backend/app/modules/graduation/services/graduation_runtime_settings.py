"""毕业设计运行时兼容安装。

- 归档预览令牌使用系统 JWT 强密钥签名；
- 安装真实文件归档证据链与批量预览/执行一致性；
- 安装选题志愿 Excel 的统一模板、预校验与确认规则；
- 安装毕业设计材料专用的业务对象下载授权链；
- 对毕业设计新旧 XLSX 导出统一做公式注入净化；
- 将“二次答辩”严格限制为唯一第二轮；
- 成绩申诉受理与成绩撤回、学生阶段回退和通知保持原子一致；
- 成果互查任务绑定具体已通过定稿、双方范围和附件证据。
"""
from __future__ import annotations

from app.core.config import settings

_INSTALLED = False


def signing_secret() -> str:
    secret = (getattr(settings, "JWT_SECRET_KEY", "") or getattr(settings, "JWT_SECRET", "") or "").strip()
    if len(secret) < 16:
        from app.core.exceptions import AppException
        raise AppException("SERVER_ERROR", "归档预览签名密钥未正确配置", http_status=503)
    return secret


def install_runtime_settings() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    cls = type(settings)
    if not hasattr(cls, "jwt_secret"):
        setattr(cls, "jwt_secret", property(lambda _self: signing_secret()))

    from app.modules.graduation.services.graduation_archive_consistency import (
        install_archive_consistency,
    )
    from app.modules.graduation.services.graduation_archive_batch_consistency import (
        install_archive_batch_consistency,
    )
    from app.modules.graduation.services.graduation_defense_round_consistency import (
        install_defense_round_consistency,
    )
    from app.modules.graduation.services.graduation_export_security import (
        install_graduation_export_security,
    )
    from app.modules.graduation.services.graduation_grade_appeal_consistency import (
        install_grade_appeal_consistency,
    )
    from app.modules.graduation.services.graduation_material_access_consistency import (
        install_material_access_consistency,
    )
    from app.modules.graduation.services.graduation_peer_consistency import (
        install_peer_consistency,
    )
    from app.modules.graduation.services.graduation_topic_import_consistency import (
        install_topic_import_consistency,
    )
    install_archive_consistency()
    install_archive_batch_consistency()
    install_material_access_consistency()
    install_topic_import_consistency()
    install_graduation_export_security()
    install_defense_round_consistency()
    install_grade_appeal_consistency()
    install_peer_consistency()
