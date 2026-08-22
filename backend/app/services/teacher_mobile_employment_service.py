"""Teacher Miniapp V3 T7 employment recommendation and destination-verification authority.

Recommendation is a first-class EmpRecommendation fact.  Destination verification keeps the
existing EmpStudent.verify_status as the single state projection, but a VERIFY command only
succeeds when an APPROVED employment material has a ready public FileBinding.  Legacy file_name
text is display-only and never counts as evidence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import EmpAuditTrail, EmpFollowup, EmpJob, EmpMaterial, EmpStudent, StudentProfile
from app.models.employment_recommendation import EmpRecommendation
from app.models.file import FileBinding, FileObject
from app.modules.employment.services import employment_destination_verification_service as verification_authority
from app.modules.employment.services import employment_material_evidence_service as evidence_authority
from app.modules.employment.services import employment_runtime_service as runtime
from app.modules.employment.services import employment_service as base
from app.services import mobile_teacher_service as teacher_guard
from app.services.db_service import _iso, _tid, session
from app.services.file_access_service import register_file_resolver
from app.services.file_business_binding_service import bind_file_to_business
from app.services.message_identity import resolve_message_user_id

# TP-E05：正式证据口径的单一权威在 employment_material_evidence_service，
# 这里只做别名，保证教师 PC 与教师小程序永远用同一套状态集合与判定函数。
_READY_FILE_STATUS = evidence_authority.READY_FILE_STATUS
_READY_SCAN_STATUS = evidence_authority.READY_SCAN_STATUS
_FORMAL_BIZ_TYPE = "EMPLOYMENT_MATERIAL"
_FORMAL_MODULE = evidence_authority.FORMAL_MODULE

assert _FORMAL_BIZ_TYPE == evidence_authority.FORMAL_BIZ_TYPE


def _ready_file(file_obj: FileObject | None) -> bool:
    return evidence_authority.is_ready_file(file_obj)


def _scope_emp(db, emp_id: Any, user: dict, *, lock: bool = False) -> tuple[EmpStudent, StudentProfile | None]:
    try:
        eid = int(emp_id)
    except (TypeError, ValueError):
        raise not_found("就业记录不存在或不在当前数据范围内")
    stmt = select(EmpStudent).where(
        EmpStudent.id == eid,
        EmpStudent.tenant_id == _tid(),
        EmpStudent.is_deleted.is_(False),
        EmpStudent.record_status == "ACTIVE",
    )
    if lock:
        stmt = stmt.with_for_update()
    emp = db.scalar(stmt)
    if not emp:
        raise not_found("就业记录不存在或不在当前数据范围内")

    scope = teacher_guard.resolve_teacher_scope(user)
    if scope.get("mode") == "ADMIN_TENANT":
        profile = None
        if emp.student_id:
            profile = db.scalar(select(StudentProfile).where(
                StudentProfile.id == int(emp.student_id),
                StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
            ))
        return emp, profile

    profile = None
    if emp.student_id:
        profile = db.scalar(select(StudentProfile).where(
            StudentProfile.id == int(emp.student_id),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ))
        if profile and teacher_guard.can_teacher_view_student(user, profile, scope=scope, db=db):
            return emp, profile
        # Bound rows must be decided by the stable current StudentProfile only.  Falling back to
        # employment snapshot class/college facts would let a former counselor retain access after
        # a transfer.  Missing/deleted profiles therefore fail closed as well.
        raise no_permission("该就业学生不在你的数据范围内")

    # Only truly unbound legacy rows may use frozen employment snapshot facts.
    if teacher_guard.scope_match_row(
        scope,
        student_no=emp.student_no,
        class_name=emp.class_name,
        college_name=emp.college_name,
    ):
        return emp, profile
    raise no_permission("该就业学生不在你的数据范围内")


def _assert_version(row, expected: Any, label: str) -> None:
    try:
        actual_expected = int(expected)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{label} expectedVersion 非法")
    if int(row.version or 0) != actual_expected:
        raise AppException(
            "DATA_CONFLICT",
            f"{label}已被其他用户修改，请刷新后重试",
            http_status=409,
            details={"expectedVersion": actual_expected, "serverVersion": int(row.version or 0)},
        )


def _group(row: dict) -> str:
    destination = str(row.get("destinationType") or "").upper()
    verify = str(row.get("verifyStatus") or "").upper()
    if destination == "UNEMPLOYED":
        return "unemployed"
    if verify in {"PENDING_VERIFY", "RETURNED"}:
        return "verify"
    if verify == "VERIFIED":
        return "done"
    return "following"


def overview(user: dict) -> dict[str, Any]:
    teacher_guard._require_teacher(user)
    rows, total = runtime.list_students(1, 100, user=user)
    jobs, _ = base.list_jobs(1, 100, status="OPEN")
    ids = [int(row["id"]) for row in rows if str(row.get("id") or "").isdigit()]
    versions: dict[int, int] = {}
    if ids:
        with session() as db:
            versions = {
                int(row.id): int(row.version or 0)
                for row in db.scalars(select(EmpStudent).where(
                    EmpStudent.tenant_id == _tid(), EmpStudent.id.in_(ids),
                    EmpStudent.is_deleted.is_(False),
                )).all()
            }
    enriched = []
    for row in rows:
        rid = int(row["id"]) if str(row.get("id") or "").isdigit() else 0
        group = _group(row)
        can_recommend = bool(group == "unemployed" and jobs)
        can_verify = bool(group == "verify")
        enriched.append({
            **row,
            "group": group,
            "version": versions.get(rid, 0),
            "allowedActions": {
                "follow": True,
                "recommend": can_recommend,
                "verify": can_verify,
            },
            "disabledReason": {
                "recommend": "" if can_recommend else ("暂无可推荐在招岗位" if group == "unemployed" else "当前学生无需岗位推荐"),
                "verify": "" if can_verify else ("学生尚未登记可核验去向" if group == "unemployed" else "当前状态无需核验"),
            },
        })
    stats = {
        "total": total,
        "unemployed": sum(1 for row in enriched if row["group"] == "unemployed"),
        "pendingVerification": sum(1 for row in enriched if row["group"] == "verify"),
        "verified": sum(1 for row in enriched if row["group"] == "done"),
        "pageSampled": len(enriched),
    }
    return {
        "hasData": bool(enriched),
        "stats": stats,
        "tabs": [
            {"key": "unemployed", "label": "未就业"},
            {"key": "following", "label": "跟进中"},
            {"key": "verify", "label": "待核验"},
            {"key": "done", "label": "已落实"},
        ],
        "list": enriched,
        "jobs": jobs,
        "truncated": total > len(enriched),
    }


def create_recommendation(user: dict, emp_student_id: Any, body: dict) -> dict:
    teacher_guard._require_teacher(user)
    reason = str(body.get("reason") or "").strip()
    note = str(body.get("note") or "").strip() or None
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "推荐理由不少于 5 字")
    try:
        job_id = int(body.get("jobId"))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "jobId 非法")

    with session() as db:
        emp, _profile = _scope_emp(db, emp_student_id, user, lock=True)
        _assert_version(emp, body.get("expectedStudentVersion"), "就业学生")
        job = db.scalar(select(EmpJob).where(
            EmpJob.id == job_id,
            EmpJob.tenant_id == _tid(),
            EmpJob.is_deleted.is_(False),
        ).with_for_update())
        if not job or str(job.status or "").upper() != "OPEN":
            raise AppException("DATA_CONFLICT", "岗位已关闭或不存在，请刷新岗位列表", http_status=409)
        duplicate = db.scalar(select(EmpRecommendation).where(
            EmpRecommendation.tenant_id == _tid(),
            EmpRecommendation.emp_student_id == emp.id,
            EmpRecommendation.job_id == job.id,
            EmpRecommendation.status == "RECOMMENDED",
            EmpRecommendation.is_deleted.is_(False),
        ).order_by(EmpRecommendation.id.desc()).limit(1))
        if duplicate:
            raise AppException(
                "DATA_CONFLICT",
                "该学生已存在同岗位有效推荐记录",
                http_status=409,
                details={"recommendationId": str(duplicate.id)},
            )
        now = datetime.utcnow()
        actor_id = resolve_message_user_id(user) or None
        actor_name = str(user.get("realName") or "").strip() or None
        recommendation = EmpRecommendation(
            tenant_id=_tid(),
            emp_student_id=emp.id,
            student_profile_id=emp.student_id,
            job_id=job.id,
            teacher_user_id=actor_id,
            teacher_name=actor_name,
            company_name_snapshot=job.company_name,
            job_title_snapshot=job.title,
            reason=reason,
            note=note,
            status="RECOMMENDED",
            outcome="PENDING",
            recommended_at=now,
        )
        db.add(recommendation)
        db.flush()

        # Follow-up is deliberately secondary.  Recommendation identity is the master fact above.
        db.add(EmpFollowup(
            tenant_id=_tid(),
            emp_student_id=emp.id,
            follow_time=now,
            way="RECOMMEND",
            content=f"推荐岗位：{job.company_name or ''} {job.title}".strip(),
            result=reason,
            next_plan=note,
            operator=actor_name,
            status="OPEN",
        ))
        emp.last_follow_up_time = now
        emp.follow_up_count = int(emp.follow_up_count or 0) + 1
        emp.version = int(emp.version or 0) + 1
        base._audit(
            db,
            "RECOMMENDATION",
            recommendation.id,
            "推荐岗位",
            f"empStudentId={emp.id};jobId={job.id};reason={reason}",
        )
        db.commit()
        return {
            "recommendationId": str(recommendation.id),
            "status": recommendation.status,
            "outcome": recommendation.outcome,
            "studentVersion": int(emp.version or 0),
        }


def _material_evidence(db, emp: EmpStudent) -> tuple[list[dict], int]:
    """本模块的教师小程序材料投影。

    TP-E05：「什么算正式证据」的判定已抽到
    `employment_material_evidence_service`，教师 PC 与教师小程序共用同一权威，
    本函数只负责小程序自己的 DTO 形状——不再各持一份判定规则，否则 PC 与
    小程序对同一份材料可能给出不同结论。
    """
    materials = db.scalars(select(EmpMaterial).where(
        EmpMaterial.tenant_id == _tid(),
        EmpMaterial.emp_student_id == emp.id,
        EmpMaterial.is_deleted.is_(False),
    ).order_by(EmpMaterial.id.desc())).all()
    facts = evidence_authority.resolve_evidence(db, [row.id for row in materials])

    result = []
    approved_ready = 0
    for material in materials:
        fact = facts.get(int(material.id)) or {}
        binding = fact.get("binding")
        file_obj = fact.get("file")
        formal = bool(fact.get("formal"))
        if formal and str(material.status or "").upper() == "APPROVED":
            approved_ready += 1
        result.append({
            "id": str(material.id),
            "materialType": material.material_type,
            "fileName": (file_obj.file_name if formal and file_obj else material.file_name) or "",
            "legacyFileNameOnly": bool(material.file_name and not formal),
            "status": material.status,
            "version": int(material.version or 0),
            "formalEvidence": formal,
            "file": ({
                "fileId": str(file_obj.id),
                "fileName": file_obj.file_name,
                "scanStatus": file_obj.scan_status,
                "bindingId": str(binding.id),
                "bizType": _FORMAL_BIZ_TYPE,
            } if formal and file_obj and binding else None),
        })
    return result, approved_ready


def get_verification(user: dict, emp_student_id: Any) -> dict:
    teacher_guard._require_teacher(user)
    with session() as db:
        emp, _profile = _scope_emp(db, emp_student_id, user)
        materials, approved_ready = _material_evidence(db, emp)
        recommendations = db.scalars(select(EmpRecommendation).where(
            EmpRecommendation.tenant_id == _tid(),
            EmpRecommendation.emp_student_id == emp.id,
            EmpRecommendation.is_deleted.is_(False),
        ).order_by(EmpRecommendation.id.desc()).limit(20)).all()
        history = db.scalars(select(EmpAuditTrail).where(
            EmpAuditTrail.tenant_id == _tid(),
            EmpAuditTrail.biz_type == "VERIFICATION",
            EmpAuditTrail.biz_id == str(emp.id),
        ).order_by(EmpAuditTrail.id.desc()).limit(30)).all()
        verify_status = str(emp.verify_status or "PENDING_VERIFY").upper()
        can_verify = bool(
            str(emp.destination_type or "").upper() != "UNEMPLOYED"
            and verify_status != "VERIFIED"
            and approved_ready > 0
        )
        return {
            "verificationId": str(emp.id),
            "version": int(emp.version or 0),
            "status": verify_status,
            "student": {
                "id": str(emp.id),
                "studentId": str(emp.student_id or ""),
                "name": emp.name,
                "studentNo": emp.student_no or "",
                "className": emp.class_name or "",
            },
            "destination": {
                "type": emp.destination_type,
                "companyName": emp.company_name or "",
                "jobTitle": emp.job_title or "",
                "signDate": emp.sign_date or "",
            },
            "materials": materials,
            "approvedFormalEvidenceCount": approved_ready,
            "recommendations": [
                {
                    "recommendationId": str(row.id),
                    "jobId": str(row.job_id),
                    "jobTitle": row.job_title_snapshot,
                    "companyName": row.company_name_snapshot or "",
                    "reason": row.reason,
                    "status": row.status,
                    "outcome": row.outcome,
                    "recommendedAt": _iso(row.recommended_at) or "",
                }
                for row in recommendations
            ],
            "history": [
                {
                    "id": str(row.id),
                    "action": row.action,
                    "detail": row.detail or "",
                    "operator": row.operator or "",
                    "before": row.before_val or "",
                    "after": row.after_val or "",
                    "occurredAt": _iso(row.occurred_at) or "",
                }
                for row in history
            ],
            "allowedActions": {
                "verify": can_verify,
                "return": verify_status != "RETURNED",
            },
            "disabledReason": (
                "" if can_verify else
                "缺少已审核通过且完成 FileBinding/安全扫描的正式就业材料"
            ),
        }


def bind_material_evidence(user: dict, material_id: Any, body: dict) -> dict:
    teacher_guard._require_teacher(user)
    try:
        mid = int(material_id)
    except (TypeError, ValueError):
        raise not_found("就业材料不存在或不在当前数据范围内")
    file_id = str(body.get("fileId") or "").strip()
    if not file_id.isdigit():
        raise AppException("VALIDATION_ERROR", "fileId 非法")

    with session() as db:
        material = db.scalar(select(EmpMaterial).where(
            EmpMaterial.id == mid,
            EmpMaterial.tenant_id == _tid(),
            EmpMaterial.is_deleted.is_(False),
        ).with_for_update())
        if not material:
            raise not_found("就业材料不存在或不在当前数据范围内")
        _assert_version(material, body.get("expectedVersion"), "就业材料")
        emp, profile = _scope_emp(db, material.emp_student_id, user, lock=True)
        if not profile or not emp.student_id:
            raise AppException("DATA_CONFLICT", "历史就业材料未绑定稳定学生主档，禁止建立正式文件证据", http_status=409)
        existing = db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == _tid(),
            FileBinding.biz_type == _FORMAL_BIZ_TYPE,
            FileBinding.biz_id == str(material.id),
            FileBinding.module_code == _FORMAL_MODULE,
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ).with_for_update())
        if existing:
            if int(existing.file_id) == int(file_id):
                return {
                    "materialId": str(material.id),
                    "fileId": file_id,
                    "bindingId": str(existing.id),
                    "version": int(material.version or 0),
                }
            raise AppException("DATA_CONFLICT", "该就业材料已绑定正式证据文件，不允许静默替换", http_status=409)

        binding = bind_file_to_business(
            db,
            file_id=file_id,
            biz_type=_FORMAL_BIZ_TYPE,
            biz_id=material.id,
            actor=user,
            subject_type="STUDENT",
            subject_id=str(profile.id),
            relation_type="BUSINESS_EVIDENCE",
            module_code=_FORMAL_MODULE,
            student_id=profile.id,
            college_id=profile.college_id,
            class_id=profile.class_id,
            scope={
                "employmentStudentId": str(emp.id),
                "studentId": str(profile.id),
                "studentNo": str(profile.student_no or ""),
                "materialId": str(material.id),
                "materialType": str(material.material_type or ""),
            },
        )
        file_obj = db.scalar(select(FileObject).where(
            FileObject.id == int(file_id),
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        ))
        if file_obj:
            material.file_name = file_obj.file_name
        material.version = int(material.version or 0) + 1
        base._audit(db, "MATERIAL", material.id, "绑定正式就业材料证据", f"fileId={file_id}")
        db.commit()
        return {
            "materialId": str(material.id),
            "fileId": file_id,
            "bindingId": str(binding.id),
            "version": int(material.version or 0),
        }


def review_verification(user: dict, verification_id: Any, body: dict) -> dict:
    teacher_guard._require_teacher(user)
    action = str(body.get("action") or "").upper()
    comment = str(body.get("comment") or "").strip()
    if action not in {"VERIFY", "RETURN"}:
        raise AppException("VALIDATION_ERROR", "非法核验动作")
    if action == "RETURN" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "退回必须填写不少于 5 字的可执行补正意见")

    with session() as db:
        # 授权用本端（移动教师端）自己的范围权威；核验的业务规则交给共享 domain
        # 命令，保证 PC 与小程序对"什么证据足以支撑 VERIFIED"给出同一答案。
        emp, _profile = _scope_emp(db, verification_id, user, lock=True)
        emp.verify_status = str(emp.verify_status or "PENDING_VERIFY").upper()
        result = verification_authority.review(
            db, emp,
            action=action,
            comment=comment,
            expected_version=body.get("expectedVersion"),
        )
        db.commit()
        return result


@register_file_resolver(_FORMAL_BIZ_TYPE)
def employment_material_file_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """Public file-center ACL for formal employment material evidence.

    File admins do not bypass employment object scope.  The ACTIVE binding must resolve to one
    current employment material and the binding's STUDENT subject must match the stable profile.
    """
    if db is None:
        return False
    active = [
        item for item in bindings
        if not item.is_deleted
        and item.status == "ACTIVE"
        and item.is_current
        and str(item.biz_type or "").upper() == _FORMAL_BIZ_TYPE
        and str(item.module_code or "").upper() == _FORMAL_MODULE
    ]
    for binding in active:
        raw_mid = str(binding.biz_id or "").strip()
        if not raw_mid.isdigit():
            continue
        material = db.scalar(select(EmpMaterial).where(
            EmpMaterial.id == int(raw_mid),
            EmpMaterial.tenant_id == int(file_obj.tenant_id),
            EmpMaterial.is_deleted.is_(False),
        ))
        if not material:
            continue
        emp = db.scalar(select(EmpStudent).where(
            EmpStudent.id == material.emp_student_id,
            EmpStudent.tenant_id == int(file_obj.tenant_id),
            EmpStudent.is_deleted.is_(False),
            EmpStudent.record_status == "ACTIVE",
        ))
        if not emp or not emp.student_id:
            continue
        profile = db.scalar(select(StudentProfile).where(
            StudentProfile.id == int(emp.student_id),
            StudentProfile.tenant_id == int(file_obj.tenant_id),
            StudentProfile.is_deleted.is_(False),
        ))
        if not profile:
            continue
        if str(binding.subject_type or "").upper() != "STUDENT" or str(binding.subject_id or "") != str(profile.id):
            continue
        user_type = str((user or {}).get("userType") or "").upper()
        if user_type == "STUDENT":
            values = {
                str((user or {}).get("studentId") or "").strip(),
                str((user or {}).get("studentNo") or "").strip(),
            }
            if str(profile.id) in values or str(profile.student_no or "") in values:
                return True
            continue
        try:
            if teacher_guard.can_teacher_view_student(user or {}, profile, db=db):
                return True
        except Exception:
            continue
    return False
