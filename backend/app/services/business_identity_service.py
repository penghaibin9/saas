"""SYS-07：自动业务身份（任课、毕设导师、评阅、答辩专家、答辩秘书、实习指导）。

铁律：业务身份**不落成固定角色**
────────────────────────────────
"张老师是这批学生的毕设导师"这件事的权威源是毕设业务表，不是权限表。一旦把它写成
一条长期固定角色，导师换人、任务转交、批次结束都不会自动收回——这正是学校最常见的
越权来源。所以这里**实时从业务权威表计算**，不建任何镜像表：

- 关系在 → 身份在；关系没了 → 身份当场消失（``test_t02`` 就是拿转交验证这一点）；
- 需要人工临时授予时，不直接发权限，而是生成一张 SYS-09 安全变更单走审批激活。

导师侧的键是 t_gd_mentor.id / t_user.id 两套：能映射到账号的给出 userId，
映射不到的显式标 ``subjectResolved=false``，绝不猜。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

IDENTITY_COURSE_TEACHER = "COURSE_TEACHER"
IDENTITY_GD_MENTOR = "GD_MENTOR"
IDENTITY_GD_REVIEWER = "GD_REVIEWER"
IDENTITY_GD_DEFENSE_JUDGE = "GD_DEFENSE_JUDGE"
IDENTITY_GD_DEFENSE_SECRETARY = "GD_DEFENSE_SECRETARY"
IDENTITY_INTERNSHIP_ADVISOR = "INTERNSHIP_ADVISOR"

IDENTITY_LABELS = {
    IDENTITY_COURSE_TEACHER: "任课教师",
    IDENTITY_GD_MENTOR: "毕设导师",
    IDENTITY_GD_REVIEWER: "毕设评阅人",
    IDENTITY_GD_DEFENSE_JUDGE: "答辩评委",
    IDENTITY_GD_DEFENSE_SECRETARY: "答辩秘书",
    IDENTITY_INTERNSHIP_ADVISOR: "实习校内指导教师",
}

IDENTITY_OWNERS = {
    IDENTITY_COURSE_TEACHER: "academicAffairs",
    IDENTITY_GD_MENTOR: "graduationDesign",
    IDENTITY_GD_REVIEWER: "graduationDesign",
    IDENTITY_GD_DEFENSE_JUDGE: "graduationDesign",
    IDENTITY_GD_DEFENSE_SECRETARY: "graduationDesign",
    IDENTITY_INTERNSHIP_ADVISOR: "internship",
}

# 身份 → 业务权威表（写在这里只是为了给页面显示"去哪儿改"，读取仍走下面各自的函数）
IDENTITY_SOURCES = {
    IDENTITY_COURSE_TEACHER: "t_aa_teaching_class_teacher.teacher_id",
    IDENTITY_GD_MENTOR: "t_gd_student.mentor_id",
    IDENTITY_GD_REVIEWER: "t_gd_review.reviewer_mentor_id",
    IDENTITY_GD_DEFENSE_JUDGE: "t_gd_defense_group.chair_mentor_id / judge",
    IDENTITY_GD_DEFENSE_SECRETARY: "t_gd_defense_group.secretary_mentor_id",
    IDENTITY_INTERNSHIP_ADVISOR: "t_internship_record.advisor_user_id",
}


def _tid(tenant_id: int | None = None) -> int:
    return int(tenant_id if tenant_id is not None else (current_tenant_id() or 0))


def _mentor_to_user(db, tenant_id: int) -> dict[int, dict]:
    """t_gd_mentor.id → 账号。映射靠 teacher_no == login_name，映射不上就如实说映射不上。"""
    from app.models import User
    from app.models.graduation import GraduationMentor

    mentors = db.scalars(select(GraduationMentor).where(
        GraduationMentor.tenant_id == tenant_id,
        GraduationMentor.is_deleted.is_(False))).all()
    if not mentors:
        return {}
    by_login = {u.login_name: u for u in db.scalars(select(User).where(
        User.tenant_id == tenant_id, User.is_deleted.is_(False))).all()}
    out: dict[int, dict] = {}
    for m in mentors:
        account = by_login.get(m.teacher_no)
        out[int(m.id)] = {
            "subjectKey": f"mentor:{m.id}",
            "userId": str(account.id) if account is not None else "",
            "name": m.teacher_name or (account.real_name if account is not None else ""),
            "subjectResolved": account is not None,
        }
    return out


def _bump(bucket: dict, key: tuple, subject: dict, object_ref: str) -> None:
    row = bucket.setdefault(key, {"subject": subject, "objects": []})
    row["objects"].append(object_ref)


def compute_identities(*, tenant_id: int | None = None, user_id: int | None = None) -> list[dict]:
    """实时算出本校当前的自动业务身份。不写库、不缓存、不建镜像。"""
    from app.models import User
    from app.models.academic_affairs_teaching_class import AaTeachingClassTeacher
    from app.models.graduation import (GraduationDefenseGroup, GraduationReview,
                                       GraduationStudent)
    from app.models.internship import InternshipRecord

    tid = _tid(tenant_id)
    bucket: dict[tuple, dict] = {}
    db = get_sessionmaker()()
    try:
        accounts = {int(u.id): u for u in db.scalars(select(User).where(
            User.tenant_id == tid, User.is_deleted.is_(False))).all()}

        def _user_subject(uid: Any) -> dict | None:
            if uid in (None, "", 0):
                return None
            account = accounts.get(int(uid))
            return {
                "subjectKey": f"user:{int(uid)}",
                "userId": str(int(uid)),
                "name": account.real_name if account is not None else "",
                "subjectResolved": account is not None,
            }

        for row in db.scalars(select(AaTeachingClassTeacher).where(
                AaTeachingClassTeacher.tenant_id == tid,
                AaTeachingClassTeacher.is_deleted.is_(False),
                AaTeachingClassTeacher.status == "ACTIVE")).all():
            subject = _user_subject(row.teacher_id)
            if subject:
                _bump(bucket, (IDENTITY_COURSE_TEACHER, subject["subjectKey"]), subject,
                      f"teachingClass:{row.teaching_class_id}"
                      if hasattr(row, "teaching_class_id") else f"row:{row.id}")

        mentors = _mentor_to_user(db, tid)
        for row in db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == tid,
                GraduationStudent.is_deleted.is_(False),
                GraduationStudent.record_status == "ACTIVE")).all():
            subject = mentors.get(int(row.mentor_id)) if row.mentor_id else None
            if subject:
                _bump(bucket, (IDENTITY_GD_MENTOR, subject["subjectKey"]), subject,
                      f"gdStudent:{row.id}")

        for row in db.scalars(select(GraduationReview).where(
                GraduationReview.tenant_id == tid,
                GraduationReview.is_deleted.is_(False))).all():
            subject = mentors.get(int(row.reviewer_mentor_id)) if row.reviewer_mentor_id else None
            if subject:
                _bump(bucket, (IDENTITY_GD_REVIEWER, subject["subjectKey"]), subject,
                      f"gdReview:{row.id}")

        for row in db.scalars(select(GraduationDefenseGroup).where(
                GraduationDefenseGroup.tenant_id == tid,
                GraduationDefenseGroup.is_deleted.is_(False))).all():
            chair = mentors.get(int(row.chair_mentor_id)) if row.chair_mentor_id else None
            if chair:
                _bump(bucket, (IDENTITY_GD_DEFENSE_JUDGE, chair["subjectKey"]), chair,
                      f"defenseGroup:{row.id}")
            secretary = (mentors.get(int(row.secretary_mentor_id))
                         if row.secretary_mentor_id else None)
            if secretary:
                _bump(bucket, (IDENTITY_GD_DEFENSE_SECRETARY, secretary["subjectKey"]),
                      secretary, f"defenseGroup:{row.id}")

        for row in db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == tid,
                InternshipRecord.is_deleted.is_(False))).all():
            subject = _user_subject(row.advisor_user_id)
            if subject:
                _bump(bucket, (IDENTITY_INTERNSHIP_ADVISOR, subject["subjectKey"]), subject,
                      f"internship:{row.id}")
    finally:
        db.close()

    out: list[dict] = []
    for (identity_type, _key), row in bucket.items():
        subject = row["subject"]
        if user_id is not None and str(subject.get("userId") or "") != str(int(user_id)):
            continue
        out.append({
            "identityType": identity_type,
            "label": IDENTITY_LABELS[identity_type],
            "ownerModule": IDENTITY_OWNERS[identity_type],
            "source": IDENTITY_SOURCES[identity_type],
            "subjectKey": subject["subjectKey"],
            "userId": subject.get("userId") or "",
            "name": subject.get("name") or "",
            "subjectResolved": bool(subject.get("subjectResolved")),
            "objectCount": len(row["objects"]),
            "objects": row["objects"][:20],
            # 自动身份没有独立的有效期字段：它随业务关系存在而存在
            "effectiveAt": "", "expiresAt": "",
            "validity": "FOLLOWS_BUSINESS_RELATION",
        })
    return sorted(out, key=lambda r: (r["identityType"], r["subjectKey"]))


def list_business_identities(*, tenant_id: int | None = None,
                             identity_type: str = "", user_id: int | None = None) -> dict:
    rows = compute_identities(tenant_id=tenant_id, user_id=user_id)
    if identity_type:
        if identity_type not in IDENTITY_LABELS:
            raise AppException("VALIDATION_ERROR", f"未知业务身份类型：{identity_type}")
        rows = [r for r in rows if r["identityType"] == identity_type]
    unresolved = [r for r in rows if not r["subjectResolved"]]
    return {
        "list": rows,
        "total": len(rows),
        "types": [{"identityType": k, "label": v, "ownerModule": IDENTITY_OWNERS[k],
                   "source": IDENTITY_SOURCES[k]} for k, v in IDENTITY_LABELS.items()],
        "unresolvedSubjects": len(unresolved),
        "note": "业务身份由业务权威表实时计算；要调整请到对应业务模块改关系，本页不写业务终态。",
    }


def request_manual_identity(*, identity_type: str, user_id: int, reason: str,
                            expires_at: str | None = None,
                            tenant_id: int | None = None, user: dict | None = None) -> dict:
    """人工业务身份只能走安全变更：这里**不发权限**，只生成一张待审批的变更单。"""
    if identity_type not in IDENTITY_LABELS:
        raise AppException("VALIDATION_ERROR", f"未知业务身份类型：{identity_type}")
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "应急原因不少于 5 个字")
    tid = _tid(tenant_id)

    from app.services import security_change_service as sec

    change = sec.create_change_set(
        title=f"应急业务身份：{IDENTITY_LABELS[identity_type]} → 账号 {user_id}",
        reason=(f"{reason}｜身份类型={identity_type}｜账号={user_id}"
                f"｜到期={expires_at or '未指定'}｜权威表={IDENTITY_SOURCES[identity_type]}"),
        risk_level="HIGH", tenant_id=tid)

    from app.services import audit_log

    audit_log.record("BUSINESS_IDENTITY_REQUEST",
                     f"申请应急业务身份 {identity_type} → 账号 {user_id}",
                     detail={"reason": reason, "identityType": identity_type,
                             "userId": str(user_id), "expiresAt": expires_at or "",
                             "changeSetId": str(change["changeSetId"]),
                             "moduleCode": "systemAdmin"})
    return {
        "changeSetId": str(change["changeSetId"]),
        "status": "PENDING_SECURITY_CHANGE",
        "identityType": identity_type,
        "ownerModule": IDENTITY_OWNERS[identity_type],
        "authoritativeSource": IDENTITY_SOURCES[identity_type],
        "granted": False,
        # 说清楚边界：安全变更目前只能激活自定义角色与数据范围两类目标，
        # 业务身份的真正落点在业务表，必须由 owner 模块建立关系。这里只留下受审计的申请记录。
        "message": ("已登记为高风险安全变更申请（未授予任何权限）。复核通过后，"
                    f"仍须由 {IDENTITY_OWNERS[identity_type]} 模块在 "
                    f"{IDENTITY_SOURCES[identity_type]} 建立真实业务关系，身份才会出现。"),
    }
