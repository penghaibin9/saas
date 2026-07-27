from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def cutover_model_and_writer() -> None:
    model_path = "backend/app/models/campus_service.py"
    model = _read(model_path)
    old = "    cs_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)\n"
    new = "    cs_student_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)\n"
    if old in model:
        model = model.replace(old, new, 1)
    elif new not in model:
        raise RuntimeError("CsLeave.cs_student_id model anchor missing")
    _write(model_path, model)

    service_path = "backend/app/services/affairs_leave_service.py"
    service = _read(service_path)
    old = "        x = CsLeave(tenant_id=_tid(), cs_student_id=0, student_id=student_id,\n"
    new = "        x = CsLeave(tenant_id=_tid(), cs_student_id=None, student_id=student_id,\n"
    if old in service:
        service = service.replace(old, new, 1)
    elif new not in service:
        raise RuntimeError("formal leave writer still has unknown legacy identity form")
    _write(service_path, service)


def write_migration() -> None:
    path = ROOT / "backend/alembic/versions/0144_affairs_leave_identity_cutover.py"
    content = '''"""Stop writing legacy campus-service student identity for new leave records.

Revision ID: 0144_affairs_leave_identity_cutover
Revises: 0143_merge_affairs_material_ops
"""
from alembic import op
import sqlalchemy as sa


revision = "0144_affairs_leave_identity_cutover"
down_revision = "0143_merge_affairs_material_ops"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "t_cs_leave",
        "cs_student_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade():
    # Historical rows retain their original value. New rows created after the cutover
    # intentionally have NULL here, so a safe downgrade must map only those rows to the
    # old sentinel before restoring NOT NULL.
    op.execute("UPDATE t_cs_leave SET cs_student_id = 0 WHERE cs_student_id IS NULL")
    op.alter_column(
        "t_cs_leave",
        "cs_student_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
'''
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise RuntimeError(f"migration already exists with unexpected content: {path}")
    path.write_text(content, encoding="utf-8")


def write_contract_test() -> None:
    path = ROOT / "backend/tests/test_affairs_leave_identity_cutover_contract.py"
    path.write_text(
        '''from pathlib import Path


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
''',
        encoding="utf-8",
    )


def audit() -> None:
    model = _read("backend/app/models/campus_service.py")
    service = _read("backend/app/services/affairs_leave_service.py")
    if "cs_student_id: Mapped[int | None]" not in model:
        raise RuntimeError("legacy leave identity column is still non-null in ORM")
    if "cs_student_id=None, student_id=student_id" not in service:
        raise RuntimeError("new leave writer still writes legacy identity sentinel")
    if not (ROOT / "backend/alembic/versions/0144_affairs_leave_identity_cutover.py").exists():
        raise RuntimeError("leave identity migration missing")


def run() -> None:
    cutover_model_and_writer()
    write_migration()
    write_contract_test()
    audit()


if __name__ == "__main__":
    run()
    print("leave identity cutover audit passed")
