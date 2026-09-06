from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_material_status_projection_never_returns_unknown_machine_value():
    source = (ROOT/'backend/app/modules/student_affairs/services/affairs_material_center_service.py').read_text(encoding='utf-8')
    assert 'MATERIAL_STATUS_LABELS.get(row.status, "状态待确认")' in source
    assert 'SUBMISSION_STATUS_LABELS.get(row.status, "状态待确认")' in source
    assert '.get(row.status, row.status)' not in source
