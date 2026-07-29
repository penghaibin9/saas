from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_new_leave_records_use_only_student_profile_identity():
    model = read("backend/app/models/campus_service.py")
    service = read("backend/app/services/affairs_leave_service.py")
    assert "cs_student_id: Mapped[int | None]" in model
    assert "cs_student_id=None, student_id=student_id" in service
    assert "cs_student_id=0, student_id=student_id" not in service


def test_leave_identity_migration_is_single_head_successor():
    migration = read("backend/alembic/versions/0144_affairs_leave_identity_cutover.py")
    assert 'revision = "0144_affairs_leave_identity_cutover"' in migration
    assert 'down_revision = "0143_merge_affairs_material_ops"' in migration
    assert '"t_cs_leave"' in migration
    assert '"cs_student_id"' in migration
    assert "nullable=True" in migration
