"""W7.6 runtime coverage for review todo and student reject outbox lifecycles."""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001


def test_w76_formal_review_todo_done_and_returned_reopen(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import GraduationMentor, GraduationReview, GraduationStudent, UnifiedTodo, User
    from app.modules.graduation.services import graduation_review_w76_lifecycle_service as w76

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        reviewer = User(
            tenant_id=TID,
            login_name="GD-W76-REVIEWER",
            real_name="W76评阅教师",
            password_hash="x",
            user_type="TEACHER",
            status="ACTIVE",
        )
        db.add(reviewer)
        db.flush()
        mentor = GraduationMentor(
            tenant_id=TID,
            teacher_no="GD-W76-REVIEWER",
            teacher_name="W76评阅教师",
            qualification_status="QUALIFIED",
            max_capacity=10,
        )
        db.add(mentor)
        db.flush()
        student = GraduationStudent(
            tenant_id=TID,
            student_id=976001,
            student_no="GD-W76-STU-01",
            name="W76评阅学生",
            stage="FINAL_REVIEW",
            eligibility_status="QUALIFIED",
        )
        db.add(student)
        db.flush()
        review = GraduationReview(
            tenant_id=TID,
            gd_student_id=student.id,
            gd_final_id=976001,
            reviewer_name=mentor.teacher_name,
            reviewer_mentor_id=mentor.id,
            status="ASSIGNED",
            assigned_at=datetime.utcnow(),
        )
        db.add(review)
        db.commit()
        review_id = int(review.id)
        reviewer_uid = int(reviewer.id)
    finally:
        db.close()

    try:
        assert w76._sync_formal_todo(review_id) is True
        db = get_sessionmaker()()
        try:
            row = db.query(UnifiedTodo).filter_by(
                tenant_id=TID,
                source_module="graduation",
                source_biz_id=review_id,
                todo_type=w76.TODO_FORMAL_REVIEW,
                assignee_id=reviewer_uid,
            ).one()
            assert row.status == "PENDING"
            assert "正式评阅待处理" in row.title
            initial_version = int(row.version or 0)
        finally:
            db.close()

        # Review Center reconciliation may run on read. Replaying an already-correct
        # projection must be a true no-op: no UPDATE and no artificial version drift.
        assert w76._sync_formal_todo(review_id) is False
        db = get_sessionmaker()()
        try:
            row = db.query(UnifiedTodo).filter_by(
                tenant_id=TID,
                source_module="graduation",
                source_biz_id=review_id,
                todo_type=w76.TODO_FORMAL_REVIEW,
                assignee_id=reviewer_uid,
            ).one()
            assert int(row.version or 0) == initial_version
            assert row.status == "PENDING"
        finally:
            db.close()

        assert w76._complete_formal_todo(review_id) == 1
        db = get_sessionmaker()()
        try:
            row = db.query(UnifiedTodo).filter_by(
                tenant_id=TID,
                source_module="graduation",
                source_biz_id=review_id,
                todo_type=w76.TODO_FORMAL_REVIEW,
                assignee_id=reviewer_uid,
            ).one()
            assert row.status == "DONE"
            review = db.get(GraduationReview, review_id)
            review.status = "RETURNED"
            db.commit()
        finally:
            db.close()

        assert w76._sync_formal_todo(review_id) is True
        db = get_sessionmaker()()
        try:
            rows = db.query(UnifiedTodo).filter_by(
                tenant_id=TID,
                source_module="graduation",
                source_biz_id=review_id,
                todo_type=w76.TODO_FORMAL_REVIEW,
                assignee_id=reviewer_uid,
            ).all()
            assert len(rows) == 1
            assert rows[0].status == "PENDING"
            assert "正式评阅退回重评" in rows[0].title
        finally:
            db.close()
    finally:
        set_tenant(None)


def test_w76_student_rejected_feedback_writes_one_outbox_not_direct_message(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent, MessageEventOutbox, StudentProfile, UnifiedMessage
    from app.models import graduation_review_evidence as _review_evidence  # noqa: F401
    from app.modules.graduation.services import graduation_review_feedback_service as feedback
    from app.modules.graduation.services.graduation_review_message_event_guard import EVENT_REVIEW_REJECTED

    source_id = 976101
    idem = "w76-runtime-rejected-976101"
    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        profile = StudentProfile(
            tenant_id=TID,
            student_no="GD-W76-MSG-01",
            real_name="W76消息学生",
            current_stage="GRADUATION",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(profile)
        db.flush()
        student = GraduationStudent(
            tenant_id=TID,
            student_id=profile.id,
            student_no=profile.student_no,
            name=profile.real_name,
            stage="FINAL_REVIEW",
            eligibility_status="QUALIFIED",
        )
        db.add(student)
        db.flush()
        gd_student_id = int(student.id)
        profile_id = int(profile.id)
        db.commit()
    finally:
        db.close()

    try:
        for _ in range(2):
            db = get_sessionmaker()()
            try:
                feedback.append_feedback_in_session(
                    db,
                    batch_id=None,
                    gd_student_id=gd_student_id,
                    stage="FINAL",
                    source_record_id=source_id,
                    material_id=976102,
                    file_version_id=976103,
                    source_sha256="a" * 64,
                    result="REJECTED",
                    summary="请根据评阅意见修改后重新提交。",
                    categories=["内容质量"],
                    issues=["结论与数据需对应"],
                    visible_to_student=True,
                    idempotency_key=idem,
                )
                db.commit()
            finally:
                db.close()

        db = get_sessionmaker()()
        try:
            outboxes = db.query(MessageEventOutbox).filter_by(
                tenant_id=TID,
                event_code=EVENT_REVIEW_REJECTED,
                source_biz_id=source_id,
            ).all()
            assert len(outboxes) == 1
            refs = outboxes[0].recipient_refs_json or []
            assert refs == [{"studentId": profile_id}]
            assert db.query(UnifiedMessage).filter_by(
                tenant_id=TID,
                source_module="graduation",
                source_biz_id=source_id,
            ).count() == 0
        finally:
            db.close()
    finally:
        set_tenant(None)


def test_w74_formal_review_read_returns_only_current_stable_reviewer_task(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import GraduationMentor, GraduationReview, GraduationStudent
    from app.modules.graduation.services import graduation_review_read_service as review_read

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        mine = GraduationMentor(
            tenant_id=TID,
            teacher_no="GD-W74-SCOPE-ME",
            teacher_name="W74评阅教师甲",
            qualification_status="QUALIFIED",
            max_capacity=10,
        )
        other = GraduationMentor(
            tenant_id=TID,
            teacher_no="GD-W74-SCOPE-OTHER",
            teacher_name="W74评阅教师乙",
            qualification_status="QUALIFIED",
            max_capacity=10,
        )
        db.add_all([mine, other])
        db.flush()
        student = GraduationStudent(
            tenant_id=TID,
            student_id=976201,
            student_no="GD-W74-SCOPE-STU",
            name="W74范围学生",
            stage="FINAL_REVIEW",
            eligibility_status="QUALIFIED",
        )
        db.add(student)
        db.flush()
        my_review = GraduationReview(
            tenant_id=TID,
            gd_student_id=student.id,
            gd_final_id=976201,
            reviewer_name=mine.teacher_name,
            reviewer_mentor_id=mine.id,
            status="ASSIGNED",
            assigned_at=datetime.utcnow(),
        )
        other_review = GraduationReview(
            tenant_id=TID,
            gd_student_id=student.id,
            gd_final_id=976201,
            reviewer_name=other.teacher_name,
            reviewer_mentor_id=other.id,
            status="ASSIGNED",
            assigned_at=datetime.utcnow(),
        )
        db.add_all([my_review, other_review])
        db.commit()
        student_id = int(student.id)
        my_review_id = int(my_review.id)
        other_review_id = int(other_review.id)
    finally:
        db.close()

    set_current_user({
        "tenantId": str(TID),
        "currentRoleCode": "GD_REVIEWER",
        "userType": "TEACHER",
        "loginName": "GD-W74-SCOPE-ME",
        "realName": "W74评阅教师甲",
    })
    try:
        rows, total = review_read.list_reviews(
            page=1,
            page_size=20,
            gd_student_id=student_id,
        )
        ids = {int(row["id"]) for row in rows}
        assert total == 1
        assert ids == {my_review_id}
        assert other_review_id not in ids

        stats = review_read.review_stats()
        by_status = {row["status"]: row["count"] for row in stats["byStatus"]}
        assert stats["total"] == 1
        assert by_status["ASSIGNED"] == 1
        assert sum(by_status.values()) == 1
    finally:
        set_current_user(None)
        set_tenant(None)
