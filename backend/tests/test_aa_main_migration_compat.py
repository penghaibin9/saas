"""教务迁移链必须与当前 main 的毕设、实习、学工和学生账号迁移链收敛为单 head。"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND = Path(__file__).resolve().parents[1]
VERSIONS = BACKEND / "alembic" / "versions"


def _source(filename: str) -> str:
    return (VERSIONS / filename).read_text(encoding="utf-8")


def _script() -> ScriptDirectory:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(config)


def test_current_main_merge_migrations_are_preserved():
    main_merge = _source("0141_merge_gd_intern_affairs_heads.py")
    main_head = _source("0142_gd_excellent_delay_workflows.py")

    assert 'revision = "0141_merge_gd_intern_affairs_heads"' in main_merge
    for parent in (
        "gd_r3_audit_context",
        "0140_intern_batch_participant",
        "0139_affairs_money_decimal",
        "student_c1_account_link",
    ):
        assert f'"{parent}"' in main_merge

    assert 'revision = "0142_gd_excellent_delay"' in main_head
    assert 'down_revision = "0141_merge_gd_intern_affairs_heads"' in main_head


def test_main_merge_parents_exist_on_long_lived_branch():
    expected = {
        "gd_r3_audit_context.py": "gd_r3_audit_context",
        "0140_internship_batch_participant.py": "0140_intern_batch_participant",
        "0139_affairs_money_decimal.py": "0139_affairs_money_decimal",
        "student_c1_account_link.py": "student_c1_account_link",
    }
    for filename, revision in expected.items():
        source = _source(filename)
        assert f'revision = "{revision}"' in source


def test_academic_and_current_main_heads_are_joined_without_ddl():
    script = _script()
    heads = script.get_heads()
    assert len(heads) == 1

    reachable = {
        revision.revision
        for revision in script.walk_revisions(base="base", head=heads)
    }
    assert "0134_aa_makeup_source_identity" in reachable
    assert "0142_gd_excellent_delay" in reachable

    head = script.get_revision(heads[0])
    parents = head.down_revision
    assert isinstance(parents, tuple)
    assert len(parents) >= 2

    source = Path(head.path).read_text(encoding="utf-8")
    assert "def upgrade" in source
    assert "def downgrade" in source
    assert "op." not in source


def test_alembic_graph_has_exactly_one_head():
    assert len(_script().get_heads()) == 1
