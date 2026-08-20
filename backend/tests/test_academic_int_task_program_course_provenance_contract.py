"""Source contract for the INT TeachingTask -> ProgramCourse provenance handoff."""
from __future__ import annotations

import inspect
from pathlib import Path


VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revision_text(revision: str) -> str:
    marker = f'revision = "{revision}"'
    matches = []
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(line.strip() == marker for line in text.splitlines()):
            matches.append((path, text))
    assert len(matches) == 1, [str(path) for path, _ in matches]
    return matches[0][1]


def test_provenance_migration_is_nullable_expand_only_after_program_series():
    text = _revision_text("20260818_acad_int_task_pc_prov")
    compact = "".join(text.split())
    upper = text.upper()
    assert 'down_revision="20260817_acad_int_program_series"' in compact
    assert '"source_program_course_id"' in text
    assert "nullable=True" in compact
    assert "UPDATE T_AA_TEACHING_TASK" not in upper
    assert "LEGACY-" not in text


def test_task_model_keeps_historical_source_nullable_without_guess_index():
    from app.models import AaTeachingTask

    column = AaTeachingTask.__table__.c.source_program_course_id
    assert column.nullable is True
    assert column.index in (None, False)


def test_canonical_generation_writes_exact_program_course_id_and_same_row_formation():
    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as generation

    source = inspect.getsource(generation.generate_batch_tx)
    assert "source_program_course_id=program_course.id" in source
    assert "formation_mode=formation_mode" in source
    assert "formation_mode = _snapshot_program_course_formation(program_course)" in source
    assert source.index("formation_mode = _snapshot_program_course_formation(program_course)") < source.index("source_program_course_id=program_course.id")


def test_a_owned_consumer_never_infers_source_from_weak_runtime_facts():
    from app.modules.academic_affairs.services import academic_affairs_task_formation_provenance_service as service

    source = inspect.getsource(service.resolve_task_formation_snapshot)
    assert "source_program_course_id" in source
    assert "AaProgramCourse.id == int(source_id)" in source
    assert "AaProgramBinding" not in source
    assert "SchoolClass" not in source
    assert "resolve_program_for_scope" not in source
    assert "major_id" not in source
    assert "grade_year" not in source
