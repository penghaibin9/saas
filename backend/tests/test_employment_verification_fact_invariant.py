"""W1/P0：就业核验结论不能跨 canonical 去向事实变化继续生效。

这组测试不经过 Student Portal / submission service，直接覆盖模型层 before_flush invariant，
证明教师 PC、批量命令或以后新增的 ORM 写入口只要修改 destination/company/job/signDate
任一核验事实，旧 VERIFIED 就会 fail-closed 且事实版本前进；与去向无关的编辑则不会
误伤核验结果。
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
            sign_date="2026-06-01",
            verify_status="VERIFIED",
            material_status="APPROVED",
            help_level="NORMAL",
            risk_level="LOW",
            record_status="ACTIVE",
        )
        db.add(row)
        db.commit()
        return int(row.id), int(row.version or 0)
    finally:
        db.close()


def test_fact_change_invalidates_verified_and_advances_version_outside_submission_service(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id, old_version = _seed_verified()
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, emp_id)
        row.company_name = "新单位"
        db.commit()
        db.refresh(row)
        assert row.company_name == "新单位"
        assert row.verify_status == "PENDING_VERIFY"
        assert int(row.version or 0) == old_version + 1
    finally:
        db.close()


def test_job_title_change_also_invalidates_verified(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id, old_version = _seed_verified()
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, emp_id)
        row.job_title = "新岗位"
        db.commit()
        db.refresh(row)
        assert row.verify_status == "PENDING_VERIFY"
        assert int(row.version or 0) == old_version + 1
    finally:
        db.close()


def test_sign_date_change_invalidates_verified_and_document_fact_version(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id, old_version = _seed_verified()
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, emp_id)
        row.destination_document_source_version = old_version
        db.commit()
        row.sign_date = "2026-07-01"
        db.commit()
        db.refresh(row)
        assert row.sign_date == "2026-07-01"
        assert row.verify_status == "PENDING_VERIFY"
        assert int(row.version or 0) == old_version + 1
        assert int(row.destination_document_source_version or 0) != int(row.version or 0)
    finally:
        db.close()


def test_non_verification_fact_change_preserves_verified(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id, old_version = _seed_verified()
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, emp_id)
        row.follow_up_count = int(row.follow_up_count or 0) + 1
        db.commit()
        db.refresh(row)
        assert row.verify_status == "VERIFIED"
        # 模型 invariant 不替普通业务字段擅自维护版本；由对应 command 自己决定。
        assert int(row.version or 0) == old_version
    finally:
        db.close()


def test_setting_verified_without_fact_change_is_not_self_invalidated(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    emp_id, _old_version = _seed_verified()
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
