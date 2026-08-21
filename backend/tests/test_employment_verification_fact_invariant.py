"""W1/P0：就业核验结论不能跨 canonical 去向事实变化继续生效。

这组测试不经过 Student Portal / submission service，直接覆盖模型层 before_flush invariant，
证明教师 PC、批量命令或以后新增的 ORM 写入口只要修改 destination/company/job 任一事实，
旧 VERIFIED 就会 fail-closed；与去向无关的编辑则不会误伤核验结果。
"""
from __future__ import annotations

TID = 1000000000000000001


def _seed_verified():
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    db = get_sessionmaker()()
    try:
        row = EmpStudent(
            tenant_id=TID,
            student_no="INV-W1-001",
            name="核验不变量学生",
            destination_type="SIGNED",
            company_name="原单位",
            job_title="原岗位",
            verify_status="VERIFIED",
            material_status="APPROVED",
            help_level="NORMAL",
            risk_level="LOW",
            record_status="ACTIVE",
        )
        db.add(row)
        db.commit()
        return int(row.id)
    finally:
        db.close()


def test_fact_change_invalidates_verified_even_outside_submission_service(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id = _seed_verified()
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, emp_id)
        row.company_name = "新单位"
        db.commit()
        db.refresh(row)
        assert row.company_name == "新单位"
        assert row.verify_status == "PENDING_VERIFY"
    finally:
        db.close()


def test_job_title_change_also_invalidates_verified(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id = _seed_verified()
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, emp_id)
        row.job_title = "新岗位"
        db.commit()
        db.refresh(row)
        assert row.verify_status == "PENDING_VERIFY"
    finally:
        db.close()


def test_non_verification_fact_change_preserves_verified(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id = _seed_verified()
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, emp_id)
        row.follow_up_count = int(row.follow_up_count or 0) + 1
        db.commit()
        db.refresh(row)
        assert row.verify_status == "VERIFIED"
    finally:
        db.close()


def test_setting_verified_without_fact_change_is_not_self_invalidated(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id = _seed_verified()
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, emp_id)
        row.verify_status = "PENDING_VERIFY"
        db.commit()
        row.verify_status = "VERIFIED"
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        assert row.verify_status == "VERIFIED"
    finally:
        db.close()
