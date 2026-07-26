"""学生 PC 门户 · PC 重活公共底座：电子签署（可插拔 provider）+ 打印/导出留痕。

各业务模块（毕设任务书确认、三方协议、奖助承诺书等）统一调用本底座：
- sign：可靠留痕（内容 SHA-256 哈希快照 + 时间戳 + 签署人 + 审计 PORTAL_SIGN），provider 可插拔；
  法律级（法大大/e签宝/CA + 实名 + 可信时间戳）待甲方采购密钥后接入，接口已预留不实做。
- print_log / export_log：打印/导出留痕（审计 PORTAL_PRINT/PORTAL_EXPORT + 返回水印）。
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from app.core.exceptions import AppException
from app.db.session import db_enabled
from app.services import audit_log
from app.services.db_service import _iso, _tid
from app.services.mobile_student_service import (_require_student, _session,
                                                 resolve_student)

# 已实现的电子签 provider。法律级 provider 需采购持牌平台密钥后接入（见施工包 D-05）。
IMPLEMENTED_SIGN_PROVIDERS = {"reliable_log"}


def _resolve_provider(name) -> str:
    p = str(name or "reliable_log").strip() or "reliable_log"
    if p not in IMPLEMENTED_SIGN_PROVIDERS:
        raise AppException("VALIDATION_ERROR",
                           "暂不支持该电子签 provider：法律级电子签名需甲方采购持牌平台（法大大/e签宝/CA）密钥后接入")
    return p


def _watermark(user: dict) -> str:
    return user.get("realName") or user.get("studentNo") or "本人"


def sign(user: dict, body: dict) -> dict:
    """对某业务内容电子签署（默认可靠留痕）。内容哈希快照 + 时间戳 + 审计。"""
    u = _require_student(user)
    body = body or {}
    biz_type = str(body.get("bizType") or "").strip()
    biz_id = str(body.get("bizId") or "").strip()
    content = str(body.get("content") or "")
    confirm = bool(body.get("confirm"))
    provider = _resolve_provider(body.get("provider"))
    if not biz_type:
        raise AppException("VALIDATION_ERROR", "bizType 必填")
    if not content:
        raise AppException("VALIDATION_ERROR", "签署内容为空")
    if not confirm:
        raise AppException("VALIDATION_ERROR", "请先勾选确认后再签署")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实签署")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案，无法签署")
        from app.models import PortalSignRecord
        signed_at = datetime.utcnow()
        rec = PortalSignRecord(tenant_id=_tid(), student_id=stu.id, biz_type=biz_type,
                               biz_id=biz_id or None, content_hash=content_hash,
                               provider=provider, signer_name=stu.real_name, signed_at=signed_at)
        db.add(rec)
        db.flush()
        rid = rec.id
        db.commit()
    audit_log.record("PORTAL_SIGN", f"{biz_type}:{biz_id}",
                     {"studentNo": u.get("studentNo"), "contentHash": content_hash,
                      "provider": provider})
    return {"signId": str(rid), "contentHash": content_hash, "provider": provider,
            "signerName": u.get("realName") or "", "signedAt": _iso(signed_at),
            # reliable_log 为可靠留痕，非法律级电子签名；法律效力待采购持牌平台
            "legalEffect": provider != "reliable_log",
            "confirmationType": "EVIDENCE_LOG"}


def create_sign_record_in_session(db, user: dict, body: dict, student) -> dict:
    """供需要业务原子性的流程复用；只 flush，由调用方统一提交或回滚。"""
    body = body or {}
    biz_type = str(body.get("bizType") or "").strip()
    biz_id = str(body.get("bizId") or "").strip()
    content = str(body.get("content") or "")
    if not biz_type or not content or not bool(body.get("confirm")):
        raise AppException("VALIDATION_ERROR", "签署类型、内容与确认状态必须完整")
    provider = _resolve_provider(body.get("provider"))
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    from app.models import PortalSignRecord
    signed_at = datetime.utcnow()
    rec = PortalSignRecord(
        tenant_id=_tid(), student_id=student.id, biz_type=biz_type,
        biz_id=biz_id or None, content_hash=content_hash, provider=provider,
        signer_name=student.real_name, signed_at=signed_at)
    db.add(rec)
    db.flush()
    return {"signId": str(rec.id), "contentHash": content_hash, "provider": provider,
            "signerName": user.get("realName") or "", "signedAt": _iso(signed_at),
            "legalEffect": provider != "reliable_log",
            "confirmationType": "EVIDENCE_LOG"}


def print_log(user: dict, body: dict) -> dict:
    """打印留痕（审计 PORTAL_PRINT + 水印）。"""
    u = _require_student(user)
    body = body or {}
    biz_type = str(body.get("bizType") or "").strip()
    biz_id = str(body.get("bizId") or "").strip()
    doc_name = str(body.get("docName") or "").strip()
    if not biz_type:
        raise AppException("VALIDATION_ERROR", "bizType 必填")
    audit_log.record("PORTAL_PRINT", f"{biz_type}:{biz_id}",
                     {"studentNo": u.get("studentNo"), "docName": doc_name})
    return {"watermark": _watermark(u), "loggedAt": _iso(datetime.utcnow())}


def export_log(user: dict, body: dict) -> dict:
    """导出留痕（审计 PORTAL_EXPORT + 水印）。"""
    u = _require_student(user)
    body = body or {}
    biz_type = str(body.get("bizType") or "").strip()
    biz_id = str(body.get("bizId") or "").strip()
    doc_name = str(body.get("docName") or "").strip()
    if not biz_type:
        raise AppException("VALIDATION_ERROR", "bizType 必填")
    audit_log.record("PORTAL_EXPORT", f"{biz_type}:{biz_id}",
                     {"studentNo": u.get("studentNo"), "docName": doc_name})
    return {"watermark": _watermark(u), "loggedAt": _iso(datetime.utcnow())}
