"""Position publishing: real MySQL version races, tenant boundary and rights checks."""
import threading
import uuid
import pytest

TENANT = 1000000000000000001

def context(tenant=TENANT):
    from app.core.context import set_tenant, set_current_user
    set_tenant({"tenantId": str(tenant)})
    set_current_user({"userId": "1", "tenantId": str(tenant), "realName": "岗位验收",
                      "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN"})

def session():
    from app.db.session import get_sessionmaker
    return get_sessionmaker()()

@pytest.fixture
def position(db_mode):
    from app.models import EmpCompany, InternshipBatch, InternshipPosition
    from app.modules.internship.services import internship_position_service as service
    context()
    with session() as db:
        company = EmpCompany(tenant_id=TENANT, name="虚构岗位验收企业", coop_status="ACTIVE", qualification_status="PASSED")
        batch = InternshipBatch(tenant_id=TENANT, batch_name="岗位验收批次", batch_no=uuid.uuid4().hex, status="RUNNING")
        db.add_all([company, batch]); db.flush()
        row = InternshipPosition(tenant_id=TENANT, company_id=company.id, company_name=company.name,
            batch_id=batch.id, title="虚构验收岗位", status="DRAFT", headcount=3,
            work_content="指导下记录与复盘", daily_hours=8, weekly_hours=40, night_shift=False,
            overtime_allowed=False, rest_days_per_week=2, remuneration_type="MONTHLY",
            remuneration_amount=2000, remuneration_cycle="MONTHLY", accommodation_provided=False,
            meal_provided=True, hazardous_flag=False)
        db.add(row); db.commit()
        position_id = str(row.id)
    return service, service.get_position(position_id)

def test_full_publish_risk_loop_and_stale_editor(position):
    from app.core.exceptions import AppException
    from app.modules.internship.schemas.internship_position import PositionUpdate
    svc, row = position
    submitted = svc.set_status(row["id"], "SUBMIT", expected_version=row["version"])
    assert submitted["version"] == row["version"] + 1
    with pytest.raises(AppException) as conflict:
        svc.update_position(row["id"], PositionUpdate(expectedVersion=row["version"], title="旧窗口覆盖"))
    assert conflict.value.http_status == 409
    published = svc.set_status(row["id"], "PUBLISH", expected_version=submitted["version"])
    assert published["status"] == "PUBLISHED"
    assert published["batchName"] == "岗位验收批次"
    assert published["sourceType"] == "SCHOOL" and published["campaignId"] == ""
    risk = svc.mark_risk(row["id"], True, "复核现场情况", expected_version=published["version"])
    with pytest.raises(AppException):
        svc.set_status(row["id"], "OFFLINE", expected_version=published["version"])
    cleared = svc.mark_risk(row["id"], False, expected_version=risk["version"])
    assert cleared["status"] == "OFFLINE" and not cleared["riskFlag"]
    with pytest.raises(AppException):
        svc.mark_risk(row["id"], False, expected_version=cleared["version"])
    assert svc.get_position(row["id"])["version"] == cleared["version"]

def test_publish_with_unknown_rights_rolls_back(position):
    from app.core.exceptions import AppException
    from app.modules.internship.schemas.internship_position import PositionUpdate
    svc, row = position
    updated = svc.update_position(row["id"], PositionUpdate(expectedVersion=row["version"], dailyHours=None))
    pending = svc.set_status(row["id"], "SUBMIT", expected_version=updated["version"])
    with pytest.raises(AppException):
        svc.set_status(row["id"], "PUBLISH", expected_version=pending["version"])
    latest = svc.get_position(row["id"])
    assert latest["status"] == "PENDING" and latest["version"] == pending["version"]
    assert any(issue["field"] == "dailyHours" for issue in latest["compliance"]["unknowns"])

def test_concurrent_status_and_risk_have_one_winner(position):
    from app.core.exceptions import AppException
    from sqlalchemy import select, func
    from app.models import InternshipAuditTrail
    svc, row = position
    barrier = threading.Barrier(2)
    results = []
    def run(risk):
        context(); barrier.wait(timeout=10)
        try:
            if risk: svc.mark_risk(row["id"], True, "并发核验", expected_version=row["version"])
            else: svc.set_status(row["id"], "SUBMIT", expected_version=row["version"])
            results.append(200)
        except AppException as exc:
            results.append(exc.http_status)
    threads = [threading.Thread(target=run, args=(risk,)) for risk in [True, False]]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=20)
    assert all(not thread.is_alive() for thread in threads)
    assert sorted(results) == [200, 409]
    context()
    assert svc.get_position(row["id"])["version"] == row["version"] + 1
    with session() as db:
        assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(
            InternshipAuditTrail.target_type == "POSITION", InternshipAuditTrail.target_id == int(row["id"]))) == 1

def test_foreign_tenant_cannot_change_status_or_risk(position):
    from app.core.exceptions import AppException
    svc, row = position
    context(TENANT + 1)
    for operation in [lambda: svc.set_status(row["id"], "SUBMIT", expected_version=row["version"]),
                      lambda: svc.mark_risk(row["id"], True, "越界", expected_version=row["version"])]:
        with pytest.raises(AppException) as missing: operation()
        assert missing.value.http_status == 404
    context()
    assert svc.get_position(row["id"])["version"] == row["version"]


def test_position_read_permission_does_not_expose_another_advisors_students(position):
    from app.models import InternshipRecord, StudentProfile
    svc, row = position
    with session() as db:
        for advisor in (9001, 9002):
            student = StudentProfile(tenant_id=TENANT, student_no='POS-SCOPE-'+uuid.uuid4().hex[:10],
                                     real_name=f'虚构学生{advisor}', current_stage='INTERN', status='ACTIVE')
            db.add(student); db.flush()
            db.add(InternshipRecord(tenant_id=TENANT, student_id=student.id, batch_id=int(row['batchId']),
                                    position_id=int(row['id']), advisor_user_id=advisor, status='PREPARING'))
        db.commit()
    admin = svc.get_position(row['id'], user={'currentRoleCode':'SCHOOL_ADMIN','userId':'1','userType':'ADMIN'})
    assert len(admin['assignedStudents']) == 2
    mentor = svc.get_position(row['id'], user={'currentRoleCode':'INTERN_MENTOR','userId':'9001','userType':'TEACHER'})
    assert [student['name'] for student in mentor['assignedStudents']] == ['虚构学生9001']
    assert mentor['assignedCount'] == 1
    unassigned = svc.get_position(row['id'], user={'currentRoleCode':'INTERN_MENTOR','userId':'9003','userType':'TEACHER'})
    assert unassigned['assignedStudents'] == [] and unassigned['assignedCount'] == 0
    assert (mentor['id'], mentor['title'], mentor['headcount']) == (admin['id'], admin['title'], admin['headcount'])
