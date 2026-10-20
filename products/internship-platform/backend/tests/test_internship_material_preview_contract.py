from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "app/modules/internship/services/internship_material_preview_access.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "app/modules/internship/routers/internship_material_center.py").read_text(encoding="utf-8")


def test_internship_material_ticket_resolver_is_current_tenant_scoped_and_business_scoped():
    for marker in [
        'FileBinding.tenant_id == _tid()',
        'FileBinding.module_code == material_center.MODULE_CODE',
        'FileBinding.relation_type == "MATERIAL"',
        'FileBinding.is_current.is_(True)',
        'FileBinding.status == "ACTIVE"',
        'material_center._assert_scope(db, int(internship_id), user, f"material.{normalized}")',
        'FileVersion.tenant_id == _tid()',
        'FileVersion.is_current.is_(True)',
        'version.status not in material_center.READY_VERSION_STATUS',
        'require_file_access(str(target_file_id), user=user, action=normalized)',
        'FileObject.tenant_id == _tid()',
        'material_center._file_ready(file_obj)',
        'get_backend().fetch_local(file_obj.file_key)',
    ]:
        assert marker in ACCESS, marker


def test_internship_material_preview_and_download_permissions_never_collapse():
    assert 'if value not in {"preview", "download"}' in ACCESS
    assert '"action": normalized' in ACCESS
    assert 'payload.get("action")' in ACCESS
    assert 'PREVIEW_TTL_SECONDS = 180' in ACCESS
    assert 'DOWNLOAD_TTL_SECONDS = 60' in ACCESS
    assert '"singleUse": normalized == "download"' in ACCESS
    assert 'if normalized == "download":' in ACCESS
    assert 'cache_set_json_if_absent(' in ACCESS
    assert 'TICKET_STORE_UNAVAILABLE' in ACCESS


def test_internship_ticket_is_bound_to_tenant_actor_file_and_action():
    for marker in [
        '"typ": TICKET_TYPE',
        '"tenantId": int(_tid())',
        '"fileId": int(file_id)',
        '"actor": _actor(user)',
        'payload.get("typ") != TICKET_TYPE',
        'int(payload.get("tenantId") or 0) != int(_tid())',
        'int(payload.get("fileId") or 0) != int(file_id)',
        'str(payload.get("actor") or "") != _actor(user)',
    ]:
        assert marker in ACCESS, marker


def test_internship_router_exposes_audited_inline_preview_and_separate_download():
    for marker in [
        '@router.post("/material-center/files/{file_id}/ticket"',
        '@router.get("/material-center/files/{file_id}/preview"',
        '@router.get("/material-center/files/{file_id}/download"',
        'material_tickets.issue_ticket(file_id, action, user)',
        'material_tickets.consume_ticket(file_id, "preview", ticket, user)',
        'material_tickets.consume_ticket(file_id, "download", ticket, user)',
        'audit_action="INTERNSHIP_VERSIONED_MATERIAL_PREVIEW"',
        'audit_action="INTERNSHIP_VERSIONED_MATERIAL_DOWNLOAD"',
        'inline=True',
        '"businessTicket": True',
    ]:
        assert marker in ROUTER, marker
