"""V2-04 正式成绩课程身份与修读次数解析。

原则：
- ``course_id`` 指向具体 AaCourse 版本行，``course_code + course_version``作为不可变快照；
- 新教学任务发布代表一次新的修读，attempt_no 在同一学生+稳定课程代码下递增；
- 补考/清考不增加修读次数，后续写入口必须继承原成绩 attempt_no；
- 历史无ID成绩只进入欠账报告，不在运行时按课程名静默合并。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid


def resolve_grade_task_course(db, grade_task):
    """解析成绩任务对应的具体课程版本，并兼容回填 AaGradeTask.course_id。"""
    from app.models import AaCourse, AaTeachingTask

    course_id = int(grade_task.course_id) if getattr(grade_task, "course_id", None) else None
    if course_id is None and getattr(grade_task, "teaching_task_id", None):
        teaching_task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == int(grade_task.teaching_task_id),
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
        if not teaching_task:
            raise not_found("成绩任务关联的教学任务不存在")
        course_id = int(teaching_task.course_id) if teaching_task.course_id else None
        if course_id:
            grade_task.course_id = course_id
    if course_id is None:
        raise AppException(
            "DATA_CONFLICT",
            "成绩任务没有稳定courseId，禁止发布正式成绩；请先绑定课程库具体版本",
            http_status=409,
        )

    course = db.query(AaCourse).filter(
        AaCourse.id == course_id,
        AaCourse.tenant_id == _tid(),
        AaCourse.is_deleted.is_(False),
    ).first()
    if not course:
        raise not_found("成绩任务绑定的课程版本不存在或已删除")
    if not (course.course_code or "").strip() or not int(course.version or 0):
        raise AppException("DATA_CONFLICT", "课程库版本缺少课程代码或版本号，禁止发布正式成绩", http_status=409)

    # 任务展示快照可保留历史名称，但缺失的名称/学分必须从具体课程版本补齐。
    if not (grade_task.course_name or "").strip():
        grade_task.course_name = course.course_name
    if grade_task.credit is None:
        grade_task.credit = course.credit
    return course


def lock_grade_identity(db, acad_student_id: int, course_code: str):
    """取得并锁定 (学生, 稳定课程代码) 的成绩身份头。

    这是所有正式成绩写入的互斥点。返回前该行已持有排他锁，调用方必须在同一事务里完成
    「读现状 → 判重 → 分配 attempt_no → 写成绩」，锁随事务提交释放。
    """
    from app.models import AaGradeIdentityHead

    code = str(course_code or "").strip()
    if not code:
        raise AppException(
            "DATA_CONFLICT",
            "正式成绩缺少稳定课程代码，无法分配修读次数",
            http_status=409,
        )

    def _query():
        return db.query(AaGradeIdentityHead).filter(
            AaGradeIdentityHead.tenant_id == _tid(),
            AaGradeIdentityHead.acad_student_id == int(acad_student_id),
            AaGradeIdentityHead.course_code == code,
            AaGradeIdentityHead.is_deleted.is_(False),
        )

    head = _query().with_for_update().first()
    if head:
        return head
    # 首次写这门课的成绩：建头再锁。并发下另一个事务可能抢先插入，唯一约束会让本次 INSERT 失败；
    # 用 savepoint 包住，失败时只回滚这一小段而不是整个业务事务，然后改读对方那一行。
    #
    # 进 savepoint 前必须先把调用方已有的待写数据 flush 掉：begin_nested() 之后的 flush 会把
    # session 里所有 pending 对象一起写进这个 savepoint，一旦建头撞唯一键回滚，调用方在本次
    # 业务里写的成绩行会被一并撤销——业务数据丢在一个本该只影响计数器的地方。
    db.flush()
    try:
        with db.begin_nested():
            head = AaGradeIdentityHead(
                tenant_id=_tid(), acad_student_id=int(acad_student_id),
                course_code=code, current_attempt_no=0,
            )
            db.add(head)
            db.flush()
    except IntegrityError:
        head = None
    return _query().with_for_update().first() or head


def next_study_attempt_no(db, acad_student_id: int, course_code: str,
                          *, source_biz_type: str | None = None) -> int:
    """分配同一学生、同一稳定课程代码的下一次修读编号。

    原实现是 ``SELECT MAX(attempt_no) + 1``，没有任何互斥：两个事务同时读到 MAX=0 就各自
    返回 1。正常发布、成绩认定、免修、补考、清考、重修全都会写正式成绩，任意两条路径并发
    就能给同一个学生同一门课造出两条 attempt_no 相同且都 PASSED 的正式事实——
    (source_biz_type, source_biz_id) 唯一键拦不住，因为两条来源本来就不同。

    现在先锁成绩身份头，把同一(学生,课程)的分配串行化，计数器落在头上而不是每次重算。
    course_id 指向版本行、改版后会变，因此修读次数按稳定 course_code 聚合。
    历史 NULL attempt_no 不参与推断，避免按课程名猜测；回填后才进入正式序列。
    """
    from app.models import AcademicGrade

    head = lock_grade_identity(db, acad_student_id, course_code)
    allocated = int(head.current_attempt_no or 0)
    if allocated <= 0:
        # 头是新建的：用存量正式成绩的最大值初始化，保证已有历史数据不被重号。
        # 此处普通读安全——能走到这里说明本事务是第一个拿到该头锁的，没有并发方已提交的新值。
        max_no = db.scalar(select(func.max(AcademicGrade.attempt_no)).where(
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.acad_student_id == int(acad_student_id),
            AcademicGrade.course_code == str(course_code).strip(),
            AcademicGrade.attempt_no.is_not(None),
            AcademicGrade.is_deleted.is_(False),
        ))
        allocated = int(max_no or 0)

    nxt = allocated + 1
    head.current_attempt_no = nxt
    head.last_source_biz_type = (source_biz_type or "").strip().upper() or None
    head.last_allocated_at = datetime.utcnow()
    return nxt


def source_attempt_no(source_grade) -> int:
    """补考/清考继承原修读次数；原成绩未治理时fail-closed。"""
    value = getattr(source_grade, "attempt_no", None)
    if value is None or int(value) <= 0:
        raise AppException(
            "DATA_CONFLICT",
            "原成绩缺少修读次数，禁止生成新的补考/清考正式成绩；请先完成成绩身份回填",
            http_status=409,
        )
    return int(value)


def course_snapshot(course) -> dict:
    return {
        "courseId": int(course.id),
        "courseCode": str(course.course_code or "").strip(),
        "courseVersion": int(course.version or 0),
        "courseName": course.course_name or "",
        "nature": course.nature or "REQUIRED",
        "credit": float(course.credit or 0),
    }


def roster_snapshot(roster_data: dict) -> dict:
    def _int_or_none(value):
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    return {
        "teachingClassId": _int_or_none(roster_data.get("teachingClassId")),
        "rosterVersionId": _int_or_none(roster_data.get("rosterVersionId")),
        "rosterVersionNo": _int_or_none(roster_data.get("rosterVersionNo")),
        "rosterSource": roster_data.get("source") or "",
    }


def grade_identity_debt(db, *, term: str | None = None) -> dict:
    """历史正式成绩身份欠账只读汇总，不猜测回填。"""
    from app.models import AcademicGrade

    query = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )
    if term:
        query = query.filter(AcademicGrade.term == term)
    rows = query.all()
    missing_course = [row for row in rows if not row.course_id or not row.course_code or not row.course_version]
    missing_attempt = [row for row in rows if not row.attempt_no]
    return {
        "total": len(rows),
        "missingCourseIdentity": len(missing_course),
        "missingAttemptNo": len(missing_attempt),
        "ready": not missing_course and not missing_attempt,
        "sampleGradeIds": [str(row.id) for row in (missing_course + missing_attempt)[:50]],
    }
