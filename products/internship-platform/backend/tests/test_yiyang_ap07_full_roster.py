"""Yiyang AP07 complete internship roster and Excel truth acceptance."""
from __future__ import annotations

import base64
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

TID = 1000000000000000001
ADMIN = {
    "tenantId": str(TID), "userId": "9001", "realName": "AP07管理员",
    "userType": "SCHOOL_ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
}


@pytest.fixture()
def ap07_db(tmp_path):
    import app.db.session as db_session
    from app.config import settings
    from app.models import (
        College, InternshipAgreement, InternshipApplication, InternshipBatch,
        InternshipPayrollStatement, InternshipPayrollVersion, InternshipRecord,
        InternshipRotation, Major, SchoolClass, StudentProfile,
    )

    old = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite+pysqlite:///{(tmp_path / 'ap07.db').as_posix()}"
    db_session._engine = None
    db_session._factory = None
    engine = db_session.get_engine()
    for table in (
        College.__table__, Major.__table__, SchoolClass.__table__,
        InternshipBatch.__table__, StudentProfile.__table__, InternshipRecord.__table__,
        InternshipApplication.__table__, InternshipAgreement.__table__,
        InternshipRotation.__table__,
        InternshipPayrollStatement.__table__, InternshipPayrollVersion.__table__,
    ):
        table.create(bind=engine, checkfirst=True)
    try:
        yield
    finally:
        engine.dispose()
        settings.DATABASE_URL = old
        db_session._engine = None
        db_session._factory = None


def _seed():
    from app.db.session import get_sessionmaker
    from app.models import (
        College, InternshipAgreement, InternshipApplication, InternshipBatch,
        InternshipPayrollStatement, InternshipPayrollVersion, InternshipRecord,
        InternshipRotation, Major, SchoolClass, StudentProfile,
    )

    db = get_sessionmaker()()
    try:
        college = College(tenant_id=TID, college_name="信息工程学院", code="IT", status="ACTIVE")
        db.add(college); db.flush()
        major = Major(
            tenant_id=TID, college_id=college.id, major_name="软件技术", code="510203",
            status="ACTIVE", education_years=3, training_level="HIGHER", enroll_status="ENROLLING",
        )
        db.add(major); db.flush()
        cls = SchoolClass(
            tenant_id=TID, major_id=major.id, class_name="软件2401班", grade="2024", status="ACTIVE"
        )
        db.add(cls); db.flush()
        batch = InternshipBatch(
            tenant_id=TID, batch_name="益阳AP07实习批次", batch_no="YIYANG-AP07",
            start_date=datetime(2026, 9, 1), end_date=datetime(2027, 1, 31),
            planned_count=2, status="RUNNING",
        )
        db.add(batch); db.flush()

        students = []
        records = []
        for index in (1, 2):
            student = StudentProfile(
                tenant_id=TID, student_no=f"AP07-{index:03d}", real_name=f"AP07学生{index}",
                college_id=college.id, major_id=major.id, class_id=cls.id, grade="2024",
                current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE",
            )
            db.add(student); db.flush()
            record = InternshipRecord(
                tenant_id=TID, student_id=student.id, batch_id=batch.id,
                enterprise_name="益阳智造科技有限公司" if index == 1 else "益阳数据服务有限公司",
                position_name="软件测试实习生" if index == 1 else "数据助理",
                advisor_name="李老师", advisor_user_id=7001,
                eligibility_status="QUALIFIED", destination_type="SELF_ARRANGED",
                status="ONBOARD", risk_level="NONE",
                intern_start_date=datetime(2026, 9, 1), intern_end_date=datetime(2027, 1, 31),
            )
            db.add(record); db.flush()
            students.append(student); records.append(record)

        record, student = records[0], students[0]
        app = InternshipApplication(
            tenant_id=TID, record_id=record.id, student_id=student.id, batch_id=batch.id,
            campaign_id=None, application_type="SELF_ARRANGED", volunteer_no=1,
            company_name=record.enterprise_name, position_name=record.position_name,
            company_credit_code="91430900MA4L123456",
            company_nature="民营企业", company_industry="软件和信息技术服务业",
            company_registered_address="湖南省益阳市赫山区注册地址1号",
            work_country="中国", work_province="湖南省", work_city="益阳市", work_district="赫山区",
            internship_department="质量保障部", position_category="技术类",
            major_match=True, agreed_salary=Decimal("3500.00"),
            registry_verification_status="UNVERIFIED",
            status="APPROVED", reviewed_by_name="AP07管理员",
            reviewed_at=datetime(2026, 8, 25, 10, 0),
        )
        db.add(app)
        db.add(InternshipAgreement(
            tenant_id=TID, internship_id=record.id, student_id=student.id, batch_id=batch.id,
            enterprise_name=record.enterprise_name, position_name=record.position_name,
            student_confirm_status="CONFIRMED", enterprise_confirm_status="CONFIRMED",
            school_confirm_status="CONFIRMED", status="EFFECTIVE",
            file_id="9001001", source_type="FILE_EVIDENCE",
        ))
        db.add_all([
            InternshipRotation(
                tenant_id=TID, internship_id=record.id, student_id=student.id, batch_id=batch.id,
                rotation_seq=1, department_name="生产一部", mentor_name="王师傅",
                start_date=datetime(2026, 9, 1).date(), end_date=datetime(2026, 9, 30).date(),
                status="COMPLETED", total_score=Decimal("86.50"),
            ),
            InternshipRotation(
                tenant_id=TID, internship_id=record.id, student_id=student.id, batch_id=batch.id,
                rotation_seq=2, department_name="质量二部", mentor_name="赵师傅",
                start_date=datetime(2026, 10, 1).date(), end_date=datetime(2026, 10, 31).date(),
                status="COMPLETED", total_score=Decimal("75.50"),
            ),
        ])
        statement = InternshipPayrollStatement(
            tenant_id=TID, internship_id=record.id, student_id=student.id, batch_id=batch.id,
            pay_month="2026-10", agreed_salary_snapshot=Decimal("3500.00"),
            agreed_salary_currency="CNY", revision_count=2,
        )
        db.add(statement); db.flush()
        payroll = InternshipPayrollVersion(
            tenant_id=TID, statement_id=statement.id, revision_no=2,
            actual_amount=Decimal("3300.00"), currency="CNY",
            status="APPROVED", is_current=True, submitted_at=datetime(2026, 10, 31, 18, 0),
        )
        db.add(payroll); db.flush(); statement.current_version_id = payroll.id
        db.commit()
        return batch.id, record.id
    finally:
        db.close()


