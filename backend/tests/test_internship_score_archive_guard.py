"""包 7 第一组：成绩冻结、归档后禁止撤回、归档/撤回真实并发。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from threading import Barrier

TID = 1000000000000000001
INT = "/api/v1/internship"


def _admin(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from uuid import uuid4

    from app.db.session import get_sessionmaker
    from app.models import (
        EmpCompany, InternshipAgreement, InternshipBatch, InternshipCheckin,
        InternshipEnterpriseEval, InternshipFinalScore, InternshipGuidance,
        InternshipInsurance, InternshipPosition, InternshipRecord,
        InternshipStudentEval, StudentProfile, WeeklyReport,
    )

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="成绩归档并发测试批次",
            batch_no=f"SCORE-ARCHIVE-{uuid4().hex[:8]}",
            status="RUNNING",
            planned_count=1,
            end_date=date.today(),
            rules_config={"compliance": {"studentConsent": {
                "requireGuardianConsentForMinor": False,
            }}},
        )
        db.add(batch)
        db.flush()
        company = EmpCompany(
            tenant_id=TID,
            name="成绩归档并发测试企业",
            credit_code=f"91310000SA{uuid4().hex[:6].upper()}",
            coop_status="ACTIVE",
        )
        db.add(company)
        db.flush()
        position = InternshipPosition(
            tenant_id=TID,
            company_id=company.id,
            company_name=company.name,
            title="实习生",
            batch_id=batch.id,
            status="PUBLISHED",
            headcount=1,
        )
        db.add(position)
        db.flush()
        student = StudentProfile(
            tenant_id=TID,
            student_no=f"SA-{uuid4().hex[:8]}",
            real_name="成绩归档学生",
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            advisor_name="成绩归档老师",
            enterprise_name=company.name,
            position_name=position.title,
            enterprise_id=company.id,
            position_id=position.id,
            eligibility_status="QUALIFIED",
            status="ASSESSING",
            risk_level="NONE",
            batch_id=batch.id,
            version=0,
        )
        db.add(record)
        db.flush()
        db.add_all([
            InternshipInsurance(
                tenant_id=TID, internship_id=record.id,
                student_id=student.id, status="VERIFIED"),
            InternshipAgreement(
                tenant_id=TID, internship_id=record.id,
                student_id=student.id, status="EFFECTIVE"),
            InternshipCheckin(
                tenant_id=TID, internship_id=record.id,
                checkin_date="2026-07-01", checkin_at=datetime.utcnow(),
                result="NORMAL"),
            WeeklyReport(
                tenant_id=TID, internship_id=record.id,
                week_number=1, word_count=800, report_version=1,
                submitted_at=datetime.utcnow(), status="APPROVED"),
            InternshipEnterpriseEval(
                tenant_id=TID, internship_id=record.id,
                student_id=student.id, mentor_name="企业导师",
                attendance_score=90, skill_score=90, attitude_score=90,
                collaboration_score=90, safety_score=90,
                school_review_status="APPROVED"),
            InternshipStudentEval(
                tenant_id=TID, internship_id=record.id,
                student_id=student.id, self_summary="完整自评",
                submit_status="SUBMITTED"),
            InternshipGuidance(
                tenant_id=TID, internship_id=record.id,
                student_id=student.id, content="完整指导", status="NORMAL"),
        ])
        score = InternshipFinalScore(
            tenant_id=TID,
            internship_id=record.id,
            student_id=student.id,
            batch_id=batch.id,
            checkin_score=90,
            weekly_score=88,
            monthly_score=86,
            enterprise_score=92,
            school_score=94,
            w_checkin=20,
            w_weekly=20,
            w_monthly=10,
            w_enterprise=30,
            w_school=20,
            total_score=90.4,
            pass_line=60,
            is_pass=True,
            incomplete=False,
            status="PUBLISHED",
            score_config_version=2,
            published_by_name="学校管理员",
            published_at=datetime.utcnow(),
            version=3,
        )
        db.add(score)
        db.commit()
        return {
            "record": record.id,
            "recordVersion": int(record.version or 0),
            "score": score.id,
            "scoreVersion": int(score.version or 0),
        }
    finally:
        db.close()


def test_total_archive_freezes_published_score_and_blocks_direct_withdraw(client, db_mode):
    ids = _seed(db_mode)
    headers = _admin(client)
    archived = client.post(
        f"{INT}/archive/{ids['record']}/archive",
        json={"expectedVersion": ids["recordVersion"]},
        headers=headers,
    )
    assert archived.status_code == 200, archived.json()
    data = archived.json()["data"]
    assert data["finalScoreId"] == str(ids["score"])
    assert data["finalScoreVersion"] == ids["scoreVersion"]
    assert len(data["finalScoreFreezeHash"]) == 64

    from app.db.session import get_sessionmaker
    from app.models import InternshipArchive

    db = get_sessionmaker()()
    try:
        row = db.query(InternshipArchive).filter_by(
            tenant_id=TID, internship_id=ids["record"]).one()
        snapshot = row.material_snapshot
        assert snapshot["finalScoreFreeze"]["scoreId"] == str(ids["score"])
        assert snapshot["finalScoreFreeze"]["status"] == "PUBLISHED"
        assert snapshot["finalScoreFreeze"]["totalScore"] == 90.4
        assert snapshot["finalScoreFreezeHash"] == data["finalScoreFreezeHash"]
    finally:
        db.close()

    denied = client.post(
        f"{INT}/scores/{ids['score']}/withdraw",
        json={
            "reason": "归档完成后尝试直接撤回成绩",
            "expectedVersion": ids["scoreVersion"],
        },
        headers=headers,
    )
    assert denied.status_code == 409
    assert "档案已归档" in denied.json()["message"]


def test_archive_and_withdraw_race_only_one_can_commit(client, db_mode):
    ids = _seed(db_mode)
    headers = _admin(client)
    barrier = Barrier(2)

    def do_archive():
        barrier.wait()
        return client.post(
            f"{INT}/archive/{ids['record']}/archive",
            json={"expectedVersion": ids["recordVersion"]},
            headers=headers,
        )

    def do_withdraw():
        barrier.wait()
        return client.post(
            f"{INT}/scores/{ids['score']}/withdraw",
            json={
                "reason": "并发竞争撤回正式实习成绩",
                "expectedVersion": ids["scoreVersion"],
            },
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        archive_future = pool.submit(do_archive)
        withdraw_future = pool.submit(do_withdraw)
        responses = [archive_future.result(), withdraw_future.result()]

    assert sorted(response.status_code for response in responses) == [200, 409], [
        (response.status_code, response.text) for response in responses
    ]

    from app.db.session import get_sessionmaker
    from app.models import InternshipArchive, InternshipFinalScore

    db = get_sessionmaker()()
    try:
        score = db.get(InternshipFinalScore, ids["score"])
        archive = db.query(InternshipArchive).filter_by(
            tenant_id=TID, internship_id=ids["record"]).first()
        impossible = bool(
            archive and archive.status == "ARCHIVED"
            and score.status == "WITHDRAWN"
        )
        assert impossible is False
        assert (
            (archive and archive.status == "ARCHIVED" and score.status == "PUBLISHED")
            or (archive is None and score.status == "WITHDRAWN")
        )
    finally:
        db.close()
