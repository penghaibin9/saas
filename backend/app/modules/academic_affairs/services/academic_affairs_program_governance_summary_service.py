"""D4-U 培养方案治理摘要批量读取优化。

保持公开 API、权限和 ``academic_affairs_program_governance_service.validate_program_db``
规则不变；这里只把 summary 所需事实一次性预载，再通过只读 snapshot DB 复用原校验器，
避免按方案/绑定重复访问 MySQL。
"""
from __future__ import annotations

from collections import defaultdict

from app.services.db_service import _tid, session

from . import academic_affairs_program_governance_service as governance
from . import academic_affairs_program_quality_service as validator

_MISSING = object()


def _expr_key_value(expr):
    left = getattr(expr, "left", None)
    key = getattr(left, "key", None)
    right = getattr(expr, "right", None)
    if hasattr(right, "value"):
        return key, right.value
    text = str(right if right is not None else "").strip().upper()
    if text == "NULL":
        return key, None
    return key, _MISSING


class _SnapshotQuery:
    """只实现 canonical validator 在治理摘要内实际使用的只读 Query 表面。"""

    def __init__(self, rows, *, mode: str = "plain", current_program_id: int | None = None):
        self._rows = list(rows)
        self._mode = mode
        self._current_program_id = current_program_id

    def join(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def filter(self, *expressions, **_kwargs):
        if self._mode == "class":
            class_id = _MISSING
            for expr in expressions:
                key, value = _expr_key_value(expr)
                if key == "id" and value is not _MISSING:
                    class_id = value
                    break
            if class_id is not _MISSING:
                self._rows = [row for row in self._rows if int(getattr(row, "id", 0) or 0) == int(class_id or 0)]
            return self

        if self._mode == "conflict":
            criteria = {}
            for expr in expressions:
                key, value = _expr_key_value(expr)
                if key in {"major_id", "grade_year", "class_id"} and value is not _MISSING:
                    criteria[key] = value

            def _matches(pair):
                binding, _program = pair
                if self._current_program_id is not None and int(binding.program_id) == int(self._current_program_id):
                    return False
                for key, expected in criteria.items():
                    if getattr(binding, key, None) != expected:
                        return False
                return True

            self._rows = [pair for pair in self._rows if _matches(pair)]
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class _ValidationSnapshotDb:
    """给原 validator/governance validator 提供已预载事实，不再触发源 Session 查询。"""

    def __init__(
        self,
        *,
        program,
        courses,
        requirements,
        practices,
        bindings,
        catalog_rows,
        enabled_codes,
        standard_bound: bool,
        classes,
        conflict_pairs,
    ):
        self._program = program
        self._courses = list(courses)
        self._requirements = list(requirements)
        self._practices = list(practices)
        self._bindings = list(bindings)
        self._catalog_rows = list(catalog_rows)
        self._enabled_codes = sorted(str(code) for code in enabled_codes)
        self._standard_bound = bool(standard_bound)
        self._classes = list(classes)
        self._conflict_pairs = list(conflict_pairs)

    def query(self, *models):
        from app.models import (
            AaCourse,
            AaProgram,
            AaProgramBinding,
            AaProgramCourse,
            AaProgramGraduationRequirement,
            AaProgramPracticeSegment,
            SchoolClass,
            SchoolMajorStandardBinding,
        )

        if len(models) == 1 and models[0] is AaProgram:
            return _SnapshotQuery([self._program])
        if len(models) == 1 and models[0] is AaProgramCourse:
            return _SnapshotQuery(self._courses)
        if len(models) == 1 and models[0] is AaProgramGraduationRequirement:
            return _SnapshotQuery(self._requirements)
        if len(models) == 1 and models[0] is AaProgramPracticeSegment:
            return _SnapshotQuery(self._practices)
        if len(models) == 1 and models[0] is AaProgramBinding:
            return _SnapshotQuery(self._bindings)
        if len(models) == 1 and models[0] is AaCourse:
            return _SnapshotQuery(self._catalog_rows)
        if len(models) == 1 and getattr(models[0], "key", None) == "course_code":
            owner = getattr(models[0], "class_", None)
            if owner is AaCourse:
                return _SnapshotQuery([(code,) for code in self._enabled_codes])
        if len(models) == 1 and models[0] is SchoolMajorStandardBinding:
            return _SnapshotQuery([object()] if self._standard_bound else [])
        if len(models) == 1 and models[0] is SchoolClass:
            return _SnapshotQuery(self._classes, mode="class")
        if len(models) == 2 and models[0] is AaProgramBinding and models[1] is AaProgram:
            return _SnapshotQuery(
                self._conflict_pairs,
                mode="conflict",
                current_program_id=int(self._program.id),
            )
        raise AssertionError(f"unsupported validation snapshot query: {models!r}")


def _group(rows, attr: str):
    grouped = defaultdict(list)
    for row in rows:
        grouped[int(getattr(row, attr))].append(row)
    return grouped


def _empty_summary() -> dict:
    return {
        "totalPrograms": 0,
        "readyPrograms": 0,
        "blockedPrograms": 0,
        "missingMajor": 0,
        "missingGrade": 0,
        "items": [],
    }


def program_governance_summary(user) -> dict:
    from app.models import (
        AaCourse,
        AaProgram,
        AaProgramBinding,
        AaProgramCourse,
        AaProgramGraduationRequirement,
        AaProgramPracticeSegment,
        NationalStandardDocument,
        SchoolClass,
        SchoolMajorStandardBinding,
    )

    with session() as db:
        scope = governance._scope(user, db)
        tenant_all = str(getattr(scope, "scope_type", "")).upper() == "TENANT_ALL"
        allowed_major_ids = governance._allowed_major_ids(db, scope)

        program_query = db.query(AaProgram).filter(
            AaProgram.tenant_id == _tid(),
            AaProgram.is_deleted.is_(False),
        )
        if not tenant_all:
            if not allowed_major_ids:
                return _empty_summary()
            program_query = program_query.filter(AaProgram.major_id.in_(sorted(allowed_major_ids)))
        programs = program_query.order_by(AaProgram.id.desc()).all()
        if not programs:
            return _empty_summary()

        program_ids = [int(row.id) for row in programs]
        courses = db.query(AaProgramCourse).filter(
            AaProgramCourse.tenant_id == _tid(),
            AaProgramCourse.program_id.in_(program_ids),
            AaProgramCourse.is_deleted.is_(False),
        ).order_by(AaProgramCourse.program_id, AaProgramCourse.open_term_no, AaProgramCourse.id).all()
        requirements = db.query(AaProgramGraduationRequirement).filter(
            AaProgramGraduationRequirement.tenant_id == _tid(),
            AaProgramGraduationRequirement.program_id.in_(program_ids),
            AaProgramGraduationRequirement.status == "ACTIVE",
            AaProgramGraduationRequirement.is_deleted.is_(False),
        ).all()
        practices = db.query(AaProgramPracticeSegment).filter(
            AaProgramPracticeSegment.tenant_id == _tid(),
            AaProgramPracticeSegment.program_id.in_(program_ids),
            AaProgramPracticeSegment.status == "ACTIVE",
            AaProgramPracticeSegment.is_deleted.is_(False),
        ).all()
        bindings = db.query(AaProgramBinding).filter(
            AaProgramBinding.tenant_id == _tid(),
            AaProgramBinding.program_id.in_(program_ids),
            AaProgramBinding.status == "ACTIVE",
            AaProgramBinding.is_deleted.is_(False),
        ).all()

        course_ids = sorted({int(row.course_id) for row in courses if row.course_id})
        catalog_rows = db.query(AaCourse).filter(
            AaCourse.tenant_id == _tid(),
            AaCourse.id.in_(course_ids),
            AaCourse.is_deleted.is_(False),
        ).all() if course_ids else []

        prerequisite_codes = set()
        for row in catalog_rows:
            prerequisite_codes.update(
                str(code) for code in validator._safe_json(getattr(row, "prerequisite_codes_json", None), []) if code
            )
        enabled_codes = {
            str(code) for (code,) in db.query(AaCourse.course_code).filter(
                AaCourse.tenant_id == _tid(),
                AaCourse.course_code.in_(sorted(prerequisite_codes)),
                AaCourse.status == "ENABLED",
                AaCourse.is_deleted.is_(False),
            ).all() if code
        } if prerequisite_codes else set()

        major_ids = sorted({int(row.major_id) for row in programs if row.major_id})
        standard_major_ids = {
            int(value) for (value,) in db.query(SchoolMajorStandardBinding.school_major_id).join(
                NationalStandardDocument,
                NationalStandardDocument.id == SchoolMajorStandardBinding.document_id,
            ).filter(
                SchoolMajorStandardBinding.tenant_id == _tid(),
                SchoolMajorStandardBinding.school_major_id.in_(major_ids),
                SchoolMajorStandardBinding.binding_status == "ACTIVE",
                SchoolMajorStandardBinding.is_deleted.is_(False),
                NationalStandardDocument.is_deleted.is_(False),
            ).all() if value
        } if major_ids else set()

        class_ids = sorted({int(row.class_id) for row in bindings if row.class_id})
        classes = db.query(SchoolClass).filter(
            SchoolClass.tenant_id == _tid(),
            SchoolClass.id.in_(class_ids),
            SchoolClass.is_deleted.is_(False),
        ).all() if class_ids else []

        binding_major_ids = sorted({int(row.major_id) for row in bindings if row.major_id})
        conflict_pairs = db.query(AaProgramBinding, AaProgram).join(
            AaProgram,
            AaProgram.id == AaProgramBinding.program_id,
        ).filter(
            AaProgramBinding.tenant_id == _tid(),
            AaProgramBinding.major_id.in_(binding_major_ids),
            AaProgramBinding.status == "ACTIVE",
            AaProgramBinding.is_deleted.is_(False),
            AaProgram.tenant_id == _tid(),
            AaProgram.status.in_(sorted(governance._ACTIVE_PROGRAM_STATUSES)),
            AaProgram.is_deleted.is_(False),
        ).all() if binding_major_ids else []

        courses_by_program = _group(courses, "program_id")
        requirements_by_program = _group(requirements, "program_id")
        practices_by_program = _group(practices, "program_id")
        bindings_by_program = _group(bindings, "program_id")

        items = []
        for row in programs:
            snapshot = _ValidationSnapshotDb(
                program=row,
                courses=courses_by_program.get(int(row.id), []),
                requirements=requirements_by_program.get(int(row.id), []),
                practices=practices_by_program.get(int(row.id), []),
                bindings=bindings_by_program.get(int(row.id), []),
                catalog_rows=catalog_rows,
                enabled_codes=enabled_codes,
                standard_bound=bool(row.major_id and int(row.major_id) in standard_major_ids),
                classes=classes,
                conflict_pairs=conflict_pairs,
            )
            validation = governance.validate_program_db(snapshot, int(row.id))
            items.append({
                "programId": str(row.id),
                "programName": row.program_name,
                "majorId": str(row.major_id or ""),
                "gradeYear": row.grade_year or "",
                "version": row.version,
                "status": row.status,
                "totalCredits": float(row.total_credits) if row.total_credits is not None else None,
                "creditSum": validation["creditSum"],
                "courseCount": validation["courseCount"],
                "blockerCount": validation["counts"]["blocker"],
                "warningCount": validation["counts"]["warning"],
                "canSubmit": validation["canSubmit"],
                "conclusion": validation["conclusion"],
            })

        return {
            "totalPrograms": len(items),
            "readyPrograms": sum(1 for item in items if item["canSubmit"]),
            "blockedPrograms": sum(1 for item in items if not item["canSubmit"]),
            "missingMajor": sum(1 for row in programs if not row.major_id),
            "missingGrade": sum(1 for row in programs if not row.grade_year),
            "items": items,
        }