def test_ap07_page_and_full_excel_share_same_canonical_fields_and_export_all_rows(ap07_db):
    from app.core.context import set_current_user, set_tenant
    from app.modules.internship.services import internship_student_service as service

    set_tenant({"tenantId": str(TID)})
    set_current_user(ADMIN)
    batch_id, record_id = _seed()

    page, total = service.list_students(
        1, 1, batch_id=batch_id, user=ADMIN)
    assert total == 2
    assert len(page) == 1

    # Production sorting is updated_at/id descending; do not force fixture id=1
    # to be the first visible row. Locate the rich-fact student from the full
    # two-row service result while separately proving pageSize=1 is respected.
    full_rows, full_total = service.list_students(
        1, 2, batch_id=batch_id, user=ADMIN)
    assert full_total == 2
    row = next(item for item in full_rows if item["id"] == str(record_id))
    assert row["collegeName"] == "信息工程学院"
    assert row["majorName"] == "软件技术"
    assert row["sourceRegion"] == "未采集"
    assert row["companyCreditCode"] == "91430900MA4L123456"
    assert row["companyNature"] == "民营企业"
    assert row["companyIndustry"] == "软件和信息技术服务业"
    assert row["workCity"] == "益阳市"
    assert row["internshipDepartment"] == "质量保障部"
    assert row["positionCategory"] == "技术类"
    assert row["majorMatch"] is True
    assert row["majorMatchLabel"] == "对口"
    assert row["agreedSalary"] == 3500.0
    assert row["agreementStatus"] == "EFFECTIVE"
    assert row["rotationCount"] == 2
    assert "生产一部 86.5分" in row["rotationScoreSummary"]
    assert "质量二部 75.5分" in row["rotationScoreSummary"]
    assert row["latestPayrollMonth"] == "2026-10"
    assert row["latestActualSalary"] == 3300.0
    assert row["latestActualSalaryCurrency"] == "CNY"

    exported = service.export_students(batch_id=batch_id, user=ADMIN)
    assert exported["rowCount"] == 2
    assert exported["exportedRows"] == 2
    assert exported["sourceTotal"] == 2

    workbook = load_workbook(BytesIO(base64.b64decode(exported["contentBase64"])))
    sheet = workbook.active
    headers = [cell.value for cell in sheet[2]]
    expected_headers = [
        "学号", "姓名", "年级", "学院", "专业", "班级", "生源地", "实习批次",
        "校内指导教师", "企业名称", "统一社会信用代码", "单位性质", "行业分类",
        "企业注册地址", "实际工作国家/地区", "实际工作省份", "实际工作城市", "实际工作区县",
        "实习部门", "岗位名称", "岗位类别", "专业对口", "约定报酬", "约定报酬币种",
        "工商核验状态", "三方协议状态", "轮岗次数", "轮岗成绩", "最近工资月份",
        "最近实发工资", "实发工资币种", "实习状态", "实习资格", "实习去向", "风险",
    ]
    assert headers == expected_headers

    header_to_col = {value: index + 1 for index, value in enumerate(headers)}
    values = {
        header: sheet.cell(row=3, column=column).value
        for header, column in header_to_col.items()
    }
    assert values["统一社会信用代码"] == "91430900MA4L123456"
    assert sheet.cell(row=3, column=header_to_col["统一社会信用代码"]).data_type == "s"
    assert values["约定报酬"] == 3500
    assert values["专业对口"] == "对口"
    assert values["三方协议状态"] == "EFFECTIVE"
    assert values["轮岗次数"] == 2
    assert "生产一部 86.5分" in values["轮岗成绩"]
    assert values["最近实发工资"] == 3300
    assert values["生源地"] == "未采集"

    # Export must not be truncated to the first UI page.
    assert sheet.max_row == 4  # watermark + header + 2 data rows


def test_ap07_pc_view_has_compact_full_toggle_and_column_configuration():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    view = (
        root / "admin-web/src/modules/internship/views/InternshipStudentListView.vue"
    ).read_text(encoding="utf-8")
    assert "完整一览表" in view
    assert "selectedFullColumnKeys" in view
    assert "统一社会信用代码" in view
    assert "轮岗成绩" in view
    assert "最近实发工资" in view
    assert "生源地暂无独立来源时明确显示“未采集”" in view
