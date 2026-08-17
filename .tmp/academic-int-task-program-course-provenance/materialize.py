from __future__ import annotations

from pathlib import Path

BASE = "fc6029e0af973a679c3ecd9c9dae40dcc46c73ff"


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"exact replacement guard failed for {path}: count={count}\nanchor={old[:220]!r}")
    write(path, text.replace(old, new, 1))


# 1) Direct persisted TeachingTask -> ProgramCourse provenance. Historical rows stay NULL.
model = "backend/app/models/academic_affairs.py"
replace_once(
    model,
    '    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)\n'
    '    formation_mode: Mapped[str | None] = mapped_column(\n',
    '    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)\n'
    '    source_program_course_id: Mapped[int | None] = mapped_column(\n'
    '        BigInteger, nullable=True,\n'
    '        comment="INT direct provenance: exact t_aa_program_course.id used when this task was generated; legacy unresolved stays NULL",\n'
    '    )\n'
    '    formation_mode: Mapped[str | None] = mapped_column(\n',
)

# 2) Canonical generation snapshots the exact ProgramCourse row already in hand.
generation = "backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py"
replace_once(
    generation,
    'from . import academic_affairs_program_activation_service as program_activation\n'
    'from . import academic_affairs_task_core_service as core\n',
    'from . import academic_affairs_program_activation_service as program_activation\n'
    'from . import academic_affairs_task_core_service as core\n'
    'from .academic_affairs_task_formation_policy import normalize_formation_mode\n',
)
replace_once(
    generation,
    '\n\ndef generate_batch_tx(db, body, user) -> dict:\n',
    '\n\ndef _snapshot_program_course_formation(program_course) -> str | None:\n'
    '    """Copy only the explicit source-row formation; missing legacy truth stays NULL."""\n'
    '    try:\n'
    '        return normalize_formation_mode(getattr(program_course, "formation_mode", None))\n'
    '    except ValueError as exc:\n'
    '        raise AppException(\n'
    '            "DATA_CONFLICT",\n'
    '            "培养方案课程的 formationMode 非法，禁止生成带伪来源的教学任务",\n'
    '            details={\n'
    '                "blocker": "PROGRAM_COURSE_FORMATION_INVALID",\n'
    '                "programCourseId": str(getattr(program_course, "id", "") or ""),\n'
    '                "formationMode": str(getattr(program_course, "formation_mode", "") or ""),\n'
    '            },\n'
    '            http_status=409,\n'
    '        ) from exc\n'
    '\n\ndef generate_batch_tx(db, body, user) -> dict:\n',
)
replace_once(
    generation,
    '                    if not course or course.is_deleted or course.tenant_id != _tid():\n'
    '                        unresolved_program_courses += 1\n'
    '                        continue\n'
    '                    total_hours = int(course.hours_total or 0)\n',
    '                    if not course or course.is_deleted or course.tenant_id != _tid():\n'
    '                        unresolved_program_courses += 1\n'
    '                        continue\n'
    '                    formation_mode = _snapshot_program_course_formation(program_course)\n'
    '                    total_hours = int(course.hours_total or 0)\n',
)
replace_once(
    generation,
    '                        course_code=course_code, course_name=course_name,\n'
    '                        class_id=school_class.id,\n'
    '                        teaching_class_code=core._teaching_class_code(term_id, course_code, school_class.id),\n',
    '                        course_code=course_code, course_name=course_name,\n'
    '                        class_id=school_class.id,\n'
    '                        source_program_course_id=program_course.id,\n'
    '                        formation_mode=formation_mode,\n'
    '                        teaching_class_code=core._teaching_class_code(term_id, course_code, school_class.id),\n',
)

# 3) Expand-only DDL; no historical provenance fabrication.
write(
    "backend/alembic/versions/20260818_academic_int_task_program_course_provenance.py",
    '''"""Add direct TeachingTask -> ProgramCourse provenance.\n\nRevision ID: 20260818_acad_int_task_pc_prov\nRevises: 20260817_acad_int_program_series\n\nHistorical tasks deliberately remain NULL.  The canonical generator writes the exact\nProgramCourse id for future tasks; this migration performs no semantic backfill.\n"""\nfrom __future__ import annotations\n\nfrom alembic import op\nimport sqlalchemy as sa\n\nrevision = "20260818_acad_int_task_pc_prov"\ndown_revision = "20260817_acad_int_program_series"\nbranch_labels = None\ndepends_on = None\n\n\ndef upgrade() -> None:\n    op.add_column(\n        "t_aa_teaching_task",\n        sa.Column(\n            "source_program_course_id",\n            sa.BigInteger(),\n            nullable=True,\n            comment="Exact t_aa_program_course.id used by canonical generation; legacy unresolved stays NULL",\n        ),\n    )\n\n\ndef downgrade() -> None:\n    op.drop_column("t_aa_teaching_task", "source_program_course_id")\n''',
)

