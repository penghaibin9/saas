"""C-W5 fail-closed guard for legacy direct AcademicGrade mutation URLs.

``/api/v1/academic/grades`` predates the formal GradeTask workflow and writes the
projection table by course name only.  Leaving those three compatibility writes
active would bypass stable course identity, roster/version evidence, approval,
EffectiveGrade policy snapshots and append-only correction history.

The URLs remain registered so old clients receive an explicit business conflict
instead of a 404.  Formal writes must use the mature academic-affairs GradeTask,
recognition/makeup/clearance, or grade-correction commands.
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import academic_service as legacy_academic

_MESSAGE = (
    "该兼容成绩写入口已停用：正式成绩必须走教务成绩任务发布；"
    "历史补录请走稳定课程身份补录流程，已发布成绩修改请走成绩更正/复查"
)


def _blocked(*_args, **_kwargs):
    raise AppException(
        "DATA_CONFLICT",
        _MESSAGE,
        details={
            "formalWrite": "academic-affairs/grade-task",
            "publishedChange": "grade-correction-or-recheck",
            "reason": "NO_DIRECT_ACADEMIC_GRADE_MUTATION",
        },
        http_status=409,
    )


_blocked._legacy_grade_write_fail_closed = True


def install() -> None:
    for name in ("create_grade", "update_grade", "void_grade"):
        original_name = f"_legacy_grade_write_guard_original_{name}"
        if not hasattr(legacy_academic, original_name):
            setattr(legacy_academic, original_name, getattr(legacy_academic, name))
        setattr(legacy_academic, name, _blocked)
