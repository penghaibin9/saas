"""INT Program full-definition reconciliation contracts."""
from __future__ import annotations

import inspect


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter
    return adapter


def _reconcile():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_reconciliation as reconcile
    return reconcile


def _source_rows(*, credit_snapshot=None, formation="ADMIN_FIXED"):
    course = {
        "programSeriesKey": "CS-SOFT", "programVersion": 1,
        "courseCode": "CS101", "courseVersion": 1,
        "openTermNo": 1, "module": "专业核心", "formationMode": formation,
    }
    if credit_snapshot is not None:
        course["creditSnapshot"] = credit_snapshot
    return _adapter().normalize_program_import_rows({
        "MAIN": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 1,
            "programName": "方案", "majorId": 10, "gradeYear": "2026", "totalCredits": 150,
        }],
        "COURSE": [course],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 1,
            "module": "专业核心", "creditTarget": 150,
        }],
        "PRACTICE": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 1,
            "segmentName": "岗位实习", "segmentType": "POST_INTERNSHIP",
            "openTermNo": 5, "weeks": 16, "credit": 8,
            "orgMode": "DISTRIBUTED", "assessmentMode": "CHECK", "sortOrder": 10,
        }],
        "GRADUATION": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 1,
            "category": "ABILITY", "content": "完成综合项目", "sortOrder": 1,
        }],
        "BINDING": [{
            "programSeriesKey": "CS-SOFT", "programVersion": 1,
            "majorId": 10, "gradeYear": "2026", "bindingScope": "MAJOR_GRADE",
        }],
    })


def _existing(*, formation="ADMIN_FIXED", credit="3.5", include_extra=False):
    rows = [
        {
            "programId": "9001", "logicalGroup": "COURSE",
            "payload": {
                "courseKey": "CS101@v1", "module": "专业核心",
                "formationMode": formation, "openTermNo": 1, "creditSnapshot": credit,
            },
        },
        {
            "programId": "9001", "logicalGroup": "CREDIT_REQUIREMENT",
            "payload": {"module": "专业核心", "creditTarget": 150},
        },
        {
            "programId": "9001", "logicalGroup": "PRACTICE",
            "payload": {
                "segmentName": "岗位实习", "segmentType": "POST_INTERNSHIP",
                "openTermNo": 5, "weeks": 16, "credit": 8,
                "orgMode": "DISTRIBUTED", "location": None,
                "assessmentMode": "CHECK", "sortOrder": 10,
            },
        },
        {
            "programId": "9001", "logicalGroup": "GRADUATION",
            "payload": {"category": "ABILITY", "content": "完成综合项目", "sortOrder": 1},
        },
        # Binding is a relationship lifecycle and must not participate in definition identity.
        {
            "programId": "9001", "logicalGroup": "BINDING",
            "payload": {"majorId": 10, "gradeYear": "2026", "bindingScope": "CLASS", "classId": 77},
        },
    ]
    if include_extra:
        rows.append({
            "programId": "9001", "logicalGroup": "GRADUATION",
            "payload": {"category": "QUALITY", "content": "额外既有要求", "sortOrder": 2},
        })
    return rows


def _reuse_action():
    return [{
        "programKey": "SERIES:CS-SOFT:v1",
        "action": "REUSE",
        "programId": "9001",
        "requiresDefinitionReconciliation": True,
    }]


def _course_snapshots():
    return [{"courseCode": "CS101", "version": 1, "credit": "3.5"}]


def test_definition_reconciliation_is_pure_and_binding_is_explicitly_separate():
    source = inspect.getsource(_reconcile())
    for forbidden in (
        "get_sessionmaker", "session()", "db.query", "db.execute", "select(",
        "db.add", "db.commit", "db.flush", "ImportJob", "FileObject",
    ):
        assert forbidden not in source
    assert "PROGRAM_GROUP_BINDING" in source


def test_exact_full_definition_reuse_is_green_and_source_order_does_not_matter():
    source_rows = list(reversed(_source_rows()))
    result = _reconcile().reconcile_program_definitions(
        source_rows,
        _reuse_action(),
        existing_definition_rows=list(reversed(_existing())),
        course_snapshots=_course_snapshots(),
    )
    assert result["definitionReconciliationSafe"] is True
    assert result["errors"] == []
    assert result["actions"] == [{
        "programKey": "SERIES:CS-SOFT:v1",
        "action": "REUSE",
        "programId": "9001",
        "requiresDefinitionReconciliation": False,
        "definitionReconciled": True,
    }]


