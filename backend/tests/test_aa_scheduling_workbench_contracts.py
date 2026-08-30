from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SERVICE = ROOT / "app/modules/academic_affairs/services/academic_affairs_scheduling_public_service.py"


def test_workbench_extends_the_canonical_publish_gate_instead_of_replacing_it():
    source = PUBLIC_SERVICE.read_text(encoding="utf-8")

    assert "gate_service.evaluate(db, batch)" in source
    assert '"taskQueue"' in source
    assert '"workflow"' in source
    assert '"currentStageKey"' in source
    assert '"nextAction"' in source


def test_published_batch_wide_defects_route_to_reissue_not_single_item_changes():
    source = PUBLIC_SERVICE.read_text(encoding="utf-8")

    assert 'batch.status == "PUBLISHED" and not result["complete"]' in source
    assert '"code": "BATCH_REISSUE"' in source
    assert "不能用单课位调停课掩盖" in source


def test_workbench_queue_is_bounded_and_does_not_expose_raw_ids_for_entry():
    source = PUBLIC_SERVICE.read_text(encoding="utf-8")

    assert "queue_source[:100]" in source
    assert '"taskQueueTotal": len(queue_source)' in source
    assert '"canSchedule": not invalid and batch.status == "DRAFT"' in source
