"""INT MySQL/read-only contracts for Program workbook preview bridge."""
from __future__ import annotations

import ast
import inspect
import json
from io import BytesIO
from types import SimpleNamespace
import uuid

from openpyxl import load_workbook
import pytest
from sqlalchemy import event, select

TID = 1000000000000000001


def _service():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preview_service as service
    return service


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_workbook_adapter as adapter
    return adapter


def _patch_context(monkeypatch, service):
    monkeypatch.setattr(service, "_tid", lambda: TID)
    monkeypatch.setattr(
        service,
        "build_affairs_context",
        lambda _user, _db: SimpleNamespace(
            scope_type="TENANT_ALL",
            college_ids=set(),
            class_ids=set(),
        ),
    )


def _seed_authorities():
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, Major

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8].upper()
    major = Major(
        tenant_id=TID,
        college_id=881001,
        major_name=f"INT预览软件技术-{suffix}",
        code=f"PM{suffix}",
        status="ACTIVE",
        education_years=3,
        enroll_status="ENROLLING",
    )
    course = AaCourse(
        tenant_id=TID,
        course_code=f"PC{suffix}",
        course_name=f"INT预览程序设计-{suffix}",
        category="MAJOR_CORE",
        nature="REQUIRED",
        credit=3,
        exam_mode="EXAM",
        is_core=True,
        prerequisite_codes_json="[]",
        applicable_majors_json="[]",
        is_all_major=False,
        version=1,
        status="ENABLED",
    )
    db.add_all([major, course])
    db.commit()
    result = int(major.id), str(course.course_code), str(course.course_name)
    db.close()
    return result


def _workbook_bytes(*, major_id: int, course_code: str, series_key: str) -> bytes:
    content = _adapter().build_program_import_template()
    wb = load_workbook(BytesIO(content))
    for sheet_name in ("培养方案", "方案课程", "学分要求", "实践环节", "毕业要求", "适用范围"):
        wb[sheet_name]["A2"] = series_key
    wb["培养方案"]["D2"] = major_id
    wb["培养方案"]["C2"] = "INT软件技术2026培养方案"
    wb["方案课程"]["C2"] = course_code
    wb["适用范围"]["C2"] = major_id
    # PRACTICE is optional. Removing the sample keeps this fixture focused on
    # one exact Course credit + one graduation requirement.
    wb["实践环节"].delete_rows(2, 1)
    output = BytesIO()
    wb.save(output)
    wb.close()
    return output.getvalue()


