"""INT invariant contract for ACTIVE ProgramBinding target status."""
from __future__ import annotations


def _policy():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_policy as policy
    return policy


def _rows():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter

    return adapter.normalize_program_import_rows({
        "BINDING": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "majorId": 10,
            "gradeYear": "2026",
            "bindingScope": "MAJOR_GRADE",
        }],
    })


def _definition():
    return [{
        "programKey": "SERIES:CS-SOFT:v2",
        "action": "REUSE",
        "programId": "9002",
        "requiresDefinitionReconciliation": False,
        "definitionReconciled": True,
    }]


def _active():
    return [{
        "programId": "9002",
        "majorId": 10,
        "gradeYear": "2026",
        "bindingScope": "MAJOR_GRADE",
        "classId": None,
        "status": "ACTIVE",
    }]


def test_active_binding_to_published_target_is_dirty_state_not_zero_write_reuse():
    result = _policy().classify_program_binding_phase(
        _rows(),
        _definition(),
        phase="BINDING",
        program_status_by_id={"9002": "PUBLISHED"},
        active_binding_snapshots=_active(),
    )

    assert result["bindingWriteAllowed"] is False
    assert result["intents"] == []
    assert result["errors"] == [{
        "row": 2,
        "programKey": "SERIES:CS-SOFT:v2",
        "businessCode": "PROGRAM_BINDING_ACTIVE_TARGET_NOT_ENABLED",
        "message": "已存在 ACTIVE 绑定的目标 Program 不是 ENABLED，禁止按 REUSE 静默修复关系状态",
        "evidence": {
            "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
            "programId": "9002",
            "status": "PUBLISHED",
        },
        "howToResolve": "先通过受控修复/回滚流程恢复 Program 状态与 ACTIVE binding 一致性，再重新执行普通 BINDING confirm",
    }]


def test_active_binding_to_enabled_target_remains_true_zero_write_reuse():
    result = _policy().classify_program_binding_phase(
        _rows(),
        _definition(),
        phase="BINDING",
        program_status_by_id={"9002": "ENABLED"},
        active_binding_snapshots=_active(),
    )

    assert result["bindingWriteAllowed"] is True
    assert result["errors"] == []
    assert result["intents"] == [{
        "row": 2,
        "programKey": "SERIES:CS-SOFT:v2",
        "programId": "9002",
        "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "action": "REUSE",
        "supersedeProgramId": "",
    }]
