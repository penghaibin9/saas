from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_alembic_graph_merges_latest_main_and_affairs_operations():
    merge = _read("backend/alembic/versions/0143_merge_affairs_material_ops.py")
    assert 'revision = "0143_merge_affairs_material_ops"' in merge
    assert '"0142_gd_excellent_delay"' in merge
    assert '"0127_affairs_material_batch_ops"' in merge


def test_miniapp_request_keeps_internship_context_and_affairs_file_recovery():
    request = _read("miniapp/src/services/request.js")
    assert "X-Internship-Batch-Id" in request
    assert "gx_student_internship_batch_v1" in request
    assert "export function realUpload" in request
    assert "export function realDownload" in request
    assert ".catch(reject)" in request


def test_student_portal_request_keeps_internship_context_and_single_flight_refresh():
    request = _read("student-portal/src/services/request.js")
    assert "X-Internship-Batch-Id" in request
    assert "student_portal_internship_batch_v1" in request
    assert "async function refreshOnce" in request
    assert "return uploadFile(path, file, { auth, _retried: true })" in request
    assert "return downloadFile(path, fallbackName, true)" in request


def test_temporary_integration_workflow_is_removed():
    assert not (ROOT / ".github/workflows/student-affairs-integration.yml").exists()
