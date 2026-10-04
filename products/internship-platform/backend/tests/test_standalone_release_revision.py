"""Current release pins must agree; historical migration checkpoints stay fixed."""
from pathlib import Path
import runpy

import pytest


PRODUCT = Path(__file__).resolve().parents[2]
REPOSITORY = PRODUCT.parents[1]
CONTRACT = runpy.run_path(str(PRODUCT / "scripts/check_schema_revision_contract.py"))
check_contract = CONTRACT["check_contract"]
migration_head = CONTRACT["migration_head"]
CURRENT_PATHS = (
    *CONTRACT["CURRENT_PRODUCT_FILES"],
    *(Path(".github/workflows") / name for name in CONTRACT["CURRENT_WORKFLOWS"]),
)


@pytest.fixture
def release_repository(tmp_path):
    versions = tmp_path / CONTRACT["PRODUCT"] / "backend/alembic/versions"
    versions.mkdir(parents=True)
    (versions / "0001.py").write_text("revision='ix0001'\ndown_revision=None\n", encoding="utf-8")
    (versions / "0026.py").write_text("revision='ix0026'\ndown_revision='ix0001'\n", encoding="utf-8")
    for relative in CURRENT_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("EXPECTED_ALEMBIC_REVISION=ix0026\n", encoding="utf-8")
    return tmp_path


def test_production_expected_revision_matches_standalone_migration_head():
    head, paths, errors = check_contract(REPOSITORY)
    assert head
    assert len(paths) >= len(CURRENT_PATHS)
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("relative", CURRENT_PATHS, ids=lambda path: path.name)
def test_every_current_release_consumer_rejects_stale_revision(release_repository, relative):
    (release_repository / relative).write_text("EXPECTED_ALEMBIC_REVISION=ix0023\n", encoding="utf-8")
    head, _, errors = check_contract(release_repository)
    assert head == "ix0026"
    assert len(errors) == 1
    assert relative.as_posix() in errors[0]


def test_detects_new_migration_without_updated_consumers(release_repository):
    versions = release_repository / CONTRACT["PRODUCT"] / "backend/alembic/versions"
    (versions / "0027.py").write_text("revision='ix0027'\ndown_revision='ix0026'\n", encoding="utf-8")
    head, paths, errors = check_contract(release_repository)
    assert head == "ix0027"
    assert len(errors) == len(paths)


def test_reads_alembic_typed_revision_assignments(release_repository):
    versions = release_repository / CONTRACT["PRODUCT"] / "backend/alembic/versions"
    (versions / "0027.py").write_text(
        "revision: str = 'ix0027'\ndown_revision: str | None = 'ix0026'\n", encoding="utf-8"
    )
    assert migration_head(versions) == "ix0027"


def test_discovers_new_current_workflow(release_repository):
    path = release_repository / ".github/workflows/internship-standalone-new-current.yml"
    path.write_text("EXPECTED_ALEMBIC_REVISION: ix0023\n", encoding="utf-8")
    _, paths, errors = check_contract(release_repository)
    assert path.relative_to(release_repository) in paths
    assert len(errors) == 1


def test_rejects_stale_restore_receipt_assertion(release_repository):
    path = release_repository / CONTRACT["PRODUCT"] / "scripts/c09_recovery_drill_ci.sh"
    path.write_text(
        "EXPECTED_ALEMBIC_REVISION=ix0026\nassert data['alembicRevision'] == 'ix0023'\n",
        encoding="utf-8",
    )
    _, _, errors = check_contract(release_repository)
    assert len(errors) == 1
    assert "ix0023" in errors[0]


def test_rejects_missing_current_consumer(release_repository):
    path = release_repository / CURRENT_PATHS[0]
    path.unlink()
    _, _, errors = check_contract(release_repository)
    assert len(errors) == 1
    assert "缺少当前运行版本配置" in errors[0]


def test_rejects_unpinned_current_consumer(release_repository):
    (release_repository / CURRENT_PATHS[0]).write_text("EXPECTED_ALEMBIC_REVISION=\n", encoding="utf-8")
    _, _, errors = check_contract(release_repository)
    assert len(errors) == 1
    assert "缺少固定的当前期望版本" in errors[0]


@pytest.mark.parametrize(
    "declaration",
    (
        "EXPECTED_ALEMBIC_REVISION: ${EXPECTED_ALEMBIC_REVISION:-ix0026}\n",
        'EXPECTED_ALEMBIC_REVISION="${EXPECTED_ALEMBIC_REVISION:-ix0026}"\n',
        "EXPECTED_ALEMBIC_REVISION: ix0026\n",
    ),
)
def test_accepts_current_compose_shell_and_workflow_pins(release_repository, declaration):
    (release_repository / CURRENT_PATHS[0]).write_text(declaration, encoding="utf-8")
    _, _, errors = check_contract(release_repository)
    assert not errors


def test_preserves_historical_upgrade_checkpoints(release_repository):
    path = release_repository / ".github/workflows/internship-standalone-c02.yml"
    path.write_text("alembic upgrade ix0004\nassert version == 'ix0004'\n", encoding="utf-8")
    _, paths, errors = check_contract(release_repository)
    assert path.relative_to(release_repository) not in paths
    assert not errors


@pytest.mark.parametrize(
    ("migration", "message"),
    (
        ("revision='ix0026'\ndown_revision='ix0001'\n", "重复"),
        ("revision='ix0027'\ndown_revision='ix0001'\n", "唯一最高版本"),
        ("revision='ix0027'\ndown_revision='ix0099'\n", "缺少上级版本"),
        ("revision='ix0027'\ndown_revision=None\n", "唯一最高版本"),
    ),
)
def test_rejects_broken_or_ambiguous_installation_graph(release_repository, migration, message):
    versions = release_repository / CONTRACT["PRODUCT"] / "backend/alembic/versions"
    (versions / "new.py").write_text(migration, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        migration_head(versions)
