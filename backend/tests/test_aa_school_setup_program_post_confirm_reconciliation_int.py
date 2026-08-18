"""INT contracts for Program confirm -> authoritative reread reconciliation."""
from __future__ import annotations

import inspect
from decimal import Decimal


def _service():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_post_confirm_reconciliation as service
    return service


def _source_rows():
    key = "SERIES:SER-A:v1"
    return [
        {
            "rowNo": 2,
            "logicalGroup": "MAIN",
            "programKey": key,
            "definitionKey": key,
            "payload": {
                "programSeriesKey": "SER-A",
                "programVersion": 1,
                "programName": "软件技术培养方案",
                "majorId": 10,
                "gradeYear": "2026",
                "totalCredits": Decimal("3.0"),
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "COURSE",
            "programKey": key,
            "definitionKey": f"{key}|COURSE|CS101@v1",
            "payload": {
                "programKey": key,
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
            "programKey": key,
            "definitionKey": f"{key}|CREDIT|专业核心",
            "payload": {
                "programKey": key,
                "module": "专业核心",
                "creditTarget": Decimal("3"),
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "GRADUATION",
            "programKey": key,
            "definitionKey": f"{key}|GRADUATION|ABILITY|完成项目",
            "payload": {
                "programKey": key,
                "category": "ABILITY",
                "content": "完成项目",
                "sortOrder": 0,
            },
        },
    ]


def _definition_preflight(*, action="CREATE", program_id="", predecessor=""):
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "binding": {"phase": "DEFINITION", "bindingWriteAllowed": False},
        "actions": [{
            "programKey": "SERIES:SER-A:v1",
            "action": action,
            "programId": program_id,
            "predecessorProgramId": predecessor,
            "definitionReconciled": action == "REUSE",
        }],
    }


def _program_snapshot(**overrides):
    value = {
        "programId": "501",
        "seriesKey": "SER-A",
        "version": 1,
        "programName": "软件技术培养方案",
        "majorId": 10,
        "gradeYear": "2026",
        "totalCredits": Decimal("3"),
        "prevProgramId": "",
        "status": "DRAFT",
    }
    value.update(overrides)
    return value


def _definition_rows(*, module="专业核心", credit=Decimal("3.00")):
    return [
        {
            "programId": "501",
            "logicalGroup": "COURSE",
            "payload": {
                "courseKey": "CS101@v1",
                "module": module,
                "formationMode": "ADMIN_FIXED",
                "openTermNo": 1,
                "creditSnapshot": credit,
            },
        },
        {
            "programId": "501",
            "logicalGroup": "CREDIT_REQUIREMENT",
            "payload": {"module": "专业核心", "creditTarget": Decimal("3.0")},
        },
        {
            "programId": "501",
            "logicalGroup": "GRADUATION",
            "payload": {"category": "ABILITY", "content": "完成项目", "sortOrder": 0},
        },
    ]


def _courses():
    return [{"courseCode": "CS101", "version": 1, "credit": Decimal("3")}]


def test_create_definition_reread_proves_main_children_hash_and_prev_relationship():
    result = _service().reconcile_program_definition_after_confirm(
        _source_rows(),
        _definition_preflight(),
        authoritative_program_snapshots=[_program_snapshot()],
        authoritative_definition_rows=_definition_rows(),
        course_snapshots=_courses(),
    )
    assert result["phase"] == "DEFINITION"
    assert result["reconciliationSafe"] is True
    assert result["importedPrograms"] == 1
    assert result["reusedPrograms"] == 0
    assert result["programCount"] == 1
    assert result["errors"] == []
    item = result["items"][0]
    assert item["programId"] == "501"
    assert item["action"] == "CREATE"
    assert item["hashMatch"] is True
    assert len(item["definitionHash"]) == 64
    assert item["definitionHash"] == item["rereadDefinitionHash"]
    assert item["relationship"] == {
        "prevProgramId": "",
        "expectedPrevProgramId": "",
    }


def test_decimal_scale_differences_do_not_create_false_hash_mismatch():
    result = _service().reconcile_program_definition_after_confirm(
        _source_rows(),
        _definition_preflight(),
        authoritative_program_snapshots=[_program_snapshot(totalCredits=Decimal("3.000"))],
        authoritative_definition_rows=_definition_rows(credit=Decimal("3.0000")),
        course_snapshots=_courses(),
    )
    assert result["reconciliationSafe"] is True
    assert result["items"][0]["hashMatch"] is True


def test_child_relationship_drift_is_hash_failure_even_when_program_row_exists():
    result = _service().reconcile_program_definition_after_confirm(
        _source_rows(),
        _definition_preflight(),
        authoritative_program_snapshots=[_program_snapshot()],
        authoritative_definition_rows=_definition_rows(module="错误模块"),
        course_snapshots=_courses(),
    )
    assert result["reconciliationSafe"] is False
    assert result["items"][0]["hashMatch"] is False
    error = next(
        item for item in result["errors"]
        if item["businessCode"] == "PROGRAM_REREAD_DEFINITION_HASH_MISMATCH"
    )
    assert error["evidence"]["programId"] == "501"
    assert error["evidence"]["expectedHash"] != error["evidence"]["actualHash"]
    assert error["evidence"]["expectedCounts"]["COURSE"] == 1
    assert error["evidence"]["actualCounts"]["COURSE"] == 1


def test_create_reread_requires_draft_and_exact_predecessor_relationship():
    result = _service().reconcile_program_definition_after_confirm(
        _source_rows(),
        _definition_preflight(predecessor="400"),
        authoritative_program_snapshots=[_program_snapshot(status="ENABLED", prevProgramId="399")],
        authoritative_definition_rows=_definition_rows(),
        course_snapshots=_courses(),
    )
    assert result["reconciliationSafe"] is False
    error = next(
        item for item in result["errors"]
        if item["businessCode"] == "PROGRAM_REREAD_MAIN_MISMATCH"
    )
    different = {item["field"]: item for item in error["evidence"]["differentFields"]}
    assert different["status"] == {"field": "status", "expected": "DRAFT", "actual": "ENABLED"}
    assert different["prevProgramId"] == {
        "field": "prevProgramId", "expected": "400", "actual": "399",
    }


def test_reuse_requires_same_authoritative_program_id_and_keeps_hash_reconciliation():
    result = _service().reconcile_program_definition_after_confirm(
        _source_rows(),
        _definition_preflight(action="REUSE", program_id="501"),
        authoritative_program_snapshots=[_program_snapshot(status="PUBLISHED")],
        authoritative_definition_rows=_definition_rows(),
        course_snapshots=_courses(),
    )
    assert result["reconciliationSafe"] is True
    assert result["importedPrograms"] == 0
    assert result["reusedPrograms"] == 1
    assert result["items"][0]["action"] == "REUSE"


def _binding_preflight(*, action="CREATE", supersede="400"):
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "actions": [{
            "programKey": "SERIES:SER-A:v1",
            "action": "REUSE",
            "programId": "501",
            "definitionReconciled": True,
        }],
        "binding": {
            "phase": "BINDING",
            "bindingWriteAllowed": True,
            "errors": [],
            "intents": [{
                "row": 2,
                "programKey": "SERIES:SER-A:v1",
                "programId": "501",
                "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
                "action": action,
                "supersedeProgramId": supersede,
            }],
        },
    }


def test_binding_reread_proves_unique_active_target_supersede_and_enabled_status():
    result = _service().reconcile_program_bindings_after_confirm(
        _binding_preflight(),
        authoritative_binding_snapshots=[
            {
                "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
                "programId": "400",
                "status": "SUPERSEDED",
            },
            {
                "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
                "programId": "501",
                "status": "ACTIVE",
            },
        ],
        authoritative_program_status_by_id={"501": "ENABLED"},
    )
    assert result["phase"] == "BINDING"
    assert result["reconciliationSafe"] is True
    assert result["createdBindings"] == 1
    assert result["reusedBindings"] == 0
    assert result["bindingCount"] == 1
    assert len(result["activeRelationshipHash"]) == 64
    assert result["errors"] == []
    assert result["items"][0] == {
        "programKey": "SERIES:SER-A:v1",
        "programId": "501",
        "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "action": "CREATE",
        "activeRelationshipMatch": True,
        "supersedeRelationshipMatch": True,
        "targetStatusMatch": True,
    }


def test_binding_reread_fails_closed_on_duplicate_active_missing_supersede_or_status_drift():
    result = _service().reconcile_program_bindings_after_confirm(
        _binding_preflight(),
        authoritative_binding_snapshots=[
            {
                "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
                "programId": "501",
                "status": "ACTIVE",
            },
            {
                "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
                "programId": "999",
                "status": "ACTIVE",
            },
        ],
        authoritative_program_status_by_id={"501": "PUBLISHED"},
    )
    assert result["reconciliationSafe"] is False
    assert {item["businessCode"] for item in result["errors"]} == {
        "PROGRAM_BINDING_REREAD_ACTIVE_MISMATCH",
        "PROGRAM_BINDING_REREAD_SUPERSEDE_MISSING",
        "PROGRAM_BINDING_REREAD_TARGET_STATUS_MISMATCH",
    }


def test_post_confirm_reconciliation_is_pure_and_does_not_claim_shared_owner():
    source = inspect.getsource(_service())
    assert "get_sessionmaker" not in source
    assert "session()" not in source
    assert "db.query" not in source
    assert "db.add" not in source
    assert "db.commit" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
    assert "ImportJob(" not in source
    assert "FileObject(" not in source
