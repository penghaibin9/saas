"""学工历史导入 Dry-Run 终态修正。

必须安装在 affairs_history_import_guard 之后。任何错行都保持 DRY_RUN_FAILED，
绝不通过“丢弃错行、只确认正确行”把部分成功伪装成整批通过。
"""
from __future__ import annotations

from app.core.exceptions import AppException

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_history_import_guard as guard
    from app.services import domain_import_service as service

    previous = service.dry_run

    def dry_run(domain, rows, *, namespace=None, user=None):
        if domain != "student-affairs":
            return previous(domain, rows, namespace=namespace, user=user)
        # 直接调用原始学工预检函数，绕开上一层“成功批次持久化”包装。
        result = service._dry_run_student_affairs(rows, namespace=namespace, user=user)
        batch_no = result["batchNo"]
        memory = service._MEM.pop(batch_no, None)
        if not memory:
            raise AppException("SERVER_ERROR", "Dry-Run批次生成失败")
        if int(result.get("errorRows") or 0) > 0:
            memory["status"] = "DRY_RUN_FAILED"
            memory["rows"] = []  # 错行批次不得保留任何可确认写入数据
            guard._persist(batch_no, memory)
            return result
        normalized = guard._normalize_rows(memory.get("rows") or [])
        guard._validate_references(normalized)
        memory["rows"] = normalized
        memory["status"] = "DRY_RUN_PASSED"
        guard._persist(batch_no, memory)
        result.update({
            "status": "DRY_RUN_PASSED", "okRows": len(normalized),
            "errorRows": 0, "errors": [],
        })
        return result

    service.dry_run = dry_run
    _INSTALLED = True
