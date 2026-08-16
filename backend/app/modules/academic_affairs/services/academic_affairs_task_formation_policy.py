"""TeachingTask formation contract for Academic A-W3.

This module deliberately contains no database reads or writes.  It freezes the
formation vocabulary and the narrow evidence that can be proven from today's
runtime facts while the shared ProgramCourse/TeachingTask schema is owned by
Academic INT.

Important boundaries:
- course nature/name is never formation evidence;
- a RETAKE roster version is provenance for roster membership, not proof that
  the whole TeachingTask is a dedicated RETAKE offering;
- LAYERED has storage/display support today but no proven canonical writer, so
  legacy rows cannot be promoted to LAYERED from labels or scores;
- ambiguous or contradictory history stays fail-closed instead of being
  rewritten to ADMIN_FIXED.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

FORMATION_ADMIN_FIXED = "ADMIN_FIXED"
FORMATION_SELECTABLE = "SELECTABLE"
FORMATION_MERGED = "MERGED"
FORMATION_RETAKE = "RETAKE"
FORMATION_LAYERED = "LAYERED"

FORMATION_MODES = frozenset({
    FORMATION_ADMIN_FIXED,
    FORMATION_SELECTABLE,
    FORMATION_MERGED,
    FORMATION_RETAKE,
    FORMATION_LAYERED,
})

FORMATION_LABELS = {
    FORMATION_ADMIN_FIXED: "固定行政班",
    FORMATION_SELECTABLE: "自主选课",
    FORMATION_MERGED: "合班",
    FORMATION_RETAKE: "重修",
    FORMATION_LAYERED: "分层",
}

CLASS_TYPE_BY_FORMATION = {
    FORMATION_ADMIN_FIXED: "ADMIN",
    FORMATION_SELECTABLE: "SELECTION",
    FORMATION_MERGED: "MERGED",
    FORMATION_RETAKE: "RETAKE",
    FORMATION_LAYERED: "LAYERED",
}

EVIDENCE_PROVEN = "PROVEN"
EVIDENCE_UNKNOWN = "UNKNOWN"
EVIDENCE_CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class FormationEvidence:
    """Conservative interpretation of legacy execution facts.

    ``mode`` is populated only when the current repository can prove the
    formation without using names, course nature, or client-side inference.
    UNKNOWN/CONFLICT must remain blocked for authoritative backfill.
    """

    mode: str | None
    status: str
    source: str
    blockers: tuple[str, ...] = ()

    @property
    def proven(self) -> bool:
        return self.status == EVIDENCE_PROVEN and self.mode in FORMATION_MODES


def normalize_formation_mode(value, *, required: bool = False) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        if required:
            raise ValueError("formationMode is required")
        return None
    if text not in FORMATION_MODES:
        raise ValueError(f"unsupported formationMode: {text}")
    return text


def class_type_for_formation(value) -> str:
    mode = normalize_formation_mode(value, required=True)
    return CLASS_TYPE_BY_FORMATION[mode]


def selection_eligible(value) -> bool:
    """Only an explicit SELECTABLE formation may enter B Selection supply."""
    return normalize_formation_mode(value, required=True) == FORMATION_SELECTABLE


def _upper_set(values: Iterable[object] | None) -> set[str]:
    return {
        str(value or "").strip().upper()
        for value in (values or ())
        if str(value or "").strip()
    }


def resolve_legacy_task_formation(
    *,
    is_merged: bool,
    class_id: int | None,
    selection_exists: bool = False,
    teaching_class_type: str | None = None,
    roster_source_types: Iterable[object] | None = None,
) -> FormationEvidence:
    """Resolve only formation semantics that are provable from legacy facts.

    This function is intended for migration inventory/reconciliation, not as a
    permanent replacement for an explicit formation snapshot on TeachingTask.
    Contradictory history is returned as CONFLICT so callers can surface a
    blocker instead of silently choosing a winner.
    """
    class_type = str(teaching_class_type or "").strip().upper()
    roster_sources = _upper_set(roster_source_types)
    selection_evidence = bool(
        selection_exists
        or class_type == "SELECTION"
        or "SELECTION_LOCK" in roster_sources
    )

    if is_merged:
        if selection_evidence or class_type in {"RETAKE", "LAYERED"}:
            return FormationEvidence(
                mode=None,
                status=EVIDENCE_CONFLICT,
                source="LEGACY_CONFLICT",
                blockers=("MERGED_FORMATION_CONFLICT",),
            )
        return FormationEvidence(
            mode=FORMATION_MERGED,
            status=EVIDENCE_PROVEN,
            source="TASK_MERGE_STATE",
        )

    if selection_evidence:
        if class_type in {"MERGED", "RETAKE", "LAYERED"}:
            return FormationEvidence(
                mode=None,
                status=EVIDENCE_CONFLICT,
                source="LEGACY_CONFLICT",
                blockers=("SELECTION_FORMATION_CONFLICT",),
            )
        return FormationEvidence(
            mode=FORMATION_SELECTABLE,
            status=EVIDENCE_PROVEN,
            source="SELECTION_RUNTIME_EVIDENCE",
        )

    # A RETAKE roster source only means that one or more students joined this
    # task through retake processing.  It must not reclassify an ordinary task.
    if class_type == "RETAKE":
        return FormationEvidence(
            mode=None,
            status=EVIDENCE_UNKNOWN,
            source="UNPROVEN_RETAKE_CLASS_TYPE",
            blockers=("RETAKE_TASK_SOURCE_UNPROVEN",),
        )
    if class_type == "LAYERED":
        return FormationEvidence(
            mode=None,
            status=EVIDENCE_UNKNOWN,
            source="UNPROVEN_LAYERED_CLASS_TYPE",
            blockers=("LAYERED_SOURCE_UNPROVEN",),
        )
    if class_type not in {"", "ADMIN"}:
        return FormationEvidence(
            mode=None,
            status=EVIDENCE_CONFLICT,
            source="UNKNOWN_CLASS_TYPE",
            blockers=("CLASS_TYPE_UNRECOGNIZED",),
        )

    if class_id:
        return FormationEvidence(
            mode=FORMATION_ADMIN_FIXED,
            status=EVIDENCE_PROVEN,
            source=(
                "ADMIN_CLASS_WITH_RETAKE_ROSTER"
                if "RETAKE" in roster_sources
                else "ADMIN_CLASS_ID"
            ),
        )

    return FormationEvidence(
        mode=None,
        status=EVIDENCE_UNKNOWN,
        source="FORMATION_SOURCE_MISSING",
        blockers=("FORMATION_SOURCE_MISSING",),
    )
