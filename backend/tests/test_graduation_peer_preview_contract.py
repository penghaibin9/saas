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


def test_peer_preview_resolver_never_authorizes_by_bare_file_id():
    source = _read("backend/app/modules/graduation/services/graduation_peer_consistency.py")
    for marker in (
        "def resolve_peer_preview(peer_id, file_id, user):",
        "resolve_current_gd_student(db, user)",
        "peer.gd_student_id",
        "peer.reviewer_gd_student_id",
        "final = _bound_final(db, peer)",
        "target_file_id not in _attachment_ids(final)",
        'FileObject.biz_type == "GRADUATION_MATERIAL"',
        "is_downloadable_status(file_row.status)",
        "get_backend().fetch_local(file_key)",
    ):
        assert marker in source

    assert "return path, filename" in source
    assert "assert_student_access(db, student" not in source[source.index("def resolve_peer_preview"):source.index("@_conflict_guard")]
