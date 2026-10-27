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

from sqlalchemy import select, exists, and_, or_

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
    "COUNSELOR_CLASS": "辅导员负责班级",
    "COUNSELOR_CO": "协同辅导员责任",
    "COUNSELOR_TEMP": "临时代班责任",
    "HEAD_TEACHER_CLASS": "班主任负责班级",
    IDENTITY_COURSE_TEACHER: "任课教师",
    IDENTITY_GD_MENTOR: "毕设导师",
    IDENTITY_GD_REVIEWER: "毕设评阅人",
    IDENTITY_GD_DEFENSE_JUDGE: "答辩评委",
    IDENTITY_GD_DEFENSE_SECRETARY: "答辩秘书",
    IDENTITY_INTERNSHIP_ADVISOR: "实习校内指导教师",
}

IDENTITY_OWNERS = {
    "COUNSELOR_CLASS": "studentAffairs",
    "COUNSELOR_CO": "studentAffairs",
    "COUNSELOR_TEMP": "studentAffairs",
    "HEAD_TEACHER_CLASS": "studentAffairs",
    IDENTITY_COURSE_TEACHER: "academicAffairs",
    IDENTITY_GD_MENTOR: "graduationDesign",
    IDENTITY_GD_REVIEWER: "graduationDesign",
    IDENTITY_GD_DEFENSE_JUDGE: "graduationDesign",
    IDENTITY_GD_DEFENSE_SECRETARY: "graduationDesign",
    IDENTITY_INTERNSHIP_ADVISOR: "internship",
}

# 身份 → 业务权威表（写在这里只是为了给页面显示"去哪儿改"，读取仍走下面各自的函数）
IDENTITY_SOURCES = {
    "COUNSELOR_CLASS": "t_affairs_counselor_assignment / 未登记正式主责时 t_class.counselor_id",
    "COUNSELOR_CO": "t_affairs_counselor_assignment.CO",
    "COUNSELOR_TEMP": "t_affairs_counselor_assignment.TEMP",
    "HEAD_TEACHER_CLASS": "t_class.head_teacher_id",
    IDENTITY_COURSE_TEACHER: "t_aa_teaching_class_teacher.teacher_key / 未生成教学班时 t_aa_teaching_task.teacher_key",
    IDENTITY_GD_MENTOR: "t_gd_student.mentor_id",
    IDENTITY_GD_REVIEWER: "t_gd_review.reviewer_mentor_id",
    IDENTITY_GD_DEFENSE_JUDGE: "t_gd_defense_group.chair_mentor_id / judge",
    IDENTITY_GD_DEFENSE_SECRETARY: "t_gd_defense_group.secretary_mentor_id",
    IDENTITY_INTERNSHIP_ADVISOR: "t_internship_record.advisor_user_id",
}


def _tid(tenant_id: int | None = None) -> int:
    return int(tenant_id if tenant_id is not None else (current_tenant_id() or 0))


def _mentor_to_user(db, tenant_id: int, accounts=None, user_id=None) -> dict[int, dict]:
    """t_gd_mentor.id → 账号。映射靠 teacher_no == login_name，映射不上就如实说映射不上。"""
    from app.models import User
    from app.models.graduation import GraduationMentor

    if accounts is None:
        accounts = {u.id: u for u in db.scalars(select(User).where(User.tenant_id == tenant_id, User.is_deleted.is_(False))).all()}
    by_login = {u.login_name: u for u in accounts.values()}
    stmt = select(GraduationMentor).where(GraduationMentor.tenant_id == tenant_id, GraduationMentor.is_deleted.is_(False))
    if user_id is not None:
        stmt = stmt.where(GraduationMentor.teacher_no.in_(list(by_login)))
    mentors = db.scalars(stmt).all()
    out: dict[int, dict] = {}
    for m in mentors:
        account = by_login.get(m.teacher_no)
        out[int(m.id)] = {
            "subjectKey": f"mentor:{m.id}",
            "userId": str(account.id) if account is not None else "",
            "name": account.real_name if account is not None else (m.teacher_name or ""),
            "subjectResolved": account is not None,
        }
    return out


def _bump(bucket: dict, key: tuple, subject: dict, object_ref: str, source: str = '') -> None:
    row = bucket.setdefault(key, {"subject": subject, "objects": [], "seen": set(), "sources": {}})
    if object_ref not in row["seen"]:
        row["seen"].add(object_ref)
        row["objects"].append(object_ref)
        row['sources'][object_ref] = source


