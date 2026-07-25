"""学生 PC 门户 · 家长授权代理（proxy）服务。

学生本人侧：绑定家长、查看已授权家长、撤销授权。全程严格「本人」数据范围。
家长侧（登录 + 只读查看）在后续增量单独实现（family_service），本文件只负责学生侧授权管理。

复用底座：mobile_student_service 的 _require_student/_session/resolve_student；db_service 的
_tid/_iso/_mask_phone；统一 AppException 错误码；audit_log 审计。不新造身份/会话/脱敏逻辑。
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import db_enabled
from app.services import audit_log
from app.services.db_service import _iso, _mask_phone, _tid
from app.services.mobile_student_service import (_require_student, _session,
                                                 resolve_student)

# 家长可见范围（与产品决策 D-07 一致；心理关注/家庭隐私材料明细不在其列）
VISIBLE_SCOPES = {"ACADEMIC_GRADE", "FEE_AID_STATUS", "CAMPUS_ALERT", "CAREER_PROGRESS"}
RELATIONS = {"FATHER", "MOTHER", "GUARDIAN", "PARENT", "OTHER"}


def _phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.strip().encode("utf-8")).hexdigest()


def _norm_scopes(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    return sorted({s for s in raw if s in VISIBLE_SCOPES})


def bind_guardian(user: dict, body: dict) -> dict:
    """学生本人授权一个家长（proxy 只读）。"""
    u = _require_student(user)
    body = body or {}
    name = str(body.get("guardianName") or "").strip()
    phone = str(body.get("guardianPhone") or "").strip()
    relation = str(body.get("relation") or "PARENT").strip().upper()
    scopes = _norm_scopes(body.get("visibleScopes"))
    if not name:
        raise AppException("VALIDATION_ERROR", "家长姓名必填")
    if not (phone.isdigit() and len(phone) == 11):
        raise AppException("VALIDATION_ERROR", "家长手机号须为 11 位数字")
    if relation not in RELATIONS:
        relation = "OTHER"
    if not scopes:
        raise AppException("VALIDATION_ERROR", "至少授权一项可见范围")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实提交")
    ph = _phone_hash(phone)
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案，无法授权")
        from app.models import StudentParentLink
        dup = db.scalars(select(StudentParentLink).where(
            StudentParentLink.tenant_id == _tid(),
            StudentParentLink.student_id == stu.id,
            StudentParentLink.guardian_phone_hash == ph,
            StudentParentLink.link_status == "ACTIVE",
            StudentParentLink.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该家长手机号已授权，请勿重复添加")
        from app.core.field_crypto import encrypt_field
        row = StudentParentLink(
            tenant_id=_tid(), student_id=stu.id, student_no=stu.student_no,
            guardian_name=name, relation=relation,
            guardian_phone_encrypted=encrypt_field(phone), guardian_phone_hash=ph,
            visible_scopes=scopes, link_status="ACTIVE")
        db.add(row)
        db.flush()
        rid = row.id
        db.commit()
    audit_log.record("PORTAL_PARENT_BIND", f"student-parent-link:{rid}",
                     {"studentNo": u.get("studentNo"), "guardianPhone": _mask_phone(phone),
                      "scopes": scopes})
    return {"id": str(rid), "status": "ACTIVE", "message": "家长授权成功"}


def list_guardians(user: dict) -> dict:
    """学生本人查看自己授权的家长列表（手机号脱敏）。"""
    u = _require_student(user)
    if not db_enabled():
        return {"hasData": False, "items": []}
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return {"hasData": False, "items": []}
        from app.models import StudentParentLink
        rows = db.scalars(select(StudentParentLink).where(
            StudentParentLink.tenant_id == _tid(),
            StudentParentLink.student_id == stu.id,
            StudentParentLink.is_deleted.is_(False)
        ).order_by(StudentParentLink.id.desc())).all()
        items = [{
            "id": str(r.id), "guardianName": r.guardian_name, "relation": r.relation,
            "guardianPhone": _mask_phone(r.guardian_phone_encrypted),
            "visibleScopes": r.visible_scopes or [], "status": r.link_status,
            "createdAt": _iso(r.created_at),
        } for r in rows]
    return {"hasData": bool(items), "items": items}


def revoke_guardian(user: dict, link_id) -> dict:
    """学生本人撤销某条家长授权（软撤销 link_status=REVOKED，保留行做审计）。"""
    u = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持")
    try:
        lid = int(link_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "无效的授权 ID")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        from app.models import StudentParentLink
        row = db.scalars(select(StudentParentLink).where(
            StudentParentLink.tenant_id == _tid(),
            StudentParentLink.id == lid,
            StudentParentLink.is_deleted.is_(False))).first()
        if not row:
            raise AppException("DATA_NOT_FOUND", "授权不存在")
        # 数据范围：只能撤销自己的授权，越权 403002
        if row.student_id != stu.id:
            raise AppException("NO_DATA_SCOPE", "不能操作他人的家长授权")
        if row.link_status == "REVOKED":
            return {"id": str(row.id), "status": "REVOKED", "message": "已撤销"}
        row.link_status = "REVOKED"
        db.add(row)
        db.commit()
    audit_log.record("PORTAL_PARENT_REVOKE", f"student-parent-link:{lid}",
                     {"studentNo": u.get("studentNo")})
    return {"id": str(lid), "status": "REVOKED", "message": "已撤销该家长的查看授权"}
