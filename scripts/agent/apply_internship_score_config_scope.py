from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGED: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        CHANGED.append(rel)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, got {count}")
    return text.replace(old, new, 1)


def replace_function(text: str, name: str, block: str) -> str:
    match = re.search(rf"(?ms)^def {re.escape(name)}\(.*?(?=^def |\Z)", text)
    if not match:
        raise RuntimeError(f"function not found: {name}")
    return text[:match.start()] + block.rstrip() + "\n\n\n" + text[match.end():].lstrip("\n")


def patch_model() -> None:
    rel = "backend/app/models/internship.py"
    text = read(rel)
    class_match = re.search(r"(?ms)^class InternshipScoreConfig\b.*?(?=^class InternshipFinalScore)", text)
    if not class_match:
        raise RuntimeError("InternshipScoreConfig class not found")
    block = class_match.group(0)
    if "uk_intern_score_cfg_active_scope" not in block:
        block = replace_once(
            block,
            '    __tablename__ = "t_internship_score_config"\n',
            '    __tablename__ = "t_internship_score_config"\n'
            '    __table_args__ = (\n'
            '        UniqueConstraint("tenant_id", "active_scope_key",\n'
            '                         name="uk_intern_score_cfg_active_scope"),\n'
            '    )\n',
            "score config unique",
        )
    if "active_scope_key:" not in block:
        block = replace_once(
            block,
            "    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)\n",
            "    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)\n"
            "    active_scope_key: Mapped[str | None] = mapped_column(\n"
            "        String(80), index=True, comment=\"ACTIVE 配置唯一作用域；历史 RETIRED 置空\")\n",
            "score active scope field",
        )
    text = text[:class_match.start()] + block + text[class_match.end():]
    write(rel, text)


def patch_migration() -> None:
    rel = "backend/alembic/versions/20260803_internship_prod_hardening.py"
    text = read(rel)
    if "def _normalize_score_config_scopes" not in text:
        marker = "\ndef upgrade() -> None:\n"
        helper = '''
def _score_scope_key(batch_id) -> str:
    return f"BATCH:{int(batch_id)}" if batch_id is not None else "TENANT_DEFAULT"


def _normalize_score_config_scopes(bind) -> None:
    rows = bind.execute(sa.text(
        "SELECT id, tenant_id, batch_id FROM t_internship_score_config "
        "WHERE status='ACTIVE' AND is_deleted=0 "
        "ORDER BY tenant_id, batch_id, id DESC"
    )).mappings().all()
    kept: set[tuple[int, int | None]] = set()
    for row in rows:
        group = (int(row["tenant_id"]), int(row["batch_id"]) if row["batch_id"] is not None else None)
        if group in kept:
            bind.execute(sa.text(
                "UPDATE t_internship_score_config SET status='RETIRED', "
                "active_scope_key=NULL WHERE id=:id"
            ), {"id": int(row["id"])})
            continue
        kept.add(group)
        bind.execute(sa.text(
            "UPDATE t_internship_score_config SET active_scope_key=:scope_key WHERE id=:id"
        ), {"scope_key": _score_scope_key(row["batch_id"]), "id": int(row["id"])})
    bind.execute(sa.text(
        "UPDATE t_internship_score_config SET active_scope_key=NULL "
        "WHERE status<>'ACTIVE' OR is_deleted<>0"
    ))
'''
        text = replace_once(text, marker, helper + marker, "score scope migration helper")
    if '"active_scope_key"' not in text[text.index("def upgrade"):text.index("def downgrade")]:
        anchor = '''    _ensure_column(bind, "t_internship_change_request", sa.Column(
        "record_version_snapshot", sa.Integer(), nullable=True))
'''
        addition = anchor + '''    _ensure_column(bind, "t_internship_score_config", sa.Column(
        "active_scope_key", sa.String(80), nullable=True))
    _normalize_score_config_scopes(bind)
    _ensure_unique(
        bind,
        "uk_intern_score_cfg_active_scope",
        "t_internship_score_config",
        ["tenant_id", "active_scope_key"],
    )
'''
        text = replace_once(text, anchor, addition, "score scope migration upgrade")
    downgrade_block = text[text.index("def downgrade"):]
    if "uk_intern_score_cfg_active_scope" not in downgrade_block:
        anchor = '''    for table, name in (
        ("t_risk_record", "uk_risk_source"),
'''
        addition = '''    if "uk_intern_score_cfg_active_scope" in _constraint_names(
        bind, "t_internship_score_config"
    ):
        op.drop_constraint(
            "uk_intern_score_cfg_active_scope",
            "t_internship_score_config",
            type_="unique",
        )
    if "active_scope_key" in _columns(bind, "t_internship_score_config"):
        op.drop_column("t_internship_score_config", "active_scope_key")

''' + anchor
        text = replace_once(text, anchor, addition, "score scope migration downgrade")
    write(rel, text)


