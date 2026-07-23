"""工作台 P5：毕设/实习流程写入 UnifiedTodo，审结后标 DONE（幂等）。

造数走 mentor_id→teacher_no / advisor_user_id，保证 assignee 可解析。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001


def _uid_token(uid: int, role: str, real_name: str = "导师", login_name: str | None = None):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": str(uid), "realName": real_name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": "PC",
        "loginName": login_name or f"T{uid}"})}


def test_gd_proposal_todo_upsert_and_done(db_mode):
    from app.core.context import set_current_user
    from app.db.session import get_sessionmaker
    from app.models import (GraduationMentor, GraduationProposal, GraduationStudent,
                            GraduationTaskBook, UnifiedTodo, User)
    from app.modules.graduation.services import graduation_service as gd_svc
    from app.modules.graduation.services import graduation_todo_helper as gd_todo

    db = get_sessionmaker()()
    try:
        u = User(tenant_id=TID, login_name="GD-M-P5", real_name="毕设P5导师",
                 password_hash="x", user_type="TEACHER", status="ACTIVE")
        db.add(u); db.flush()
        m = GraduationMentor(
            tenant_id=TID, teacher_no="GD-M-P5", teacher_name="毕设P5导师",
            qualification_status="QUALIFIED", max_capacity=10)
        db.add(m); db.flush()
        stu = GraduationStudent(
            tenant_id=TID, student_id=88001, student_no="GDP5-01", name="开题生P5",
            advisor_name="毕设P5导师", mentor_id=m.id, topic_id=1, topic_title="题目",
            stage="GUIDING", eligibility_status="QUALIFIED")
        db.add(stu); db.flush()
        db.add(GraduationTaskBook(
            tenant_id=TID, gd_student_id=stu.id, taskbook_version=1, status="CONFIRMED",
            objective="目标", content="内容", history_json=[], confirmed_at=datetime.utcnow()))
        db.commit()
        gid, mentor_uid = stu.id, u.id
    finally:
        db.close()

    out = gd_svc.submit_proposal(gid, "选题背景说明足够长用于测试",
                                 "研究方案足够长用于测试十二周", "预期成果系统")
    pid = int(out["id"])

    db = get_sessionmaker()()
    try:
        todos = db.query(UnifiedTodo).filter_by(
            source_module="graduation", source_biz_id=pid,
            todo_type=gd_todo.TODO_PROPOSAL, assignee_id=mentor_uid).all()
        assert len(todos) == 1 and todos[0].status == "PENDING"
        assert "开题待批阅" in todos[0].title
        p = db.get(GraduationProposal, pid)
        stu = db.get(GraduationStudent, gid)
        gd_todo.push_proposal_todo(db, p, stu)
        db.commit()
        assert db.query(UnifiedTodo).filter_by(
            source_module="graduation", source_biz_id=pid,
            todo_type=gd_todo.TODO_PROPOSAL, assignee_id=mentor_uid).count() == 1
    finally:
        db.close()

    set_current_user({
        "currentRoleCode": "SCHOOL_ADMIN", "userType": "TEACHER",
        "realName": "校管", "userId": "1", "tenantId": str(TID)})
    try:
        gd_svc.review_proposal(pid, "APPROVE", comment=None)
    finally:
        set_current_user(None)

    db = get_sessionmaker()()
    try:
        row = db.query(UnifiedTodo).filter_by(
            source_module="graduation", source_biz_id=pid,
            todo_type=gd_todo.TODO_PROPOSAL, assignee_id=mentor_uid).one()
        assert row.status == "DONE"
    finally:
        db.close()


def test_gd_final_and_topic_change_todo_helper(db_mode):
    """成果与选题变更：helper 写入 PENDING，todo_done 标 DONE，重复 upsert 幂等。"""
    from app.db.session import get_sessionmaker
    from app.models import (GraduationFinal, GraduationMentor, GraduationStudent,
                            GraduationTopicChangeRequest, UnifiedTodo, User)
    from app.modules.graduation.services import graduation_todo_helper as gd_todo

    db = get_sessionmaker()()
    try:
        u = User(tenant_id=TID, login_name="GD-M-P5B", real_name="毕设P5B",
                 password_hash="x", user_type="TEACHER", status="ACTIVE")
        db.add(u); db.flush()
        m = GraduationMentor(
            tenant_id=TID, teacher_no="GD-M-P5B", teacher_name="毕设P5B",
            qualification_status="QUALIFIED", max_capacity=10)
        db.add(m); db.flush()
        stu = GraduationStudent(
            tenant_id=TID, student_id=88002, student_no="GDP5-02", name="成果生P5",
            advisor_name="毕设P5B", mentor_id=m.id, topic_id=2, topic_title="题B",
            stage="GUIDING", eligibility_status="QUALIFIED")
        db.add(stu); db.flush()
        fin = GraduationFinal(
            tenant_id=TID, gd_student_id=stu.id, final_type="THESIS", status="PENDING_REVIEW",
            submit_at=datetime.utcnow())
        db.add(fin); db.flush()
        ch = GraduationTopicChangeRequest(
            tenant_id=TID, gd_student_id=stu.id, old_topic_id=2, new_topic_id=3,
            reason="选题理由足够长", status="PENDING")
        db.add(ch); db.flush()
        assert gd_todo.push_final_todo(db, fin, stu) is True
        assert gd_todo.push_topic_change_todo(db, ch, stu) is True
        db.flush()
        # 同会话二次 upsert：须先 flush 才能被 select 命中，否则会插入重复键
        assert gd_todo.push_final_todo(db, fin, stu) is True
        assert gd_todo.push_topic_change_todo(db, ch, stu) is True
        db.commit()
        fid, cid, mentor_uid = fin.id, ch.id, u.id
    finally:
        db.close()

    db = get_sessionmaker()()
    try:
        assert db.query(UnifiedTodo).filter_by(
            todo_type=gd_todo.TODO_FINAL, source_biz_id=fid, assignee_id=mentor_uid).count() == 1
        assert db.query(UnifiedTodo).filter_by(
            todo_type=gd_todo.TODO_TOPIC_CHANGE, source_biz_id=cid, assignee_id=mentor_uid).count() == 1
        assert gd_todo.todo_done(db, biz_id=fid, todo_type=gd_todo.TODO_FINAL) == 1
        assert gd_todo.todo_done(db, biz_id=cid, todo_type=gd_todo.TODO_TOPIC_CHANGE) == 1
        db.commit()
        assert db.query(UnifiedTodo).filter_by(
            todo_type=gd_todo.TODO_FINAL, source_biz_id=fid).one().status == "DONE"
        assert db.query(UnifiedTodo).filter_by(
            todo_type=gd_todo.TODO_TOPIC_CHANGE, source_biz_id=cid).one().status == "DONE"
    finally:
        db.close()


def test_intern_exception_and_visit_todo_helper(db_mode):
    """打卡异常与巡访整改待办：写入后办结。"""
    from app.db.session import get_sessionmaker
    from app.models import (AttendanceException, InternshipRecord, InternshipVisit,
                            StudentProfile, UnifiedTodo, User)
    from app.modules.internship.services import internship_todo_helper as ix_todo

    db = get_sessionmaker()()
    try:
        mentor = User(tenant_id=TID, login_name="IX-M-P5B", real_name="实习P5B",
                      password_hash="x", user_type="TEACHER", status="ACTIVE")
        db.add(mentor); db.flush()
        stu = StudentProfile(tenant_id=TID, student_no="IXP5-02", real_name="异常生P5",
                             current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(stu); db.flush()
        rec = InternshipRecord(
            tenant_id=TID, student_id=stu.id, advisor_user_id=mentor.id,
            advisor_name="实习P5B", enterprise_name="企业B", position_name="岗B",
            status="ONBOARD", risk_level="NONE")
        db.add(rec); db.flush()
        exc = AttendanceException(
            tenant_id=TID, internship_id=rec.id, exception_type="MISSING",
            exception_date=datetime.utcnow(), status="PENDING_HANDLE")
        db.add(exc); db.flush()
        vis = InternshipVisit(
            tenant_id=TID, internship_id=rec.id, student_id=stu.id,
            method="PHONE", rectify_status="PENDING", visit_at=datetime.utcnow())
        db.add(vis); db.flush()
        assert ix_todo.push_exception_todo(db, exc, rec) is True
        assert ix_todo.push_visit_rectify_todo(db, vis, rec) is True
        db.commit()
        eid, vid, mentor_uid = exc.id, vis.id, mentor.id
    finally:
        db.close()

    db = get_sessionmaker()()
    try:
        assert db.query(UnifiedTodo).filter_by(
            todo_type=ix_todo.TODO_EXCEPTION, source_biz_id=eid, assignee_id=mentor_uid).count() == 1
        assert db.query(UnifiedTodo).filter_by(
            todo_type=ix_todo.TODO_VISIT_RECTIFY, source_biz_id=vid, assignee_id=mentor_uid).count() == 1
        ix_todo.todo_done(db, biz_id=eid, todo_type=ix_todo.TODO_EXCEPTION)
        ix_todo.todo_done(db, biz_id=vid, todo_type=ix_todo.TODO_VISIT_RECTIFY)
        db.commit()
        assert db.query(UnifiedTodo).filter_by(
            todo_type=ix_todo.TODO_EXCEPTION, source_biz_id=eid).one().status == "DONE"
        assert db.query(UnifiedTodo).filter_by(
            todo_type=ix_todo.TODO_VISIT_RECTIFY, source_biz_id=vid).one().status == "DONE"
    finally:
        db.close()


def test_prod_blocks_mock_todo_summary(monkeypatch):
    """P1/P6：生产环境未开库时 /todos/summary 不得回落假数字。"""
    from app.api.v1 import todo as todo_api
    from app.core.exceptions import AppException

    monkeypatch.setattr(todo_api, "db_enabled", lambda: False)
    monkeypatch.setattr(todo_api.settings, "APP_ENV", "prod")
    try:
        todo_api._use_real_db()
        assert False, "should raise"
    except AppException as e:
        assert e.code == "SERVER_ERROR"
        assert e.details and e.details.get("reason") == "DB_REQUIRED_IN_PROD"


def test_intern_weekly_and_leave_todo_lifecycle(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (InternshipLeave, InternshipRecord, StudentProfile,
                            UnifiedTodo, User, WeeklyReport)
    from app.modules.internship.services import internship_leave_service as leave_svc
    from app.modules.internship.services import internship_todo_helper as ix_todo

    db = get_sessionmaker()()
    try:
        mentor = User(tenant_id=TID, login_name="IX-M-P5", real_name="实习P5导师",
                      password_hash="x", user_type="TEACHER", status="ACTIVE")
        db.add(mentor); db.flush()
        stu = StudentProfile(tenant_id=TID, student_no="IXP5-01", real_name="周报生P5",
                             current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(stu); db.flush()
        rec = InternshipRecord(
            tenant_id=TID, student_id=stu.id, advisor_user_id=mentor.id,
            advisor_name="实习P5导师", enterprise_name="企业", position_name="岗",
            status="ONBOARD", risk_level="NONE")
        db.add(rec); db.flush()
        w = WeeklyReport(tenant_id=TID, internship_id=rec.id, week_number=7, word_count=100,
                         work_content="工作内容足够十个字以上", harvest_content="收获内容足够十个字以上",
                         report_version=1, submitted_at=datetime.utcnow(), status="PENDING_REVIEW")
        db.add(w); db.flush()
        ix_todo.push_weekly_todo(db, w, rec)
        lv = InternshipLeave(
            tenant_id=TID, internship_id=rec.id, student_id=stu.id, leave_type="PERSONAL",
            start_date="2026-07-01", end_date="2026-07-02", days=2, reason="事假事由",
            status="PENDING", apply_by_name=stu.real_name)
        db.add(lv); db.flush()
        ix_todo.push_leave_todo(db, lv, rec)
        db.commit()
        wid, lid, mentor_uid = w.id, lv.id, mentor.id
    finally:
        db.close()

    db = get_sessionmaker()()
    try:
        assert db.query(UnifiedTodo).filter_by(
            todo_type=ix_todo.TODO_WEEKLY, source_biz_id=wid,
            assignee_id=mentor_uid, status="PENDING").count() == 1
        assert db.query(UnifiedTodo).filter_by(
            todo_type=ix_todo.TODO_LEAVE, source_biz_id=lid,
            assignee_id=mentor_uid, status="PENDING").count() == 1
    finally:
        db.close()

    h = _uid_token(mentor_uid, "INTERN_MENTOR", "实习P5导师", login_name="IX-M-P5")
    r = client.post(f"/api/v1/internship/reports/{wid}/review",
                    json={"action": "APPROVE", "comment": ""}, headers=h)
    assert r.status_code == 200 and r.json()["code"] == 0, r.text

    leave_svc.review({
        "userId": str(mentor_uid), "realName": "实习P5导师",
        "currentRoleCode": "INTERN_MENTOR", "userType": "TEACHER",
        "tenantId": str(TID), "loginName": "IX-M-P5"}, lid, "APPROVE", "")

    db = get_sessionmaker()()
    try:
        assert db.query(UnifiedTodo).filter_by(
            todo_type=ix_todo.TODO_WEEKLY, source_biz_id=wid).one().status == "DONE"
        assert db.query(UnifiedTodo).filter_by(
            todo_type=ix_todo.TODO_LEAVE, source_biz_id=lid).one().status == "DONE"
    finally:
        db.close()