def _capture_sql(engine):
    statements: list[str] = []

    def before_cursor_execute(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(str(statement))

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    return statements, before_cursor_execute


def _assert_read_only(statements):
    normalized = [" ".join(statement.upper().split()) for statement in statements]
    assert normalized
    assert all(" FOR UPDATE" not in statement for statement in normalized)
    forbidden = ("INSERT ", "UPDATE ", "DELETE ", "REPLACE ", "CREATE ", "ALTER ", "DROP ", "TRUNCATE ")
    assert all(not statement.startswith(forbidden) for statement in normalized)


def test_source_reject_returns_preview_without_opening_database(monkeypatch):
    service = _service()

    def forbidden_session():
        raise AssertionError("source-only reject must not open a DB session")

    monkeypatch.setattr(service, "session", forbidden_session)
    result = service.preview_program_normalized_rows([], phase="DEFINITION", user={})
    assert result["stage"] == "SOURCE"
    assert result["programPreflightSafe"] is False
    assert result["invalidRows"] == 1
    assert result["errors"][0]["code"] == "PROGRAM_SOURCE_EMPTY"


@pytest.mark.usefixtures("db_mode")
def test_definition_workbook_preview_is_real_db_read_only_and_creates_nothing(monkeypatch):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaProgram

    service = _service()
    _patch_context(monkeypatch, service)
    major_id, course_code, _course_name = _seed_authorities()
    series_key = f"INT-PREVIEW-{uuid.uuid4().hex[:12].upper()}"
    workbook = _workbook_bytes(
        major_id=major_id,
        course_code=course_code,
        series_key=series_key,
    )

    engine = get_engine()
    statements, listener = _capture_sql(engine)
    try:
        result = service.preview_program_workbook(
            workbook,
            phase="DEFINITION",
            user={"currentRoleCode": "ACADEMIC_ADMIN"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    _assert_read_only(statements)
    assert result["stage"] == "READY"
    assert result["phase"] == "DEFINITION"
    assert result["programPreflightSafe"] is True
    assert result["createPrograms"] == 1
    assert result["reusePrograms"] == 0
    assert result["normalizedRowCount"] == 5
    assert result["sheetRowCounts"]["PRACTICE"] == 0

    db = get_sessionmaker()()
    programs = db.scalars(select(AaProgram).where(
        AaProgram.tenant_id == TID,
        AaProgram.series_key == series_key,
        AaProgram.is_deleted.is_(False),
    )).all()
    db.close()
    assert programs == []


@pytest.mark.usefixtures("db_mode")
def test_binding_workbook_preview_reuses_published_definition_without_mutation(monkeypatch):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaProgram, AaProgramBinding, AaProgramCourse, AaProgramGraduationRequirement

    service = _service()
    _patch_context(monkeypatch, service)
    major_id, course_code, course_name = _seed_authorities()
    series_key = f"INT-BIND-PREVIEW-{uuid.uuid4().hex[:10].upper()}"
    workbook = _workbook_bytes(
        major_id=major_id,
        course_code=course_code,
        series_key=series_key,
    )

    db = get_sessionmaker()()
    from app.models import AaCourse
    course = db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == TID,
        AaCourse.course_code == course_code,
        AaCourse.version == 1,
        AaCourse.is_deleted.is_(False),
    )).one()
    program = AaProgram(
        tenant_id=TID,
        series_key=series_key,
        program_name="INT软件技术2026培养方案",
        major_id=major_id,
        grade_year="2026",
        total_credits=3,
        requirement_json=json.dumps({
            "creditStructure": [{"module": "MAJOR_CORE", "creditTarget": "3"}],
        }, ensure_ascii=False),
        version=1,
        status="PUBLISHED",
    )
    db.add(program)
    db.flush()
    db.add(AaProgramCourse(
        tenant_id=TID,
        program_id=program.id,
        course_id=course.id,
        course_name=course_name,
        open_term_no=1,
        module="MAJOR_CORE",
        credit_snapshot=3,
        formation_mode="ADMIN_FIXED",
    ))
    db.add(AaProgramGraduationRequirement(
        tenant_id=TID,
        program_id=program.id,
        category="ABILITY",
        content="完成专业综合项目并通过考核",
        sort_order=1,
        status="ACTIVE",
    ))
    db.commit()
    program_id = int(program.id)
    db.close()

    engine = get_engine()
    statements, listener = _capture_sql(engine)
    try:
        result = service.preview_program_workbook(
            workbook,
            phase="BINDING",
            user={"currentRoleCode": "ACADEMIC_ADMIN"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    _assert_read_only(statements)
    assert result["stage"] == "READY"
    assert result["phase"] == "BINDING"
    assert result["programPreflightSafe"] is True
    assert result["createPrograms"] == 0
    assert result["reusePrograms"] == 1

    db = get_sessionmaker()()
    persisted = db.get(AaProgram, program_id)
    bindings = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == TID,
        AaProgramBinding.program_id == program_id,
        AaProgramBinding.is_deleted.is_(False),
    )).all()
    db.close()
    assert persisted is not None and persisted.status == "PUBLISHED"
    assert bindings == []


def test_preview_bridge_has_no_writer_or_shared_dispatch_dependency():
    source = inspect.getsource(_service())
    for forbidden in (
        "with_for_update",
        "db.add",
        "db.flush",
        "db.commit",
        "confirm_program_definition_import",
        "confirm_program_binding_import",
        "data_exchange_confirm_service",
        "academic_file_exchange_service",
    ):
        assert forbidden not in source
    tree = ast.parse(source)
    forbidden_symbols = {"FileObject", "ImportJob"}
    assert not any(
        (isinstance(node, ast.Name) and node.id in forbidden_symbols)
        or (isinstance(node, ast.Attribute) and node.attr in forbidden_symbols)
        for node in ast.walk(tree)
    )
    assert "run_program_import_preflight" in source
    assert "program_preflight_to_file_exchange_preview" in source
    assert "parse_and_normalize_program_workbook" in source
