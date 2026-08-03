from pathlib import Path

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