# 4) A-owned consumer DTO: direct-id lookup only; never infer from class/course/current Program.
write(
    "backend/app/modules/academic_affairs/services/academic_affairs_task_formation_provenance_service.py",
    '''"""A-owned TeachingTask formation provenance consumer boundary.\n\nOnly a persisted ``source_program_course_id`` may establish ProgramCourse provenance.\nCourse/class labels, current Program activation, major/grade and task-majority heuristics\nare deliberately excluded.  Legacy/incomplete rows remain UNKNOWN; contradictory direct\nlinks are CONFLICT.\n"""\nfrom __future__ import annotations\n\nfrom sqlalchemy import select\n\nfrom app.core.exceptions import not_found\nfrom app.services.db_service import _tid, session\n\nfrom .academic_affairs_task_formation_policy import normalize_formation_mode\n\nSTATUS_PROVEN = "PROVEN"\nSTATUS_UNKNOWN = "UNKNOWN"\nSTATUS_CONFLICT = "CONFLICT"\n\n\ndef _snapshot(task, *, status: str, source_id=None, formation_mode=None, blockers=()) -> dict:\n    return {\n        "status": status,\n        "teachingTaskId": str(task.id),\n        "sourceProgramCourseId": str(source_id or ""),\n        "formationMode": str(formation_mode or ""),\n        "blockers": list(blockers),\n    }\n\n\ndef _normalized(value):\n    try:\n        return normalize_formation_mode(value), None\n    except ValueError:\n        return None, "FORMATION_MODE_INVALID"\n\n\ndef resolve_task_formation_snapshot(db, task_id, *, tenant_id: int) -> dict:\n    """Return B-consumable provenance from the persisted direct source link only."""\n    try:\n        tid = int(tenant_id)\n        task_pk = int(task_id)\n    except (TypeError, ValueError) as exc:\n        raise ValueError("positive tenant_id and task_id are required") from exc\n    if tid <= 0 or task_pk <= 0:\n        raise ValueError("positive tenant_id and task_id are required")\n\n    from app.models import AaProgramCourse, AaTeachingTask\n\n    task = db.scalars(select(AaTeachingTask).where(\n        AaTeachingTask.id == task_pk,\n        AaTeachingTask.tenant_id == tid,\n        AaTeachingTask.is_deleted.is_(False),\n    )).first()\n    if not task:\n        raise not_found("教学任务不存在")\n\n    source_id = getattr(task, "source_program_course_id", None)\n    task_mode, task_error = _normalized(getattr(task, "formation_mode", None))\n    if task_error:\n        return _snapshot(\n            task, status=STATUS_CONFLICT, source_id=source_id,\n            formation_mode=getattr(task, "formation_mode", None),\n            blockers=("TASK_FORMATION_MODE_INVALID",),\n        )\n    if not source_id:\n        return _snapshot(\n            task, status=STATUS_UNKNOWN, formation_mode=task_mode,\n            blockers=("SOURCE_PROGRAM_COURSE_ID_MISSING",),\n        )\n\n    source = db.scalars(select(AaProgramCourse).where(\n        AaProgramCourse.id == int(source_id),\n        AaProgramCourse.tenant_id == tid,\n        AaProgramCourse.is_deleted.is_(False),\n    )).first()\n    if not source:\n        return _snapshot(\n            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,\n            blockers=("SOURCE_PROGRAM_COURSE_NOT_FOUND",),\n        )\n\n    source_mode, source_error = _normalized(getattr(source, "formation_mode", None))\n    if source_error:\n        return _snapshot(\n            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,\n            blockers=("SOURCE_PROGRAM_COURSE_FORMATION_INVALID",),\n        )\n    if int(getattr(source, "course_id", 0) or 0) != int(getattr(task, "course_id", 0) or 0):\n        return _snapshot(\n            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,\n            blockers=("SOURCE_PROGRAM_COURSE_COURSE_MISMATCH",),\n        )\n    if not task_mode or not source_mode:\n        return _snapshot(\n            task, status=STATUS_UNKNOWN, source_id=source_id, formation_mode=task_mode,\n            blockers=("FORMATION_MODE_UNRESOLVED",),\n        )\n    if task_mode != source_mode:\n        return _snapshot(\n            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,\n            blockers=("TASK_SOURCE_FORMATION_MISMATCH",),\n        )\n\n    return _snapshot(\n        task, status=STATUS_PROVEN, source_id=source_id, formation_mode=task_mode,\n    )\n\n\ndef get_task_formation_snapshot(task_id) -> dict:\n    """Request-context convenience facade; internal callers may share their DB session above."""\n    with session() as db:\n        return resolve_task_formation_snapshot(db, task_id, tenant_id=_tid())\n''',
)

