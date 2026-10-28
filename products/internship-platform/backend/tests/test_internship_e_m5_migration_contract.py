from __future__ import annotations

import ast
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
VERSIONS=HERE/"alembic"/"versions"


def _assignments(path: Path):
    tree=ast.parse(path.read_text(encoding="utf-8"))
    out={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            try: out[node.targets[0].id]=ast.literal_eval(node.value)
            except Exception: pass
    return out


def test_e_series_migration_lineage_is_linear_through_m5():
    files={
        "m1": VERSIONS/"20260815_internship_e_m1_authority.py",
        "m3": VERSIONS/"20260815_internship_e_m3_material_snapshot.py",
        "m4": VERSIONS/"20260815_internship_e_m4_volunteer_group.py",
        "pos": VERSIONS/"20260815_internship_e_position_campaign.py",
        "m5": VERSIONS/"20260815_internship_e_m5_decision_placement.py",
    }
    meta={key:_assignments(path) for key,path in files.items()}
    assert meta["m3"]["down_revision"]==meta["m1"]["revision"]
    assert meta["m4"]["down_revision"]==meta["m3"]["revision"]
    assert meta["pos"]["down_revision"]==meta["m4"]["revision"]
    assert meta["m5"]["down_revision"]==meta["pos"]["revision"]


def test_m5_has_decision_effect_state_and_append_only_placement_guards():
    text=(VERSIONS/"20260815_internship_e_m5_decision_placement.py").read_text(encoding="utf-8")
    assert '"t_internship_enterprise_application_decision"' in text
    assert '"effect_status"' in text and '"valid_until"' in text and '"superseded_reason"' in text
    assert '"t_internship_placement_snapshot"' in text
    assert '"current_placement_snapshot_id"' in text
    assert "trg_intern_placement_snapshot_no_update" in text
    assert "trg_intern_placement_snapshot_no_delete" in text
    assert "INTERNSHIP_PLACEMENT_SNAPSHOT_IMMUTABLE" in text
