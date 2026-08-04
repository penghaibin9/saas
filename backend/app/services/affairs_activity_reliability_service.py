"""学生活动四端可靠性收口。

- 学生可报名活动严格按 SCHOOL/COLLEGE/CLASS 适用范围裁剪；
- 教师列表按学工数据范围裁剪；
- 报名锁定活动行，名额判断与写入处于同一事务，避免并发超额；
- 活动列表使用 SQL count + offset/limit + 报名数聚合，消除全量加载和 N+1。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session


def _student_org(db, user) -> tuple[object, set[str], set[str]]:
    from app.models import College, Major, SchoolClass
    from app.services.mobile_student_service import _require_student, resolve_student

    _require_student(user)
    student = resolve_student(db, user)
    if not student:
        raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
    class_tokens: set[str] = set()
    college_tokens: set[str] = set()
    cls = db.get(SchoolClass, int(student.class_id)) if student.class_id else None
    if cls and not cls.is_deleted and cls.tenant_id == _tid():
        class_tokens.update(filter(None, {
            str(cls.id), str(cls.class_code or "").strip(), str(cls.class_name or "").strip(),
        }))
        major = db.get(Major, int(cls.major_id)) if cls.major_id else None
        college = db.get(College, int(major.college_id)) if major and major.college_id else None
        if college and not college.is_deleted and college.tenant_id == _tid():
            college_tokens.update(filter(None, {
                str(college.id), str(college.code or "").strip(),
                str(college.college_name or "").strip(), str(college.short_name or "").strip(),
            }))
    return student, class_tokens, college_tokens


def _activity_matches(activity, class_tokens: set[str], college_tokens: set[str]) -> bool:
    scope_type = str(activity.scope_type or "SCHOOL").upper()
    ref = str(activity.scope_ref or "").strip()
    if scope_type == "SCHOOL":
        return True
    if scope_type == "CLASS":
        return bool(ref) and ref in class_tokens
    if scope_type == "COLLEGE":
        return bool(ref) and ref in college_tokens
    return False


def _teacher_scope_tokens(db, user) -> tuple[bool, set[str], set[str]]:
    from app.core.affairs_security import build_affairs_context
    from app.models import College, Major, SchoolClass, StudentProfile

    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return True, set(), set()

    student_ids: set[int] = set()
    if ctx.scope_type == "STUDENT":
        student_ids = {int(x) for x in (ctx.student_ids | ctx.psychology_student_ids)}
        class_ids = set(db.scalars(select(StudentProfile.class_id).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id.in_(student_ids or {-1}),
            StudentProfile.is_deleted.is_(False),
        )).all())
    else:
        class_ids = set(ctx.allowed_class_ids(db) or set())

    classes = db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == _tid(),
        SchoolClass.id.in_(class_ids or {-1}),
        SchoolClass.is_deleted.is_(False),
    )).all()
    class_tokens: set[str] = set()
    major_ids: set[int] = set()
    for cls in classes:
        class_tokens.update(filter(None, {
            str(cls.id), str(cls.class_code or "").strip(), str(cls.class_name or "").strip(),
        }))
        if cls.major_id:
            major_ids.add(int(cls.major_id))
    majors = db.scalars(select(Major).where(
        Major.tenant_id == _tid(), Major.id.in_(major_ids or {-1}), Major.is_deleted.is_(False),
    )).all()
    college_ids = {int(x.college_id) for x in majors if x.college_id}
    colleges = db.scalars(select(College).where(
        College.tenant_id == _tid(), College.id.in_(college_ids or {-1}), College.is_deleted.is_(False),
    )).all()
    college_tokens: set[str] = set()
    for college in colleges:
        college_tokens.update(filter(None, {
            str(college.id), str(college.code or "").strip(),
            str(college.college_name or "").strip(), str(college.short_name or "").strip(),
        }))
    return False, class_tokens, college_tokens


def _scope_condition(model, tenant_all: bool, class_tokens: set[str], college_tokens: set[str]):
    if tenant_all:
        return None
    return or_(
        model.scope_type.is_(None),
        model.scope_type == "SCHOOL",
        (model.scope_type == "CLASS") & model.scope_ref.in_(class_tokens or {"__NONE__"}),
        (model.scope_type == "COLLEGE") & model.scope_ref.in_(college_tokens or {"__NONE__"}),
    )


def install() -> None:
    from app.models import AffairsActivity, AffairsActivitySignup
    from app.services import affairs_activity_service as activity
    from app.services.affairs_list_stats import status_counts_by_column

    def list_activities(user, activity_type=None, status=None, page=1, page_size=20):
        page = max(1, int(page or 1))
        page_size = min(200, max(1, int(page_size or 20)))
        with session() as db:
            tenant_all, class_tokens, college_tokens = _teacher_scope_tokens(db, user)
            base_conds = [AffairsActivity.tenant_id == _tid(), AffairsActivity.is_deleted.is_(False)]
            scope_cond = _scope_condition(AffairsActivity, tenant_all, class_tokens, college_tokens)
            if scope_cond is not None:
                base_conds.append(scope_cond)
            if activity_type:
                base_conds.append(AffairsActivity.activity_type == activity_type)
            conds = list(base_conds)
            if status:
                statuses = [x.strip() for x in str(status).split(",") if x.strip()]
                conds.append(AffairsActivity.status.in_(statuses))

            total = int(db.scalar(select(func.count()).select_from(AffairsActivity).where(*conds)) or 0)
            status_counts = status_counts_by_column(
                db, AffairsActivity, AffairsActivity.status, base_conds,
            )
            signup_counts = (
                select(
                    AffairsActivitySignup.activity_id.label("activity_id"),
                    func.count(AffairsActivitySignup.id).label("signup_count"),
                )
                .where(
                    AffairsActivitySignup.tenant_id == _tid(),
                    AffairsActivitySignup.signup_status != "CANCELLED",
                    AffairsActivitySignup.is_deleted.is_(False),
                )
                .group_by(AffairsActivitySignup.activity_id)
                .subquery()
            )
            rows = db.execute(
                select(
                    AffairsActivity,
                    func.coalesce(signup_counts.c.signup_count, 0),
                )
                .outerjoin(signup_counts, signup_counts.c.activity_id == AffairsActivity.id)
                .where(*conds)
                .order_by(AffairsActivity.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return [
                activity._row(row, signup_count=int(count or 0))
                for row, count in rows
            ], total, status_counts

    def enroll(activity_id, user, action="ENROLL"):
        action = str(action or "ENROLL").upper()
        with session() as db:
            student, class_tokens, college_tokens = _student_org(db, user)
            row = db.scalars(select(AffairsActivity).where(
                AffairsActivity.tenant_id == _tid(),
                AffairsActivity.id == int(activity_id),
                AffairsActivity.is_deleted.is_(False),
            ).with_for_update()).first()
            if not row:
                raise AppException("DATA_NOT_FOUND", "活动不存在")
            if not _activity_matches(row, class_tokens, college_tokens):
                raise AppException("NO_DATA_SCOPE", "该活动不在你的适用范围内")
            if row.status != "PUBLISHED":
                raise AppException("DATA_CONFLICT", "活动未在报名中")
            if row.enroll_deadline and row.enroll_deadline < datetime.utcnow():
                raise AppException("DATA_CONFLICT", "报名已截止")

            signup = db.scalars(select(AffairsActivitySignup).where(
                AffairsActivitySignup.tenant_id == _tid(),
                AffairsActivitySignup.activity_id == row.id,
                AffairsActivitySignup.student_id == int(student.id),
                AffairsActivitySignup.is_deleted.is_(False),
            ).with_for_update()).first()
            if action == "CANCEL":
                if signup and signup.signup_status in ("ENROLLED", "WAITLIST"):
                    signup.signup_status = "CANCELLED"
                    signup.version = int(signup.version or 0) + 1
                    activity._audit(db, row.id, "ACTIVITY_ENROLL_CANCEL", f"student={student.id}")
                db.commit()
                return {"activityId": str(row.id), "signupStatus": "CANCELLED"}
            if action != "ENROLL":
                raise AppException("VALIDATION_ERROR", "报名动作非法")
            if signup and signup.signup_status in ("ENROLLED", "WAITLIST", "CHECKED_IN", "CONFIRMED"):
                raise AppException("DATA_CONFLICT", "已报名，请勿重复")
            if row.quota is not None:
                count = int(db.scalar(select(func.count()).select_from(AffairsActivitySignup).where(
                    AffairsActivitySignup.tenant_id == _tid(),
                    AffairsActivitySignup.activity_id == row.id,
                    AffairsActivitySignup.signup_status.in_(("ENROLLED", "CHECKED_IN", "CONFIRMED")),
                    AffairsActivitySignup.is_deleted.is_(False),
                )) or 0)
                if count >= int(row.quota):
                    raise AppException("DATA_CONFLICT", "活动名额已满")
            if signup:
                signup.signup_status = "ENROLLED"
                signup.enrolled_at = datetime.utcnow()
                signup.version = int(signup.version or 0) + 1
            else:
                db.add(AffairsActivitySignup(
                    tenant_id=_tid(), activity_id=row.id, student_id=int(student.id),
                    signup_status="ENROLLED", enrolled_at=datetime.utcnow(),
                ))
            activity._audit(db, row.id, "ACTIVITY_ENROLL", f"student={student.id}")
            db.commit()
            return {"activityId": str(row.id), "signupStatus": "ENROLLED"}

    def my_activities(user, page=1, page_size=20):
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 20)))
        with session() as db:
            student, class_tokens, college_tokens = _student_org(db, user)
            scope_cond = _scope_condition(
                AffairsActivity, False, class_tokens, college_tokens,
            )
            available_conds = [
                AffairsActivity.tenant_id == _tid(),
                AffairsActivity.status == "PUBLISHED",
                AffairsActivity.is_deleted.is_(False),
            ]
            if scope_cond is not None:
                available_conds.append(scope_cond)
            available_total = int(db.scalar(
                select(func.count()).select_from(AffairsActivity).where(*available_conds)
            ) or 0)
            available_rows = db.scalars(
                select(AffairsActivity)
                .where(*available_conds)
                .order_by(AffairsActivity.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            available_ids = {int(x.id) for x in available_rows}
            page_signups = db.scalars(select(AffairsActivitySignup).where(
                AffairsActivitySignup.tenant_id == _tid(),
                AffairsActivitySignup.student_id == int(student.id),
                AffairsActivitySignup.activity_id.in_(available_ids or {-1}),
                AffairsActivitySignup.is_deleted.is_(False),
            )).all()
            signup_map = {int(x.activity_id): x for x in page_signups}
            available = [
                {**activity._row(row), "mySignupStatus": (
                    signup_map[int(row.id)].signup_status if int(row.id) in signup_map else None
                )}
                for row in available_rows
            ]

            mine_base = [
                AffairsActivitySignup.tenant_id == _tid(),
                AffairsActivitySignup.student_id == int(student.id),
                AffairsActivitySignup.is_deleted.is_(False),
            ]
            mine_total = int(db.scalar(
                select(func.count()).select_from(AffairsActivitySignup).where(*mine_base)
            ) or 0)
            mine_rows = db.execute(
                select(AffairsActivitySignup, AffairsActivity)
                .join(AffairsActivity, AffairsActivity.id == AffairsActivitySignup.activity_id)
                .where(
                    *mine_base,
                    AffairsActivity.tenant_id == _tid(),
                    AffairsActivity.is_deleted.is_(False),
                )
                .order_by(AffairsActivitySignup.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            mine = [
                {**activity._row(row), "mySignupStatus": signup.signup_status}
                for signup, row in mine_rows
            ]
            return {
                "available": available,
                "mine": mine,
                "availableTotal": available_total,
                "mineTotal": mine_total,
                "page": page,
                "pageSize": page_size,
                "availableHasMore": page * page_size < available_total,
                "mineHasMore": page * page_size < mine_total,
            }


    activity.list_activities = list_activities
    activity.enroll = enroll
    activity.my_activities = my_activities