# 5) Source/shape contract plus focused MySQL consumer truth.
write(
    "backend/tests/test_academic_int_task_program_course_provenance_contract.py",
    '''"""Source contract for the INT TeachingTask -> ProgramCourse provenance handoff."""\nfrom __future__ import annotations\n\nimport inspect\nfrom pathlib import Path\n\n\nVERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"\n\n\ndef _revision_text(revision: str) -> str:\n    marker = f'revision = "{revision}"'\n    matches = []\n    for path in VERSIONS.glob("*.py"):\n        text = path.read_text(encoding="utf-8")\n        if any(line.strip() == marker for line in text.splitlines()):\n            matches.append((path, text))\n    assert len(matches) == 1, [str(path) for path, _ in matches]\n    return matches[0][1]\n\n\ndef test_provenance_migration_is_nullable_expand_only_after_program_series():\n    text = _revision_text("20260818_acad_int_task_pc_prov")\n    compact = "".join(text.split())\n    upper = text.upper()\n    assert 'down_revision="20260817_acad_int_program_series"' in compact\n    assert '"source_program_course_id"' in text\n    assert "nullable=True" in compact\n    assert "UPDATE T_AA_TEACHING_TASK" not in upper\n    assert "LEGACY-" not in text\n\n\ndef test_task_model_keeps_historical_source_nullable_without_guess_index():\n    from app.models import AaTeachingTask\n\n    column = AaTeachingTask.__table__.c.source_program_course_id\n    assert column.nullable is True\n    assert column.index in (None, False)\n\n\ndef test_canonical_generation_writes_exact_program_course_id_and_same_row_formation():\n    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as generation\n\n    source = inspect.getsource(generation.generate_batch_tx)\n    assert "source_program_course_id=program_course.id" in source\n    assert "formation_mode=formation_mode" in source\n    assert "formation_mode = _snapshot_program_course_formation(program_course)" in source\n    assert source.index("formation_mode = _snapshot_program_course_formation(program_course)") < source.index("source_program_course_id=program_course.id")\n\n\ndef test_a_owned_consumer_never_infers_source_from_weak_runtime_facts():\n    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service\n\n    source = inspect.getsource(service.resolve_task_formation_snapshot)\n    assert "source_program_course_id" in source\n    assert "AaProgramCourse.id == int(source_id)" in source\n    assert "AaProgramBinding" not in source\n    assert "SchoolClass" not in source\n    assert "resolve_program_for_scope" not in source\n    assert "major_id" not in source\n    assert "grade_year" not in source\n''',
)