def patch_service() -> None:
    rel = "backend/app/modules/internship/services/internship_score_service.py"
    text = read(rel)
    if "def _config_scope_key" not in text:
        marker = "\ndef _active_config(db, batch_id=None):\n"
        helper = '''
def _config_scope_key(batch_id=None) -> str:
    return f"BATCH:{int(batch_id)}" if batch_id not in (None, "") else "TENANT_DEFAULT"


def _active_config(db, batch_id=None, *, lock=False):
'''
        text = replace_once(text, marker, helper, "score service scope helper")
        # Replace the remainder of the old function body separately below.
    active = '''def _active_config(db, batch_id=None, *, lock=False):
    """Batch-specific ACTIVE config wins; tenant default is the explicit fallback."""
    query = select(InternshipScoreConfig).where(
        InternshipScoreConfig.tenant_id == _tid(),
        InternshipScoreConfig.status == "ACTIVE",
        InternshipScoreConfig.is_deleted.is_(False),
        InternshipScoreConfig.active_scope_key == _config_scope_key(batch_id),
    ).order_by(InternshipScoreConfig.id.desc())
    row = db.scalars(query.with_for_update() if lock else query).first()
    if row or batch_id in (None, ""):
        return row
    fallback = select(InternshipScoreConfig).where(
        InternshipScoreConfig.tenant_id == _tid(),
        InternshipScoreConfig.status == "ACTIVE",
        InternshipScoreConfig.is_deleted.is_(False),
        InternshipScoreConfig.active_scope_key == "TENANT_DEFAULT",
    ).order_by(InternshipScoreConfig.id.desc())
    return db.scalars(fallback.with_for_update() if lock else fallback).first()
'''
    text = replace_function(text, "_active_config", active)

    get_cfg = '''def get_config(user=None, batch_id=None) -> dict:
    with session() as db:
        requested_batch_id = int(batch_id) if batch_id not in (None, "") else None
        if requested_batch_id is not None:
            from app.models import InternshipBatch
            batch = db.get(InternshipBatch, requested_batch_id)
            if not batch or batch.is_deleted or batch.tenant_id != _tid():
                raise not_found("实习批次不存在")
        config = _active_config(db, batch_id=requested_batch_id)
        if not config:
            return {
                "checkinWeight": 20, "weeklyWeight": 20, "monthlyWeight": 10,
                "enterpriseWeight": 30, "schoolWeight": 20, "passLine": 60.0,
                "isDefault": True, "configId": "", "configVersion": 0,
                "requestedBatchId": str(requested_batch_id) if requested_batch_id else "",
                "configBatchId": "", "scope": "BUILTIN_DEFAULT",
            }
        config_batch_id = int(config.batch_id) if config.batch_id is not None else None
        return {
            "checkinWeight": config.checkin_weight,
            "weeklyWeight": config.weekly_weight,
            "monthlyWeight": config.monthly_weight,
            "enterpriseWeight": config.enterprise_weight,
            "schoolWeight": config.school_weight,
            "passLine": config.pass_line,
            "isDefault": config_batch_id is None,
            "configId": str(config.id),
            "configVersion": int(config.version or 0),
            "requestedBatchId": str(requested_batch_id) if requested_batch_id else "",
            "configBatchId": str(config_batch_id) if config_batch_id else "",
            "scope": "BATCH" if config_batch_id is not None else "TENANT_DEFAULT",
        }
'''
    text = replace_function(text, "get_config", get_cfg)

    save_start = text.index("def save_config")
    approved_start = text.index("def _approved_enterprise_eval", save_start)
    save_block = text[save_start:approved_start]
    save_block = save_block.replace(
        "        old = _active_config(db, batch_id=batch_id)\n"
        "        if old and old.batch_id == (int(batch_id) if batch_id else None):\n"
        "            old.status = \"RETIRED\"\n"
        "        c = InternshipScoreConfig(tenant_id=_tid(), batch_id=int(batch_id) if batch_id else None,\n"
        "                                  status=\"ACTIVE\")\n",
        "        normalized_batch_id = int(batch_id) if batch_id else None\n"
        "        scope_key = _config_scope_key(normalized_batch_id)\n"
        "        old_rows = db.scalars(select(InternshipScoreConfig).where(\n"
        "            InternshipScoreConfig.tenant_id == _tid(),\n"
        "            InternshipScoreConfig.status == \"ACTIVE\",\n"
        "            InternshipScoreConfig.is_deleted.is_(False),\n"
        "            InternshipScoreConfig.active_scope_key == scope_key,\n"
        "        ).with_for_update()).all()\n"
        "        for old in old_rows:\n"
        "            old.status = \"RETIRED\"\n"
        "            old.active_scope_key = None\n"
        "        c = InternshipScoreConfig(\n"
        "            tenant_id=_tid(), batch_id=normalized_batch_id,\n"
        "            active_scope_key=scope_key, status=\"ACTIVE\")\n",
        1,
    )
    save_block = save_block.replace(
        "        _trail(db, c.id, \"SAVE_CONFIG\", {**parsed, \"passLine\": pass_line}, operator=_op_name(user))\n",
        "        _trail(db, c.id, \"SAVE_CONFIG\", {\n"
        "            **parsed, \"passLine\": pass_line, \"scopeKey\": scope_key,\n"
        "        }, operator=_op_name(user))\n",
        1,
    )
    text = text[:save_start] + save_block + text[approved_start:]
    write(rel, text)


