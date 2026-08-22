from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_peer_preview_route_is_inline_audited_and_task_bound():
    source = _read("backend/app/api/v1/mobile_graduation_material_center.py")
    assert '@router.get("/peer/{peer_id}/files/{file_id}/preview"' in source
    assert "peer_files.resolve_peer_preview(peer_id, file_id, user)" in source
    assert "validated_local_file_response(" in source
    assert 'audit_action="STUDENT_GRADUATION_PEER_MATERIAL_PREVIEW"' in source
    assert 'audit_target=f"graduation-peer:{peer_id}:file:{file_id}"' in source
    assert "inline=True" in source
    assert '"taskBound": True' in source


def test_peer_preview_resolver_never_authorizes_by_bare_file_id_or_bypasses_scan_gate():
    source = _read("backend/app/modules/graduation/services/graduation_peer_consistency.py")
    for marker in (
        "def resolve_peer_preview(peer_id, file_id, user):",
        "resolve_current_gd_student(db, user)",
        "peer.gd_student_id",
        "peer.reviewer_gd_student_id",
        "final = _bound_final(db, peer)",
        "target_file_id not in _attachment_ids(final)",
        'FileObject.biz_type == "GRADUATION_MATERIAL"',
        "def _file_ready(file_row",
        "READY_SCAN_STATES",
        "SCAN_NOT_REQUIRED",
        "_file_ready(file_row)",
        "get_backend().fetch_local(file_key)",
    ):
        assert marker in source

    assert "return path, filename" in source
    resolver = source[source.index("def resolve_peer_preview"):source.index("@_conflict_guard")]
    assert "assert_student_access(db, student" not in resolver
    assert "is_downloadable_status(file_row.status)" not in resolver


def test_peer_projection_tenant_scopes_historical_references_and_attachment_list_scan_state():
    source = _read("backend/app/modules/graduation/services/graduation_peer_consistency.py")
    peer_row = source[source.index("def peer_row"):source.index("def resolve_peer_preview")]
    attachments = source[source.index("def _final_attachments"):source.index("def _bound_final")]

    assert "tenant_get(db, GraduationStudent, peer.gd_student_id)" in peer_row
    assert "tenant_get(db, GraduationStudent, peer.reviewer_gd_student_id)" in peer_row
    assert "tenant_get(db, GraduationFinal, peer.gd_final_id)" in peer_row
    assert "db.get(" not in peer_row
    assert "_file_ready(row)" in attachments
    assert '"scanStatus"' in attachments
    assert '"readyForBusiness": True' in attachments


def test_peer_projection_is_preview_only_and_never_promotes_peer_task_to_download_right():
    source = _read("backend/app/modules/graduation/services/graduation_peer_consistency.py")
    attachments = source[source.index("def _final_attachments"):source.index("def _bound_final")]

    assert '"allowedActions": ["viewMetadata", "preview"]' in attachments
    assert '"canPreview": True' in attachments
    assert '"canDownload": False' in attachments
    assert "downloadUrl" not in attachments