write(
    "backend/tests/test_academic_int_task_program_course_provenance_mysql.py",
    '''"""Focused MySQL truth for direct TeachingTask -> ProgramCourse provenance."""\nfrom __future__ import annotations\n\nimport uuid\n\nimport pytest\n\nTID = 1000000000000000001\nOTHER_TID = 1000000000000000002\n\n\ndef _rows(db, *, source_mode="SELECTABLE", task_mode="SELECTABLE", task_course_id=7001, source_course_id=7001, source_tenant=TID):\n    from app.models import AaProgramCourse, AaTeachingTask\n\n    source = AaProgramCourse(\n        tenant_id=source_tenant,\n        program_id=8001,\n        course_id=source_course_id,\n        course_name=f"PROV-{uuid.uuid4().hex[:6]}",\n        open_term_no=1,\n        module="MAJOR_CORE",\n        credit_snapshot=2,\n        formation_mode=source_mode,\n    )\n    db.add(source)\n    db.flush()\n    task = AaTeachingTask(\n        tenant_id=TID,\n        batch_id=9001,\n        course_id=task_course_id,\n        course_code="PROV101",\n        course_name="来源链测试",\n        source_program_course_id=source.id,\n        formation_mode=task_mode,\n        status="PENDING_ASSIGN",\n    )\n    db.add(task)\n    db.commit()\n    return int(source.id), int(task.id)\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_complete_direct_snapshot_is_proven_and_matches_b_contract():\n    from app.db.session import get_sessionmaker\n    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service\n\n    db = get_sessionmaker()()\n    source_id, task_id = _rows(db)\n    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)\n    assert snapshot == {\n        "status": "PROVEN",\n        "teachingTaskId": str(task_id),\n        "sourceProgramCourseId": str(source_id),\n        "formationMode": "SELECTABLE",\n        "blockers": [],\n    }\n    db.close()\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_legacy_task_without_direct_source_stays_unknown_and_is_not_rewritten():\n    from app.db.session import get_sessionmaker\n    from app.models import AaTeachingTask\n    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service\n\n    db = get_sessionmaker()()\n    task = AaTeachingTask(\n        tenant_id=TID, batch_id=9002, course_id=7002, course_code="LEG101",\n        course_name="旧任务", source_program_course_id=None, formation_mode="ADMIN_FIXED",\n        status="PENDING_ASSIGN",\n    )\n    db.add(task)\n    db.commit()\n    task_id = int(task.id)\n    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)\n    assert snapshot["status"] == "UNKNOWN"\n    assert snapshot["sourceProgramCourseId"] == ""\n    assert snapshot["blockers"] == ["SOURCE_PROGRAM_COURSE_ID_MISSING"]\n    db.expire_all()\n    assert db.get(AaTeachingTask, task_id).source_program_course_id is None\n    db.close()\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_direct_source_course_mismatch_is_conflict_not_inference():\n    from app.db.session import get_sessionmaker\n    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service\n\n    db = get_sessionmaker()()\n    source_id, task_id = _rows(db, task_course_id=7101, source_course_id=7102)\n    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)\n    assert snapshot["status"] == "CONFLICT"\n    assert snapshot["sourceProgramCourseId"] == str(source_id)\n    assert snapshot["blockers"] == ["SOURCE_PROGRAM_COURSE_COURSE_MISMATCH"]\n    db.close()\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_direct_source_formation_mismatch_is_conflict():\n    from app.db.session import get_sessionmaker\n    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service\n\n    db = get_sessionmaker()()\n    _source_id, task_id = _rows(db, source_mode="ADMIN_FIXED", task_mode="SELECTABLE")\n    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)\n    assert snapshot["status"] == "CONFLICT"\n    assert snapshot["blockers"] == ["TASK_SOURCE_FORMATION_MISMATCH"]\n    db.close()\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_direct_source_with_unresolved_formation_stays_unknown():\n    from app.db.session import get_sessionmaker\n    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service\n\n    db = get_sessionmaker()()\n    source_id, task_id = _rows(db, source_mode=None, task_mode=None)\n    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)\n    assert snapshot["status"] == "UNKNOWN"\n    assert snapshot["sourceProgramCourseId"] == str(source_id)\n    assert snapshot["formationMode"] == ""\n    assert snapshot["blockers"] == ["FORMATION_MODE_UNRESOLVED"]\n    db.close()\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_cross_tenant_direct_source_is_not_accepted_as_provenance():\n    from app.db.session import get_sessionmaker\n    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service\n\n    db = get_sessionmaker()()\n    source_id, task_id = _rows(db, source_tenant=OTHER_TID)\n    snapshot = service.resolve_task_formation_snapshot(db, task_id, tenant_id=TID)\n    assert snapshot["status"] == "CONFLICT"\n    assert snapshot["sourceProgramCourseId"] == str(source_id)\n    assert snapshot["blockers"] == ["SOURCE_PROGRAM_COURSE_NOT_FOUND"]\n    db.close()\n''',
)

print("materialized TeachingTask -> ProgramCourse provenance candidate")
