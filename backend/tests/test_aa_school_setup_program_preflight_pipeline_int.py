"""Targeted INT contract for the local Program preflight pipeline."""
from __future__ import annotations

import inspect
from decimal import Decimal


def _pipeline():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preflight_pipeline as pipeline
    return pipeline


def _rows(*, include_binding=False, class_binding=False):
    program_key = "SERIES:SER-A:v1"
    rows = [
        {
            "rowNo": 2,
            "logicalGroup": "MAIN",
            "programKey": program_key,
            "definitionKey": program_key,
            "payload": {
                "programSeriesKey": "SER-A",
                "programVersion": 1,
                "programName": "软件技术 2026 培养方案",
                "majorId": 1,
                "gradeYear": "2026",
                "totalCredits": Decimal("3.0"),
                "educationYearsAssertion": 3,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "COURSE",
            "programKey": program_key,
            "definitionKey": f"{program_key}|COURSE|CS101@v1",
            "payload": {
                "programKey": program_key,
                "courseKey": "CS101@v1",
                "module": "专业核心",
                "formationMode": "ADMIN_FIXED",
                "openTermNo": 1,
                "creditSnapshot": None,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "programKey": program_key,
            "definitionKey": f"{program_key}|CREDIT|专业核心",
            "payload": {
                "programKey": program_key,
                "module": "专业核心",
                "creditTarget": Decimal("3.0"),
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "GRADUATION",
            "programKey": program_key,
            "definitionKey": f"{program_key}|GRADUATION|KNOWLEDGE|掌握程序设计基础",
            "payload": {
                "programKey": program_key,
                "category": "KNOWLEDGE",
                "content": "掌握程序设计基础",
                "sortOrder": 0,
            },
        },
    ]
    if include_binding:
        payload = {
            "programKey": program_key,
            "majorId": 1,
            "gradeYear": "2026",
            "bindingScope": "CLASS" if class_binding else "MAJOR_GRADE",
            "classId": 77 if class_binding else None,
        }
        scope_key = "CLASS:77" if class_binding else "MAJOR_GRADE"
        rows.append({
            "rowNo": 2,
            "logicalGroup": "BINDING",
            "programKey": program_key,
            "definitionKey": f"{program_key}|BINDING|{scope_key}",
            "payload": payload,
        })
    return rows


def _course_snapshots():
    return [{
        "courseId": 101,
        "courseCode": "CS101",
        "version": 1,
        "status": "ENABLED",
        "credit": Decimal("3.0"),
    }]


def _program_snapshots():
    return [{
        "programId": 501,
        "seriesKey": "SER-A",
        "version": 1,
        "prevVersionId": None,
        "programName": "软件技术 2026 培养方案",
        "majorId": 1,
        "gradeYear": "2026",
        "totalCredits": Decimal("3.0"),
        "status": "PUBLISHED",
    }]


def _existing_definitions():
    return [
        {
            "programId": 501,
            "logicalGroup": "COURSE",
            "payload": {
                "courseKey": "CS101@v1",
                "module": "专业核心",
                "formationMode": "ADMIN_FIXED",
                "openTermNo": 1,
                "creditSnapshot": Decimal("3.0"),
            },
        },
        {
            "programId": 501,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "payload": {"module": "专业核心", "creditTarget": Decimal("3.0")},
        },
        {
            "programId": 501,
            "logicalGroup": "GRADUATION",
            "payload": {
                "category": "KNOWLEDGE",
                "content": "掌握程序设计基础",
                "sortOrder": 0,
            },
        },
    ]


def _loaders(calls, *, programs=(), definitions=(), class_rows=(), status=None, active=()):
    def scope_loader():
        calls.append(("scope", ()))
        return None

    def keyed_loader(name, value):
        def _load(keys):
            calls.append((name, tuple(keys)))
            return value
        return _load

    return {
        "load_allowed_major_ids": scope_loader,
        "load_major_snapshots": keyed_loader(
            "major", [{"majorId": 1, "educationYears": 3, "status": "ACTIVE"}]
        ),
        "load_class_snapshots": keyed_loader("class", list(class_rows)),
        "load_course_snapshots": keyed_loader("course", _course_snapshots()),
        "load_program_snapshots": keyed_loader("program", list(programs)),
        "load_existing_definition_rows": keyed_loader("definitions", list(definitions)),
        "load_program_status_by_id": keyed_loader("status", dict(status or {})),
        "load_active_binding_snapshots": keyed_loader("active_binding", list(active)),
    }


def test_source_blocker_short_circuits_every_snapshot_loader():
    calls = []
    rows = [_rows()[0]]
    result = _pipeline().run_program_import_preflight(
        rows,
        phase="DEFINITION",
        **_loaders(calls),
    )
    assert result["stage"] == "SOURCE"
    assert result["programPreflightSafe"] is False
    assert result["requestKeys"] == {}
    assert calls == []
    assert {item["businessCode"] for item in result["errors"]} >= {
        "PROGRAM_COURSE_EMPTY",
        "PROGRAM_CREDIT_REQUIREMENT_EMPTY",
        "PROGRAM_GRADUATION_REQUIREMENT_EMPTY",
    }


def test_new_v1_definition_phase_uses_exact_bounded_keys_and_skips_reuse_binding_reads():
    calls = []
    result = _pipeline().run_program_import_preflight(
        _rows(include_binding=True),
        phase="DEFINITION",
        **_loaders(calls),
    )
    assert result["stage"] == "READY"
    assert result["programPreflightSafe"] is True
    assert result["requestKeys"] == {
        "majorIds": (1,),
        "classIds": (),
        "courseKeys": ("CS101@v1",),
        "seriesKeys": ("SER-A",),
        "bindingScopeKeys": ("MAJOR:1:GRADE:2026:MAJOR_GRADE",),
    }
    assert calls == [
        ("scope", ()),
        ("major", (1,)),
        ("course", ("CS101@v1",)),
        ("program", ("SER-A",)),
    ]
    assert result["actions"][0]["action"] == "CREATE"
    assert result["actions"][0]["createStatus"] == "DRAFT"
    assert result["binding"]["bindingWriteAllowed"] is False
    assert result["binding"]["intents"][0]["decision"] == "DEFER_UNTIL_PUBLISHED"


def test_reuse_loads_only_exact_program_definition_ids_after_reference_is_green():
    calls = []
    result = _pipeline().run_program_import_preflight(
        _rows(),
        phase="DEFINITION",
        **_loaders(
            calls,
            programs=_program_snapshots(),
            definitions=_existing_definitions(),
        ),
    )
    assert result["stage"] == "READY"
    assert result["programPreflightSafe"] is True
    assert calls == [
        ("scope", ()),
        ("major", (1,)),
        ("course", ("CS101@v1",)),
        ("program", ("SER-A",)),
        ("definitions", ("501",)),
    ]
    assert result["actions"][0]["action"] == "REUSE"
    assert result["actions"][0]["definitionReconciled"] is True


def test_binding_phase_reads_only_target_program_ids_and_exact_binding_scopes():
    calls = []
    result = _pipeline().run_program_import_preflight(
        _rows(include_binding=True),
        phase="BINDING",
        **_loaders(
            calls,
            programs=_program_snapshots(),
            definitions=_existing_definitions(),
            status={"501": "PUBLISHED"},
        ),
    )
    assert result["stage"] == "READY"
    assert result["programPreflightSafe"] is True
    assert calls == [
        ("scope", ()),
        ("major", (1,)),
        ("course", ("CS101@v1",)),
        ("program", ("SER-A",)),
        ("definitions", ("501",)),
        ("status", ("501",)),
        ("active_binding", ("MAJOR:1:GRADE:2026:MAJOR_GRADE",)),
    ]
    assert result["binding"]["bindingWriteAllowed"] is True
    assert result["binding"]["intents"][0] == {
        "row": 2,
        "programKey": "SERIES:SER-A:v1",
        "programId": "501",
        "scopeKey": "MAJOR:1:GRADE:2026:MAJOR_GRADE",
        "action": "CREATE",
        "supersedeProgramId": "",
    }


def test_definition_phase_defers_class_lookup_but_binding_phase_revalidates_exact_class():
    definition_calls = []
    definition = _pipeline().run_program_import_preflight(
        _rows(include_binding=True, class_binding=True),
        phase="DEFINITION",
        **_loaders(definition_calls),
    )
    assert definition["stage"] == "READY"
    assert definition_calls == [
        ("scope", ()),
        ("major", (1,)),
        ("course", ("CS101@v1",)),
        ("program", ("SER-A",)),
    ]
    assert definition["binding"]["intents"][0]["decision"] == "DEFER_UNTIL_PUBLISHED"

    binding_calls = []
    binding = _pipeline().run_program_import_preflight(
        _rows(include_binding=True, class_binding=True),
        phase="BINDING",
        **_loaders(
            binding_calls,
            programs=_program_snapshots(),
            definitions=_existing_definitions(),
            class_rows=[{
                "classId": 77,
                "majorId": 1,
                "gradeYear": "2026",
                "classStatus": "NORMAL",
            }],
            status={"501": "PUBLISHED"},
        ),
    )
    assert binding["stage"] == "READY"
    assert binding_calls[:5] == [
        ("scope", ()),
        ("major", (1,)),
        ("class", (77,)),
        ("course", ("CS101@v1",)),
        ("program", ("SER-A",)),
    ]


def test_binding_phase_without_binding_rows_is_zero_db_source_reject():
    calls = []
    result = _pipeline().run_program_import_preflight(
        _rows(include_binding=False),
        phase="BINDING",
        **_loaders(calls),
    )
    assert result["stage"] == "SOURCE"
    assert result["programPreflightSafe"] is False
    assert calls == []
    assert result["errors"] == [{
        "row": 0,
        "logicalGroup": "BINDING",
        "programKey": "",
        "businessCode": "PROGRAM_BINDING_SOURCE_EMPTY",
        "message": "BINDING phase 没有任何适用范围定义，禁止执行空绑定确认",
        "evidence": {},
        "howToResolve": "在“适用范围”工作表填写至少一条 MAJOR_GRADE 或 CLASS 绑定后重新预检",
    }]


def test_pipeline_has_no_session_or_shared_dispatcher_owner():
    source = inspect.getsource(_pipeline())
    assert "get_sessionmaker" not in source
    assert "session()" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
    assert "db.commit" not in source
    assert "db.flush" not in source
