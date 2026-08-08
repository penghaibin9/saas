"""成绩发布消除 N+1（P1 批次C·性能）。

原实现 `publish_grades()` 在逐条成绩明细的循环里，对每个学生各发一次
`db.get(StudentProfile)` + `_acad_student_id()`(内含一次 `select(AcademicStudent)`，
必要时再一次 `db.get(StudentProfile)`)，不及格学生还要再各发一次
`select(AffairsRiskRecord)` 查重复——一个班 15 名学生原来是 30-45 条 SELECT，
且随学生数线性增长。改为发布前一次性批量取出全部学生台账和已存在的预警记录。

本测试用真实 MySQL + SQLAlchemy 事件钩子统计实际发出的 SELECT 语句数，直接证明
"不随学生数线性增长"，而不是只验证功能结果不变（功能结果不变不能证明 N+1 已修）。
"""
from __future__ import annotations

TID = 1000000000000000001


def _ctx():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "1", "tenantId": str(TID), "realName": "教务处",
                      "currentRoleCode": "ACADEMIC_ADMIN", "activeContextId": "ctx"})


def _seed(db, student_count: int, *, batch_tag: str) -> int:
    """1 个 ACADEMIC_REVIEW 成绩任务 + N 名学生各一条已录全成绩的明细（约 1/3 不及格，
    同时覆盖"新建台账"和"预警去重"两条批量查询路径）。"""
    from app.models import AaGradeRecord, AaGradeTask, AaTerm, StudentProfile

    # is_current=False：两个批次(S/L)在同一测试里共存，标两个"当前学期"会撞
    # "学校存在多个当前学期"守卫；publish_grades 本身不依赖 is_current。
    term = AaTerm(tenant_id=TID, year_code=f"2024-2025-{batch_tag}", term_no=1,
                 status="PUBLISHED", is_current=False)
    db.add(term); db.flush()
    task = AaGradeTask(tenant_id=TID, term_id=term.id, course_id=1, course_name="N+1回归测试课",
                       pass_line=60, status="ACADEMIC_REVIEW")
    db.add(task); db.flush()
    for i in range(student_count):
        profile = StudentProfile(tenant_id=TID, student_no=f"NP{batch_tag}{i:04d}", real_name=f"N1学生{i}",
                                 grade="2024", student_status="NORMAL", status="ACTIVE")
        db.add(profile); db.flush()
        failed = (i % 3 == 0)
        db.add(AaGradeRecord(
            tenant_id=TID, task_id=task.id, student_id=profile.id,
            usual_score=80, final_score=(40 if failed else 80),
            total_score=(50 if failed else 80), pass_status=("FAILED" if failed else "PASSED"),
        ))
    db.commit()
    return task.id


def _count_selects_by_table(engine, fn) -> dict:
    """按命中的表名分别计数，而不是笼统的 SELECT 总数——`AcademicGrade` 上还挂着一个
    独立、pre-existing 的 fail-closed ORM 事件钩子（`effective_grade_policy_failclosed`），
    在 Core Connection 层面对每一次 INSERT 都重新解析一次有效成绩策略/当前学期，这是
    另一套子系统的既有设计（防止绕开 service 层写入无策略成绩），本次不动它，也不能让
    它掩盖本次真正要验证的那部分是否还在线性增长。"""
    from sqlalchemy import event
    counters: dict[str, int] = {}

    def _before_cursor_execute(_conn, _cursor, statement, *_args, **_kwargs):
        upper = statement.strip().upper()
        if not upper.startswith("SELECT"):
            return
        for table in ("t_student_profile", "t_acad_student", "t_affairs_risk_record", "t_aa_gpa_point_policy"):
            if table.upper() in upper:
                counters[table] = counters.get(table, 0) + 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    return counters


def test_publish_grades_bulk_lookups_do_not_scale_with_student_count(client, db_mode, monkeypatch):
    """本次批次C修复范围：`_acad_student_id`(→t_student_profile/t_acad_student)、
    不及格预警去重(→t_affairs_risk_record)、GPA 生效策略(→t_aa_gpa_point_policy)
    这三类查询，原来逐条成绩明细各查一次，现在批量化到与学生数无关的常数条——
    15 人和 3 人发布成绩，这三张表各自的 SELECT 命中次数必须完全相等，不能随学生数增长。

    注意：本测试不断言"SELECT 总数不随学生数增长"——AcademicGrade 上还有一个独立的
    fail-closed ORM 事件钩子，按设计对每条 INSERT 各查一次有效成绩策略/当前学期
    （见 academic_affairs_effective_grade_policy_failclosed.py），这是另一套子系统
    有意为之的安全机制，本次不在改动范围内，不能把它算作本次要修的 N+1。"""
    from app.db.session import get_engine, get_sessionmaker
    from app.modules.academic_affairs.services.academic_affairs_grade_core_service import publish_grades

    monkeypatch.setattr(
        "app.modules.academic_affairs.services.academic_affairs_warning_service.scan_warnings",
        lambda *_a, **_kw: None,
    )
    _ctx()
    user = {"userId": "1", "tenantId": str(TID), "realName": "教务处", "currentRoleCode": "ACADEMIC_ADMIN"}
    engine = get_engine()

    db = get_sessionmaker()()
    task_id_small = _seed(db, 3, batch_tag="S")
    db.close()
    small_counts = _count_selects_by_table(engine, lambda: publish_grades(task_id_small, user))

    db = get_sessionmaker()()
    task_id_large = _seed(db, 15, batch_tag="L")
    db.close()
    large_counts = _count_selects_by_table(engine, lambda: publish_grades(task_id_large, user))

    assert small_counts == large_counts, (
        f"批量化后的查询不应随学生数变化(3人={small_counts}, 15人={large_counts})——"
        "命中次数不同说明某一类又退化回了逐行查询"
    )
    assert small_counts.get("t_student_profile", 0) <= 1
    assert small_counts.get("t_acad_student", 0) <= 1
    assert small_counts.get("t_aa_gpa_point_policy", 0) <= 1


def test_publish_grades_still_correct_after_bulk_lookup(client, db_mode):
    """批量化不能改变发布结果：台账正确创建/刷新，不及格生成预警，重复发布不重复插入。"""
    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask, AcademicGrade, AcademicStudent, AffairsRiskRecord
    from app.modules.academic_affairs.services.academic_affairs_grade_core_service import publish_grades

    _ctx()
    user = {"userId": "1", "tenantId": str(TID), "realName": "教务处", "currentRoleCode": "ACADEMIC_ADMIN"}
    db = get_sessionmaker()()
    task_id = _seed(db, 6, batch_tag="C")
    db.close()

    result = publish_grades(task_id, user)
    assert result["status"] == "PUBLISHED"

    db = get_sessionmaker()()
    try:
        task = db.get(AaGradeTask, task_id)
        assert task.status == "PUBLISHED"
        grades = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == TID).all()
        assert len(grades) == 6
        students = db.query(AcademicStudent).filter(AcademicStudent.tenant_id == TID).all()
        assert len(students) == 6, "每个学生只应生成一条台账，不能因批量查询漏建或重复建"
        failed_risks = db.query(AffairsRiskRecord).filter(
            AffairsRiskRecord.tenant_id == TID, AffairsRiskRecord.source == "ACADEMIC_WARNING",
        ).all()
        assert len(failed_risks) == 2, "6 人中 i%3==0 的 2 人(i=0,3)应各生成一条预警"
    finally:
        db.close()
