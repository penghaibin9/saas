"""毕业设计关键审计上下文修复。

- ``db-123`` 等账号 ID 解析为稳定数据库用户 ID；
- 补齐 actor/context/role/permission/request/scope；
- 根据业务对象反查 batch_id，避免同一学生跨届后审计混批。
"""
from __future__ import annotations

import re

from sqlalchemy import event, text

from app.core.context import (
    get_current_permission_code,
    get_current_user_ctx,
    get_request_meta,
    get_trace_id,
)
from app.models import GraduationAuditTrail

_INSTALLED = False


def _db_id(value) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    text_value = str(value).strip()
    if text_value.isdigit():
        return int(text_value)
    match = re.fullmatch(r"(?:db[-_:])?(\d+)", text_value, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


_DIRECT_BATCH = {"BATCH": "t_gd_batch", "TOPIC_ROUND": "t_gd_topic_round", "TOPIC": "t_gd_topic"}
_STUDENT_TABLES = {
    "STUDENT": "t_gd_student",
    "TASKBOOK": "t_gd_task_book",
    "PROPOSAL": "t_gd_proposal",
    "FINAL": "t_gd_final",
    "PLAGIARISM": "t_gd_plagiarism",
    "REVIEW": "t_gd_review",
    "DEFENSE_SCORE": "t_gd_defense_score",
    "GRADE": "t_gd_grade",
    "RISK": "t_gd_risk",
    "ARCHIVE": "t_gd_archive_record",
    "GRADE_APPEAL": "t_gd_grade_appeal",
    "PEER": "t_gd_peer_review",
    "TOPIC_CHANGE": "t_gd_topic_change_request",
    "GUIDANCE": "t_gd_guidance",
    "MIDTERM": "t_gd_midterm",
}


def _infer_batch_id(connection, target: GraduationAuditTrail) -> int | None:
    biz_id = _db_id(target.biz_id)
    if biz_id is None:
        return None
    biz_type = str(target.biz_type or "").upper()
    if biz_type in _DIRECT_BATCH:
        table = _DIRECT_BATCH[biz_type]
        column = "id" if biz_type == "BATCH" else "batch_id"
        if biz_type == "BATCH":
            return biz_id
        return connection.execute(text(
            f"SELECT {column} FROM {table} WHERE id=:id AND tenant_id=:tenant LIMIT 1"
        ), {"id": biz_id, "tenant": target.tenant_id}).scalar()
    table = _STUDENT_TABLES.get(biz_type)
    if not table:
        return None
    if biz_type == "STUDENT":
        return connection.execute(text(
            "SELECT batch_id FROM t_gd_student WHERE id=:id AND tenant_id=:tenant LIMIT 1"
        ), {"id": biz_id, "tenant": target.tenant_id}).scalar()
    return connection.execute(text(
        f"SELECT s.batch_id FROM {table} b "
        "JOIN t_gd_student s ON s.id=b.gd_student_id AND s.tenant_id=b.tenant_id "
        "WHERE b.id=:id AND b.tenant_id=:tenant LIMIT 1"
    ), {"id": biz_id, "tenant": target.tenant_id}).scalar()


def _before_insert(_mapper, connection, target: GraduationAuditTrail) -> None:
    user = get_current_user_ctx() or {}
    request = get_request_meta() or {}
    if target.actor_user_id is None:
        target.actor_user_id = _db_id(
            user.get("userId") or user.get("id") or user.get("dbUserId") or user.get("accountId")
        )
    if not target.actor_context_id:
        value = user.get("contextId") or user.get("currentContextId")
        target.actor_context_id = str(value) if value not in (None, "") else None
    if not target.actor_name_snapshot:
        target.actor_name_snapshot = user.get("realName") or user.get("loginName")
    if not target.operator:
        target.operator = target.actor_name_snapshot or "系统任务"
    if not target.role_code:
        target.role_code = user.get("currentRoleCode") or user.get("userType") or "SYSTEM"
    if not target.role_name:
        target.role_name = user.get("currentRoleName") or target.role_code
    if not target.permission_code:
        target.permission_code = get_current_permission_code()
    if not target.request_id:
        trace = get_trace_id()
        target.request_id = trace if trace and trace != "-" else None
    if not target.request_path:
        target.request_path = request.get("path")
    if not target.client_ip:
        target.client_ip = request.get("ip") or request.get("clientIp")
    if target.data_scope_snapshot is None:
        target.data_scope_snapshot = {
            "dataScope": user.get("dataScope"),
            "collegeId": user.get("collegeId"),
            "majorId": user.get("majorId"),
            "orgId": user.get("orgId"),
        }
    if target.batch_id is None:
        target.batch_id = _infer_batch_id(connection, target)


def install_audit_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    event.listen(GraduationAuditTrail, "before_insert", _before_insert)
