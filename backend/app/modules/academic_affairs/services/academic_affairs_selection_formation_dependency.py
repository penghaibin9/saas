"""B formation dependency boundary while upstream task provenance is unavailable.

Selection must not infer formation from course/class labels or current Program state.
This module accepts only an explicit upstream provenance snapshot.  It deliberately
does not implement formation eligibility policy; once Academic A exposes the stable
consumer facade, B will pass the proven snapshot to A's canonical policy.
"""
from __future__ import annotations

from collections.abc import Mapping

from app.core.exceptions import AppException


BLOCKER_FORMATION_PROVENANCE_UNAVAILABLE = "SELECTION_FORMATION_PROVENANCE_UNAVAILABLE"


def _blocked(teaching_task_id=None, **details) -> AppException:
    evidence = {
        "blocker": BLOCKER_FORMATION_PROVENANCE_UNAVAILABLE,
        "requiredEvidence": ["status=PROVEN", "sourceProgramCourseId", "formationMode"],
        "teachingTaskId": str(teaching_task_id or ""),
        **details,
    }
    return AppException(
        "DATA_CONFLICT",
        "教学任务缺少可证明的培养方案课程编班来源，当前不能判定是否允许进入选课供给",
        details=evidence,
        http_status=409,
    )


def require_proven_task_formation_snapshot(snapshot, *, teaching_task_id=None) -> dict:
    """Return normalized explicit provenance or fail closed without inference.

    ``snapshot`` is the future A-owned consumer DTO.  B intentionally does not query
    ProgramCourse by current course/class facts and does not map formation labels on
    its own.  Until upstream can provide this DTO, callers receive a dependency
    blocker rather than a guessed formation decision.
    """
    if not isinstance(snapshot, Mapping):
        raise _blocked(teaching_task_id, provenanceStatus="MISSING")

    status = str(snapshot.get("status") or "").strip().upper()
    source_program_course_id = str(snapshot.get("sourceProgramCourseId") or "").strip()
    formation_mode = str(snapshot.get("formationMode") or "").strip().upper()
    if status != "PROVEN" or not source_program_course_id or not formation_mode:
        raise _blocked(
            teaching_task_id,
            provenanceStatus=status or "MISSING",
            sourceProgramCourseId=source_program_course_id,
            formationMode=formation_mode,
        )

    return {
        "status": "PROVEN",
        "sourceProgramCourseId": source_program_course_id,
        "formationMode": formation_mode,
    }
