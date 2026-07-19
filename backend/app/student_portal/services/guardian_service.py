"""学生 PC 门户 · 家长（proxy）侧服务：验证码登录 + 只读查看被授权学生。

安全边界：
- 家长身份仅由「学生授权的 ACTIVE 绑定 + 手机号验证码」建立；令牌 userType=GUARDIAN。
- GUARDIAN 令牌被 require_staff 一并拦在老师端之外（见 app/core/security.require_staff），
  仅能访问 /portal/guardian/*。
- 全程只读；仅返回被授权学生的授权范围（visible_scopes），心理关注/家庭隐私材料/敏感明文不返回。
- 验证码只存 hash，限次限时；生产 SMS 开启时不回带明文，SMS 未开启（dev/test）回带 devCode 供联调。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.security import create_access_token
from app.core.student_lifecycle import student_stage_label
from app.db.session import db_enabled
from app.services import audit_log
from app.services.db_service import _mask_phone, _org_names, _tid
from app.services.mobile_student_service import _session
from app.services.notification import sms_service
from app.student_portal.services.parent_link_service import _phone_hash

OTP_TTL_MIN = 10
OTP_MAX_ATTEMPTS = 5
OTP_TEMPLATE = "GUARDIAN_LOGIN"


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _valid_phone(phone: str) -> bool:
    return phone.isdigit() and len(phone) == 11


def request_otp(body: dict) -> dict:
    """家长请求登录验证码。通用成功响应（不泄露手机号是否被授权）；仅在被授权时真正下发。"""
    body = body or {}
    phone = str(body.get("phone") or "").strip()
    if not _valid_phone(phone):
        raise AppException("VALIDATION_ERROR", "手机号须为 11 位数字")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持登录")
    ph = _phone_hash(phone)
    resp: dict = {"sent": True, "ttlMinutes": OTP_TTL_MIN}
    with _session() as db:
        from app.models import PortalLoginOtp, StudentParentLink
        # 跨租户按手机号 hash 解析该家长被授权的租户（hash 不可枚举）
        links = db.scalars(select(StudentParentLink).where(
            StudentParentLink.guardian_phone_hash == ph,
            StudentParentLink.link_status == "ACTIVE",
            StudentParentLink.is_deleted.is_(False))).all()
        tenants = sorted({int(x.tenant_id) for x in links})
        if not tenants:
            return resp  # 未被任何学生授权：静默返回，不发短信、不泄露
        tid = tenants[0]  # MVP：同一家长手机号通常属一所学校；多校场景后置
        code = f"{secrets.randbelow(1000000):06d}"
        otp = PortalLoginOtp(tenant_id=tid, phone_hash=ph, code_hash=_code_hash(code),
                             purpose="GUARDIAN_LOGIN",
                             expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MIN),
                             consumed=False, attempts=0)
        db.add(otp)
        db.commit()
    sr = sms_service.send_sms(tid, phone, OTP_TEMPLATE,
                              {"code": code, "ttl": str(OTP_TTL_MIN)}, biz_type="GUARDIAN_LOGIN")
    audit_log.record("PORTAL_GUARDIAN_OTP", f"phone:{_mask_phone(phone)}",
                     {"sms": sr.get("status")})
    # SMS 未开启（dev/test）回带 devCode 便于联调与自动化测试；生产开启时绝不回带
    if sr.get("status") == "SKIPPED":
        resp["devCode"] = code
    return resp


def login(body: dict) -> dict:
    """家长用手机号+验证码登录，签发 GUARDIAN 令牌。"""
    body = body or {}
    phone = str(body.get("phone") or "").strip()
    code = str(body.get("code") or "").strip()
    if not _valid_phone(phone):
        raise AppException("VALIDATION_ERROR", "手机号须为 11 位数字")
    if not (code.isdigit() and len(code) == 6):
        raise AppException("VALIDATION_ERROR", "验证码须为 6 位数字")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持登录")
    ph = _phone_hash(phone)
    with _session() as db:
        from app.models import PortalLoginOtp, StudentParentLink
        otp = db.scalars(select(PortalLoginOtp).where(
            PortalLoginOtp.phone_hash == ph, PortalLoginOtp.consumed.is_(False)
        ).order_by(PortalLoginOtp.id.desc())).first()
        if not otp or otp.expires_at < datetime.utcnow():
            raise AppException("VALIDATION_ERROR", "验证码无效或已过期，请重新获取")
        if otp.attempts >= OTP_MAX_ATTEMPTS:
            raise AppException("VALIDATION_ERROR", "验证码错误次数过多，请重新获取")
        if otp.code_hash != _code_hash(code):
            otp.attempts += 1
            db.add(otp)
            db.commit()
            raise AppException("VALIDATION_ERROR", "验证码错误")
        otp.consumed = True
        db.add(otp)
        tid = int(otp.tenant_id)
        links = db.scalars(select(StudentParentLink).where(
            StudentParentLink.tenant_id == tid,
            StudentParentLink.guardian_phone_hash == ph,
            StudentParentLink.link_status == "ACTIVE",
            StudentParentLink.is_deleted.is_(False))).all()
        db.commit()
        if not links:
            raise AppException("NO_PERMISSION", "该手机号未被任何学生授权")
        guardian_name = links[0].guardian_name
        student_count = len(links)
    token = create_access_token({
        "userId": f"guardian-{ph[:12]}", "realName": guardian_name, "userType": "GUARDIAN",
        "guardianPhoneHash": ph, "tenantId": str(tid), "tid": str(tid),
        "currentRoleCode": "GUARDIAN", "clientType": "PC"})
    audit_log.record("PORTAL_GUARDIAN_LOGIN", f"tenant:{tid}",
                     {"phone": _mask_phone(phone), "students": student_count})
    return {"accessToken": token, "guardianName": guardian_name, "studentCount": student_count}


def _require_guardian(user: dict | None) -> dict:
    u = user or {}
    if (u.get("userType") or "").strip().upper() != "GUARDIAN":
        raise AppException("NO_PERMISSION", "该接口仅家长端可用")
    return u


def list_students(user: dict) -> dict:
    """家长查看自己被授权的学生（基本身份 + 授权范围；只读、不含敏感明文）。"""
    u = _require_guardian(user)
    ph = u.get("guardianPhoneHash")
    if not ph or not db_enabled():
        return {"hasData": False, "items": []}
    with _session() as db:
        from app.models import StudentParentLink, StudentProfile
        links = db.scalars(select(StudentParentLink).where(
            StudentParentLink.tenant_id == _tid(),
            StudentParentLink.guardian_phone_hash == ph,
            StudentParentLink.link_status == "ACTIVE",
            StudentParentLink.is_deleted.is_(False)
        ).order_by(StudentParentLink.id.desc())).all()
        sids = [int(x.student_id) for x in links]
        profs: dict = {}
        if sids:
            rows = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id.in_(sids),
                StudentProfile.is_deleted.is_(False))).all()
            _org_names(db, rows)
            profs = {r.id: r for r in rows}
        items = []
        for x in links:
            p = profs.get(int(x.student_id))
            items.append({
                "linkId": str(x.id),
                "studentNo": x.student_no,
                "studentName": p.real_name if p else "",
                "college": getattr(p, "_college_name", "") if p else "",
                "major": getattr(p, "_major_name", "") if p else "",
                "className": getattr(p, "_class_name", "") if p else "",
                "stage": student_stage_label(p.current_stage) if p else "",
                "visibleScopes": x.visible_scopes or [],
            })
    return {"hasData": bool(items), "items": items}


_INTERN_STATUS = {"ONBOARD": "实习中", "PENDING": "待入职", "ENDED": "已结束", "PAUSED": "暂停"}
_DEST = {"SIGNED": "已签约", "FLEXIBLE": "灵活就业", "FURTHER": "升学", "MILITARY": "参军",
         "UNEMPLOYED": "暂未就业"}


def student_overview(user: dict, link_id) -> dict:
    """家长查看某个被授权学生的四范围只读概览。

    严格边界：仅家长本人被授权（guardian_phone_hash 匹配 + ACTIVE）+ 仅返回该链接授权的范围
    （visible_scopes）+ 全程只读汇总，不含证件号/手机明文/心理关注/家庭隐私材料明细。
    """
    from sqlalchemy import func
    u = _require_guardian(user)
    ph = u.get("guardianPhoneHash")
    if not ph or not db_enabled():
        raise AppException("NO_PERMISSION", "无权访问")
    try:
        lid = int(link_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "无效的授权 ID")
    with _session() as db:
        from app.models import (AcademicGrade, AcademicStudent, AcademicWarning, EmpStudent,
                                InternshipRecord, StudentParentLink, StudentProfile)
        link = db.scalars(select(StudentParentLink).where(
            StudentParentLink.tenant_id == _tid(), StudentParentLink.id == lid,
            StudentParentLink.guardian_phone_hash == ph,
            StudentParentLink.link_status == "ACTIVE",
            StudentParentLink.is_deleted.is_(False))).first()
        if not link:
            raise AppException("NO_PERMISSION", "未找到你被授权查看的该学生")
        scopes = set(link.visible_scopes or [])
        sid = int(link.student_id)
        p = db.get(StudentProfile, sid)
        acad = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == sid,
            AcademicStudent.is_deleted.is_(False))).first()
        out: dict = {"studentName": p.real_name if p else "", "studentNo": link.student_no, "scopes": {}}

        if "ACADEMIC_GRADE" in scopes:
            gcount = 0
            if acad:
                gcount = db.scalar(select(func.count()).select_from(AcademicGrade).where(
                    AcademicGrade.acad_student_id == acad.id,
                    AcademicGrade.record_status == "ACTIVE",
                    AcademicGrade.is_deleted.is_(False))) or 0
            out["scopes"]["ACADEMIC_GRADE"] = {
                "gpa": float(acad.gpa) if acad and acad.gpa is not None else None,
                "earnedCredits": float(acad.obtained_credits or 0) if acad else 0,
                "requiredCredits": float(acad.required_credits or 0) if acad else 0,
                "avgScore": float(acad.avg_score) if acad and acad.avg_score is not None else None,
                "courseCount": int(gcount),
            }

        if "CAMPUS_ALERT" in scopes:
            warns = []
            if acad:
                warns = db.scalars(select(AcademicWarning).where(
                    AcademicWarning.tenant_id == _tid(), AcademicWarning.acad_student_id == acad.id,
                    AcademicWarning.is_deleted.is_(False)).order_by(AcademicWarning.id.desc())).all()
            active = [w for w in warns if (w.status or "") not in ("CLOSED", "RESOLVED")]
            out["scopes"]["CAMPUS_ALERT"] = {
                "safe": len(active) == 0, "warningCount": len(active),
                "latest": active[0].reason if active else "",
            }

        if "CAREER_PROGRESS" in scopes:
            intern = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == sid,
                InternshipRecord.is_deleted.is_(False)).order_by(InternshipRecord.id.desc())).first()
            emp = db.scalars(select(EmpStudent).where(
                EmpStudent.tenant_id == _tid(), EmpStudent.student_id == sid,
                EmpStudent.is_deleted.is_(False)).order_by(EmpStudent.id.desc())).first()
            out["scopes"]["CAREER_PROGRESS"] = {
                "stage": student_stage_label(p.current_stage) if p else "",
                "internshipEnterprise": intern.enterprise_name if intern else "",
                "internshipStatus": _INTERN_STATUS.get(intern.status, intern.status) if intern else "未开始",
                "employmentCompany": emp.company_name if emp else "",
                "employmentDestination": _DEST.get(emp.destination_type, emp.destination_type) if emp else "待登记",
            }

        if "FEE_AID_STATUS" in scopes:
            # 缴费/资助明细归财务/学工，家长侧只做「有无待办」提示，不下发金额明细。
            out["scopes"]["FEE_AID_STATUS"] = {
                "hasPending": False,
                "note": "暂无待缴费用与资助待办；缴费与资助明细以学校财务 / 学工发布为准。",
            }
    return out