def patch_router() -> None:
    rel = "backend/app/modules/internship/routers/internship.py"
    text = read(rel)
    old = '''@router.get("/scores/config", summary="成绩权重配置（五项权重，和=100）")
def score_config_get(user=Depends(require_permission("internship.score.view"))):
    return success(score.get_config(user=user))
'''
    new = '''@router.get("/scores/config", summary="成绩权重配置（五项权重，和=100）")
def score_config_get(batchId: Optional[str] = None,
                     user=Depends(require_permission("internship.score.view"))):
    return success(score.get_config(user=user, batch_id=batchId))
'''
    text = replace_once(text, old, new, "score config router")
    write(rel, text)


def add_tests() -> None:
    rel = "backend/tests/test_internship_score_config_scope_static.py"
    content = '''from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_score_config_has_unique_active_scope_key():
    model = _read("backend/app/models/internship.py")
    block = model[model.index("class InternshipScoreConfig"):model.index("class InternshipFinalScore")]
    assert "active_scope_key" in block
    assert "uk_intern_score_cfg_active_scope" in block


def test_score_config_get_is_batch_aware():
    service = _read(
        "backend/app/modules/internship/services/internship_score_service.py"
    )
    get_block = service[service.index("def get_config"):service.index("def save_config")]
    assert "batch_id=None" in get_block
    assert "requestedBatchId" in get_block
    assert "configBatchId" in get_block
    router = _read("backend/app/modules/internship/routers/internship.py")
    route = router[router.index('@router.get("/scores/config"'):router.index('@router.post("/scores/config"')]
    assert "batchId" in route
    assert "batch_id=batchId" in route


def test_score_config_save_retires_locked_scope_before_insert():
    service = _read(
        "backend/app/modules/internship/services/internship_score_service.py"
    )
    block = service[service.index("def save_config"):service.index("def _approved_enterprise_eval")]
    assert "active_scope_key == scope_key" in block
    assert ".with_for_update()" in block
    assert "old.active_scope_key = None" in block
    assert "active_scope_key=scope_key" in block
'''
    write(rel, content)


def main() -> None:
    patch_model()
    patch_migration()
    patch_service()
    patch_router()
    add_tests()
    for rel in CHANGED:
        if rel.endswith(".py"):
            ast.parse(read(rel), filename=rel)
    print("changed files:")
    for rel in CHANGED:
        print(f" - {rel}")
    if not CHANGED:
        print("score config scope hardening already applied")


if __name__ == "__main__":
    main()
