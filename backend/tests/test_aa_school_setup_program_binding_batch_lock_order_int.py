"""INT Program BINDING bulk lock-order contract."""
from __future__ import annotations


def _planner():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_write_plan as planner
    return planner


def _preflight(intents):
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "binding": {
            "phase": "BINDING",
            "bindingWriteAllowed": True,
            "errors": [],
            "intents": intents,
        },
    }


def _intents():
    return [
        {
            "row": 9,
            "programKey": "SERIES:B:v1",
            "programId": "20",
            "scopeKey": "MAJOR:10:GRADE:2026:CLASS:77",
            "action": "CREATE",
            "supersedeProgramId": "12",
        },
        {
            "row": 2,
            "programKey": "SERIES:A:v2",
            "programId": "3",
            "scopeKey": "MAJOR:11:GRADE:2026:MAJOR_GRADE",
            "action": "CREATE",
            "supersedeProgramId": "",
        },
        {
            "row": 5,
            "programKey": "SERIES:C:v1",
            "programId": "9",
            "scopeKey": "MAJOR:12:GRADE:2027:CLASS:88",
            "action": "REUSE",
            "supersedeProgramId": "",
        },
    ]


def test_bulk_binding_plan_locks_all_programs_then_anchors_then_active_scopes():
    plan = _planner().build_program_binding_write_plan(_preflight(_intents()))

    assert plan["mutationsRequireBatchLocks"] is True
    assert plan["perPlanLockOrderIsExplanatoryOnly"] is True
    assert plan["batchLockOrder"] == [
        "PROGRAM:3",
        "PROGRAM:9",
        "PROGRAM:20",
        "MAJOR:11",
        "CLASS:77",
        "CLASS:88",
        "ACTIVE_BINDING_SCOPE:MAJOR:10:GRADE:2026:CLASS:77",
        "ACTIVE_BINDING_SCOPE:MAJOR:11:GRADE:2026:MAJOR_GRADE",
        "ACTIVE_BINDING_SCOPE:MAJOR:12:GRADE:2027:CLASS:88",
    ]

    first_anchor = next(
        index for index, token in enumerate(plan["batchLockOrder"])
        if token.startswith(("MAJOR:", "CLASS:"))
    )
    first_scope = next(
        index for index, token in enumerate(plan["batchLockOrder"])
        if token.startswith("ACTIVE_BINDING_SCOPE:")
    )
    assert all(token.startswith("PROGRAM:") for token in plan["batchLockOrder"][:first_anchor])
    assert all(
        token.startswith(("MAJOR:", "CLASS:"))
        for token in plan["batchLockOrder"][first_anchor:first_scope]
    )


def test_bulk_binding_batch_lock_order_is_independent_of_source_intent_order():
    forward = _planner().build_program_binding_write_plan(_preflight(_intents()))
    reverse = _planner().build_program_binding_write_plan(_preflight(list(reversed(_intents()))))

    assert forward["batchLockOrder"] == reverse["batchLockOrder"]
    assert [item["scopeKey"] for item in forward["plans"]] == [
        item["scopeKey"] for item in reverse["plans"]
    ]


def test_reuse_scope_still_participates_in_locked_preflight_batch_order():
    plan = _planner().build_program_binding_write_plan(_preflight([{
        "row": 2,
        "programKey": "SERIES:R:v1",
        "programId": "42",
        "scopeKey": "MAJOR:10:GRADE:2026:CLASS:77",
        "action": "REUSE",
        "supersedeProgramId": "",
    }]))

    assert plan["plans"][0]["writeCount"] == 0
    assert plan["plans"][0]["lockOrder"] == []
    assert plan["batchLockOrder"] == [
        "PROGRAM:42",
        "CLASS:77",
        "ACTIVE_BINDING_SCOPE:MAJOR:10:GRADE:2026:CLASS:77",
    ]
