"""A-W3 TeachingTask Formation contract: conservative legacy evidence only."""
from __future__ import annotations

import inspect

from app.modules.academic_affairs.services import academic_affairs_task_formation_policy as policy


def test_w3_formation_vocabulary_and_class_type_mapping_are_frozen():
    assert policy.FORMATION_MODES == {
        "ADMIN_FIXED", "SELECTABLE", "MERGED", "RETAKE", "LAYERED",
    }
    assert {
        mode: policy.class_type_for_formation(mode)
        for mode in policy.FORMATION_MODES
    } == {
        "ADMIN_FIXED": "ADMIN",
        "SELECTABLE": "SELECTION",
        "MERGED": "MERGED",
        "RETAKE": "RETAKE",
        "LAYERED": "LAYERED",
    }


def test_w3_only_explicit_selectable_formation_can_enter_selection():
    assert policy.selection_eligible("SELECTABLE") is True
    for mode in policy.FORMATION_MODES - {"SELECTABLE"}:
        assert policy.selection_eligible(mode) is False


def test_w3_legacy_admin_fixed_is_proven_without_selection_evidence():
    result = policy.resolve_legacy_task_formation(
        is_merged=False,
        class_id=101,
        teaching_class_type="ADMIN",
        roster_source_types=["ADMIN_CLASS"],
    )
    assert result.proven is True
    assert result.mode == "ADMIN_FIXED"
    assert result.status == "PROVEN"


def test_w3_selection_runtime_evidence_beats_legacy_admin_class_shape_before_roster_lock():
    result = policy.resolve_legacy_task_formation(
        is_merged=False,
        class_id=101,
        selection_exists=True,
        teaching_class_type="ADMIN",
        roster_source_types=[],
    )
    assert result.proven is True
    assert result.mode == "SELECTABLE"
    assert result.source == "SELECTION_RUNTIME_EVIDENCE"


def test_w3_selectable_with_current_admin_roster_is_a_migration_conflict():
    result = policy.resolve_legacy_task_formation(
        is_merged=False,
        class_id=101,
        selection_exists=True,
        teaching_class_type="ADMIN",
        roster_source_types=["ADMIN_CLASS"],
    )
    assert result.proven is False
    assert result.mode is None
    assert result.status == "CONFLICT"
    assert result.source == "SELECTABLE_CURRENT_ADMIN_ROSTER"
    assert result.blockers == ("SELECTABLE_CURRENT_ADMIN_ROSTER",)


def test_w3_selection_lock_roster_is_also_proven_selection_evidence():
    result = policy.resolve_legacy_task_formation(
        is_merged=False,
        class_id=101,
        teaching_class_type="SELECTION",
        roster_source_types=["SELECTION_LOCK"],
    )
    assert result.proven is True
    assert result.mode == "SELECTABLE"


def test_w3_retake_roster_is_provenance_not_dedicated_retake_task():
    result = policy.resolve_legacy_task_formation(
        is_merged=False,
        class_id=101,
        teaching_class_type="ADMIN",
        roster_source_types=["RETAKE"],
    )
    assert result.proven is True
    assert result.mode == "ADMIN_FIXED"
    assert result.source == "ADMIN_CLASS_WITH_RETAKE_ROSTER"


def test_w3_retake_class_type_without_canonical_task_source_stays_unknown():
    result = policy.resolve_legacy_task_formation(
        is_merged=False,
        class_id=None,
        teaching_class_type="RETAKE",
        roster_source_types=["RETAKE"],
    )
    assert result.proven is False
    assert result.mode is None
    assert result.status == "UNKNOWN"
    assert "RETAKE_TASK_SOURCE_UNPROVEN" in result.blockers


def test_w3_layered_storage_without_writer_source_stays_unknown():
    result = policy.resolve_legacy_task_formation(
        is_merged=False,
        class_id=None,
        teaching_class_type="LAYERED",
        roster_source_types=[],
    )
    assert result.proven is False
    assert result.mode is None
    assert result.status == "UNKNOWN"
    assert "LAYERED_SOURCE_UNPROVEN" in result.blockers


def test_w3_merge_state_is_authoritative_but_conflicts_fail_closed():
    merged = policy.resolve_legacy_task_formation(
        is_merged=True,
        class_id=101,
        teaching_class_type="MERGED",
    )
    assert merged.proven is True and merged.mode == "MERGED"

    conflict = policy.resolve_legacy_task_formation(
        is_merged=True,
        class_id=101,
        selection_exists=True,
        teaching_class_type="MERGED",
    )
    assert conflict.proven is False
    assert conflict.status == "CONFLICT"
    assert conflict.mode is None


def test_w3_classless_task_without_formal_source_is_not_guessed_admin():
    result = policy.resolve_legacy_task_formation(
        is_merged=False,
        class_id=None,
        teaching_class_type=None,
        roster_source_types=[],
    )
    assert result.proven is False
    assert result.status == "UNKNOWN"
    assert result.blockers == ("FORMATION_SOURCE_MISSING",)


def test_w3_policy_has_no_course_name_or_nature_heuristic_inputs():
    params = set(inspect.signature(policy.resolve_legacy_task_formation).parameters)
    assert "course_name" not in params
    assert "course_nature" not in params
    source = inspect.getsource(policy.resolve_legacy_task_formation)
    assert "PUBLIC_ELECTIVE" not in source
    assert "ELECTIVE" not in source
