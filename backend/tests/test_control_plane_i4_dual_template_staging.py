from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import delete, func, select

from app.db.session import get_sessionmaker
from app.models.data_exchange import IdentityImportStagingRow
from app.services.identity_import_file_service import STUDENT_HEADERS, TEACHER_HEADERS
from app.services.identity_import_staging_service import stage_identity_xlsx

TENANT_ID = 94761
ACTOR_ID = 9476101


def _write(path: Path, headers, row: dict) -> None:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("导入模板")
    sheet.append(list(headers))
    sheet.append([row.get(header, "") for header in headers])
    workbook.save(path)
    workbook.close()


def _clear():
    db = get_sessionmaker()()
    try:
        db.execute(delete(IdentityImportStagingRow).where(IdentityImportStagingRow.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()


def test_real_student_and_teacher_xlsx_use_same_normalized_staging_authority(db_mode, tmp_path):
    _clear()
    student = tmp_path / "students.xlsx"
    teacher = tmp_path / "teachers.xlsx"
    _write(student, STUDENT_HEADERS, {
        "学号": "I4S000001",
        "姓名": "I4学生",
        "所属学院": "信息学院",
        "所属专业": "软件技术",
        "班级名称": "软件2601",
        "年级": "2026",
        "性别": "男",
        "身份证号": "",
    })
    _write(teacher, TEACHER_HEADERS, {
        "工号": "I4T000001",
        "姓名": "I4教师",
        "所属部门": "信息学院",
        "岗位名称": "专任教师",
        "预设角色编码": "ACADEMIC_TEACHER",
        "数据范围类型": "",
        "数据范围引用": "",
    })

    student_result = stage_identity_xlsx(
        path=student,
        filename=student.name,
        kind="STUDENT",
        tenant_id=TENANT_ID,
        job_id=94761001,
        actor_id=ACTOR_ID,
    )
    teacher_result = stage_identity_xlsx(
        path=teacher,
        filename=teacher.name,
        kind="TEACHER",
        tenant_id=TENANT_ID,
        job_id=94761002,
        actor_id=ACTOR_ID,
    )
    assert student_result["totalRows"] == 1
    assert teacher_result["totalRows"] == 1
    assert student_result["kind"] == "STUDENT"
    assert teacher_result["kind"] == "TEACHER"
    assert len(student_result["fileSha256"]) == 64
    assert len(teacher_result["fileSha256"]) == 64

    db = get_sessionmaker()()
    try:
        counts = {
            entity: int(db.scalar(select(func.count(IdentityImportStagingRow.id)).where(
                IdentityImportStagingRow.tenant_id == TENANT_ID,
                IdentityImportStagingRow.entity_type == entity,
                IdentityImportStagingRow.is_deleted.is_(False),
            )) or 0)
            for entity in ("STUDENT", "TEACHER")
        }
        assert counts == {"STUDENT": 1, "TEACHER": 1}
    finally:
        db.close()
        _clear()