def test_omitted_source_credit_snapshot_uses_exact_course_credit_for_full_reconciliation():
    result = _reconcile().reconcile_program_definitions(
        _source_rows(credit_snapshot=None),
        _reuse_action(),
        existing_definition_rows=_existing(credit="3.5"),
        course_snapshots=_course_snapshots(),
    )
    assert result["definitionReconciliationSafe"] is True


def test_existing_program_course_without_formation_provenance_fails_closed():
    result = _reconcile().reconcile_program_definitions(
        _source_rows(),
        _reuse_action(),
        existing_definition_rows=_existing(formation=None),
        course_snapshots=_course_snapshots(),
    )
    assert result["definitionReconciliationSafe"] is False
    assert result["errors"] == [{
        "programKey": "SERIES:CS-SOFT:v1",
        "businessCode": "PROGRAM_EXISTING_FORMATION_PROVENANCE_MISSING",
        "message": "既有 ProgramCourse 缺少显式 formationMode provenance，禁止猜测后复用",
        "evidence": {"programId": "9001"},
        "howToResolve": "先按 migration inventory 证明并回填 formation provenance；未知/冲突历史必须阻断",
    }]
    assert result["actions"][0]["action"] == "CONFLICT"


def test_extra_or_changed_existing_definition_conflicts_instead_of_overwriting():
    extra = _reconcile().reconcile_program_definitions(
        _source_rows(),
        _reuse_action(),
        existing_definition_rows=_existing(include_extra=True),
        course_snapshots=_course_snapshots(),
    )
    assert extra["definitionReconciliationSafe"] is False
    issue = extra["errors"][0]
    assert issue["businessCode"] == "PROGRAM_DEFINITION_SNAPSHOT_CONFLICT"
    grad = next(diff for diff in issue["evidence"]["groupDiffs"] if diff["logicalGroup"] == "GRADUATION")
    assert grad["extraInExisting"]

    changed = _existing()
    changed[1] = {
        "programId": "9001", "logicalGroup": "CREDIT_REQUIREMENT",
        "payload": {"module": "专业核心", "creditTarget": 140},
    }
    mismatch = _reconcile().reconcile_program_definitions(
        _source_rows(),
        _reuse_action(),
        existing_definition_rows=changed,
        course_snapshots=_course_snapshots(),
    )
    assert mismatch["actions"][0]["action"] == "CONFLICT"
    assert mismatch["errors"][0]["businessCode"] == "PROGRAM_DEFINITION_SNAPSHOT_CONFLICT"


def test_binding_difference_does_not_change_program_definition_identity():
    existing = _existing()
    existing[-1] = {
        "programId": "9001", "logicalGroup": "BINDING",
        "payload": {"majorId": 10, "gradeYear": "2026", "bindingScope": "CLASS", "classId": 999},
    }
    result = _reconcile().reconcile_program_definitions(
        _source_rows(),
        _reuse_action(),
        existing_definition_rows=existing,
        course_snapshots=_course_snapshots(),
    )
    assert result["definitionReconciliationSafe"] is True
    assert result["actions"][0]["definitionReconciled"] is True


def test_create_and_prior_conflict_actions_do_not_require_existing_definition_rows():
    actions = [
        {
            "programKey": "SERIES:CS-SOFT:v1", "action": "CREATE", "programId": "",
            "createStatus": "DRAFT", "predecessorProgramId": "",
            "requiresDefinitionReconciliation": False,
        },
        {
            "programKey": "SERIES:OTHER:v1", "action": "REJECT", "programId": "",
            "requiresDefinitionReconciliation": False,
        },
    ]
    result = _reconcile().reconcile_program_definitions(
        _source_rows(), actions, existing_definition_rows=[], course_snapshots=_course_snapshots()
    )
    assert result["definitionReconciliationSafe"] is True
    assert [item["action"] for item in result["actions"]] == ["CREATE", "REJECT"]