def compute_identities(*, tenant_id: int | None = None, user_id: int | None = None,
                       object_page: int = 1, object_page_size: int = 20) -> list[dict]:
    """Read relationship records; they do not represent an authorization decision."""
    from app.models import User, SchoolClass, AaTeachingTask, AaTeachingClass, AaTeachingClassTeacher, AffairsCounselorAssignment
    from app.core.timeutil import utc_now_naive
    from app.models.graduation import GraduationDefenseGroup, GraduationReview, GraduationStudent
    from app.models.internship import InternshipRecord
    from app.services.business_identity_objects import describe_objects
    tid = _tid(tenant_id)
    offset = (max(1, int(object_page)) - 1) * min(100, max(1, int(object_page_size)))
    size = min(100, max(1, int(object_page_size)))
    bucket = {}
    with get_sessionmaker()() as db:
        stmt = select(User).where(User.tenant_id == tid, User.is_deleted.is_(False))
        if user_id is not None:
            stmt = stmt.where(User.id == int(user_id))
        accounts = {u.id: u for u in db.scalars(stmt).all()}
        by_key = {key: u.id for u in accounts.values() for key in (str(u.id), f'db-{u.id}', u.login_name)}
        def subject(uid):
            if not uid:
                return None
            account = accounts.get(int(uid))
            return {'subjectKey': f'user:{uid}', 'userId': str(uid),
                    'name': account.real_name if account else '', 'subjectResolved': account is not None}
        def teacher_subject(key, name):
            uid = by_key.get(str(key or '').strip())
            return subject(uid) if uid else {'subjectKey': 'teacher-key:' + str(key or ''),
                'userId': '', 'name': name or '', 'subjectResolved': False}
        def bump(kind, person, reference, source=''):
            if person and (user_id is None or person.get('userId') == str(user_id)):
                _bump(bucket, (kind, person['subjectKey']), person, reference, source)
        now = utc_now_naive()
        duties = select(AffairsCounselorAssignment).where(AffairsCounselorAssignment.tenant_id == tid,
            AffairsCounselorAssignment.is_deleted.is_(False), AffairsCounselorAssignment.status == 'ACTIVE',
            AffairsCounselorAssignment.effective_from <= now,
            or_(AffairsCounselorAssignment.effective_to.is_(None), AffairsCounselorAssignment.effective_to > now))
        if user_id is not None:
            duties = duties.where(AffairsCounselorAssignment.user_id == user_id)
        for duty in db.scalars(duties).yield_per(500):
            kind = {'PRIMARY': 'COUNSELOR_CLASS', 'CO': 'COUNSELOR_CO', 'TEMP': 'COUNSELOR_TEMP'}.get(duty.duty_type)
            if kind:
                bump(kind, subject(duty.user_id), f'class:{duty.class_id}', '学工正式责任台账')
        has_formal = exists().where(and_(AffairsCounselorAssignment.tenant_id == tid,
            AffairsCounselorAssignment.class_id == SchoolClass.id, AffairsCounselorAssignment.duty_type == 'PRIMARY',
            AffairsCounselorAssignment.is_deleted.is_(False)))
        classes = select(SchoolClass, has_formal.label('has_formal')).where(SchoolClass.tenant_id == tid, SchoolClass.is_deleted.is_(False), SchoolClass.status == 'ACTIVE')
        if user_id is not None:
            classes = classes.where(or_(SchoolClass.counselor_id == user_id, SchoolClass.head_teacher_id == user_id))
        for row, formal_registered in db.execute(classes).yield_per(500):
            if not formal_registered:
                bump('COUNSELOR_CLASS', subject(row.counselor_id), f'class:{row.id}', '班级档案字段（尚未登记正式主责）')
            bump('HEAD_TEACHER_CLASS', subject(row.head_teacher_id), f'class:{row.id}', '班级档案班主任字段')
        formal = select(AaTeachingClassTeacher).where(AaTeachingClassTeacher.tenant_id == tid,
            AaTeachingClassTeacher.is_deleted.is_(False), AaTeachingClassTeacher.status == 'ACTIVE')
        if user_id is not None:
            formal = formal.where(AaTeachingClassTeacher.teacher_key.in_(list(by_key)))
        for row in db.scalars(formal).yield_per(500):
            bump(IDENTITY_COURSE_TEACHER, teacher_subject(row.teacher_key, row.teacher_name), f'teachingClass:{row.teaching_class_id}')
        fallback = select(AaTeachingTask).where(AaTeachingTask.tenant_id == tid, AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.teacher_key.is_not(None), ~exists().where(and_(AaTeachingClass.tenant_id == tid,
                AaTeachingClass.teaching_task_id == AaTeachingTask.id, AaTeachingClass.is_deleted.is_(False))))
        if user_id is not None:
            fallback = fallback.where(AaTeachingTask.teacher_key.in_(list(by_key)))
        for row in db.scalars(fallback).yield_per(500):
            bump(IDENTITY_COURSE_TEACHER, teacher_subject(row.teacher_key, row.teacher_name), f'teachingTask:{row.id}')
        mentors = _mentor_to_user(db, tid, accounts, user_id)
        students = select(GraduationStudent).where(GraduationStudent.tenant_id == tid,
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == 'ACTIVE')
        if user_id is not None:
            students = students.where(GraduationStudent.mentor_id.in_(list(mentors)))
        for row in db.scalars(students).yield_per(500):
            bump(IDENTITY_GD_MENTOR, mentors.get(row.mentor_id), f'gdStudent:{row.id}')
        reviews = select(GraduationReview).where(GraduationReview.tenant_id == tid, GraduationReview.is_deleted.is_(False))
        if user_id is not None:
            reviews = reviews.where(GraduationReview.reviewer_mentor_id.in_(list(mentors)))
        for row in db.scalars(reviews).yield_per(500):
            bump(IDENTITY_GD_REVIEWER, mentors.get(row.reviewer_mentor_id), f'gdReview:{row.id}')
        groups = select(GraduationDefenseGroup).where(GraduationDefenseGroup.tenant_id == tid, GraduationDefenseGroup.is_deleted.is_(False))
        if user_id is not None:
            groups = groups.where(or_(GraduationDefenseGroup.chair_mentor_id.in_(list(mentors)), GraduationDefenseGroup.secretary_mentor_id.in_(list(mentors))))
        for row in db.scalars(groups).yield_per(500):
            bump(IDENTITY_GD_DEFENSE_JUDGE, mentors.get(row.chair_mentor_id), f'defenseGroup:{row.id}')
            bump(IDENTITY_GD_DEFENSE_SECRETARY, mentors.get(row.secretary_mentor_id), f'defenseGroup:{row.id}')
        internships = select(InternshipRecord).where(InternshipRecord.tenant_id == tid, InternshipRecord.is_deleted.is_(False))
        if user_id is not None:
            internships = internships.where(InternshipRecord.advisor_user_id == user_id)
        for row in db.scalars(internships).yield_per(500):
            bump(IDENTITY_INTERNSHIP_ADVISOR, subject(row.advisor_user_id), f'internship:{row.id}')
        for row in bucket.values():
            row['objects'].sort(key=lambda ref: (ref.partition(':')[0], int(ref.partition(':')[2])))
        references = {ref for row in bucket.values() for ref in row['objects'][offset:offset + size]}
        descriptions = describe_objects(db, tid, references)
    out = []
    for (kind, key), row in bucket.items():
        person = row['subject']; objects = row['objects'][offset:offset + size]
        out.append({'identityType': kind, 'identityKey': kind + ':' + key,
            'label': IDENTITY_LABELS[kind], 'ownerModule': IDENTITY_OWNERS[kind], 'source': IDENTITY_SOURCES[kind],
            **person, 'objectCount': len(row['objects']), 'objects': objects,
            'objectItems': [{**descriptions[ref], 'relationSource': row['sources'].get(ref, '')} for ref in objects], 'objectPage': max(1, int(object_page)),
            'effectiveAt': '', 'expiresAt': '', 'validity': 'FOLLOWS_BUSINESS_RELATION'})
    return sorted(out, key=lambda row: (row['identityType'], row['subjectKey']))


def list_identity_objects(*, identity_type: str, subject_key: str, user_id: int | None = None,
                          page: int = 1, page_size: int = 20, tenant_id: int | None = None) -> dict:
    if identity_type not in IDENTITY_LABELS:
        raise AppException('VALIDATION_ERROR', '请选择已登记的业务关系类型')
    rows = compute_identities(tenant_id=tenant_id, user_id=user_id, object_page=page, object_page_size=page_size)
    row = next((item for item in rows if item['identityType'] == identity_type and item['subjectKey'] == subject_key), None)
    if row is None:
        raise AppException('DATA_NOT_FOUND', '该业务关系已失效或不在本校，请刷新关系清单')
    return {'list': row['objectItems'], 'total': row['objectCount'], 'page': page, 'pageSize': page_size}


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
        "note": "关系直接读取各业务模块；对象数不代表实际可访问人数，教学周与批次权限仍由业务模块校验。本页不修改关系。",
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
