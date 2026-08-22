from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "app/services/affairs_material_preview_access.py").read_text(encoding="utf-8")
RESOLVERS = (ROOT / "app/services/file_access_resolvers.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "app/modules/student_affairs/routers/affairs_material_center.py").read_text(encoding="utf-8")


def test_affairs_material_ticket_is_file_version_tenant_actor_and_action_bound():
    for marker in [
        '"tenantId": int(_tid())',
        '"fileId": int(file_obj.id)',
        '"fileVersionId": int(version.id)',
        '"action": normalized',
        '"actor": _actor(user)',
        'int(payload.get("tenantId") or 0) != int(_tid())',
        'int(payload.get("fileId") or 0) != int(file_id)',
        'version_id = int(payload.get("fileVersionId") or 0)',
        'str(payload.get("actor") or "") != _actor(user)',
    ]:
        assert marker in ACCESS, marker


def test_affairs_material_resolver_keeps_single_shared_resolver_and_preview_rechecks_business_scope():
    # MATERIAL_REQUIREMENT business authority is registered once in the shared File Center.
    # The versioned preview service must not register a competing resolver; instead it resolves
    # the exact requirement/binding and then calls require_file_access, which replays that shared
    # resolver before any bytes are served.
    for marker in [
        '@register_file_resolver("MATERIAL_REQUIREMENT")',
        'def material_requirement_resolver',
        'center._has_biz_permission(user or {}, requirement.biz_type)',
        'center._psy_scope_allows(db, requirement.student_id, user or {})',
        'center._require_student_scope(db, requirement.student_id, user or {}, hide=True)',
    ]:
        assert marker in RESOLVERS, marker
    assert '@register_file_resolver("MATERIAL_REQUIREMENT")' not in ACCESS

    for marker in [
        'FileBinding.module_code == center.MODULE_CODE',
        'FileBinding.relation_type == "MATERIAL_SUBMISSION"',
        'FileBinding.status.in_(BINDING_STATUS)',
        '_student_self(db, requirement, user)',
        'center._staff_can_enumerate(db, requirement, user)',
        'require_file_access(str(target_file_id), user=user, action=normalized)',
    ]:
        assert marker in ACCESS, marker


def test_affairs_historical_reader_requires_exact_binding_and_exact_file_version():
    for marker in [
        'FileBinding.file_id == target_file_id',
        'FileBinding.version_id == target_version_id',
        'FileBinding.module_code == center.MODULE_CODE',
        'FileBinding.relation_type == "MATERIAL_SUBMISSION"',
        'FileBinding.status.in_(BINDING_STATUS)',
        'FileVersion.id == target_version_id',
        'FileVersion.asset_id == binding.asset_id',
        'FileVersion.file_object_id == target_file_id',
        'str(version.status or "").upper() not in HISTORICAL_VERSION_STATUS',
        'require_file_access(str(target_file_id), user=user, action=normalized)',
        'center._file_ready(file_obj)',
    ]:
        assert marker in ACCESS, marker


def test_affairs_preview_and_download_permissions_remain_separate():
    assert 'PREVIEW_TTL_SECONDS = 180' in ACCESS
    assert 'DOWNLOAD_TTL_SECONDS = 60' in ACCESS
    assert '"singleUse": normalized == "download"' in ACCESS
    assert 'if normalized == "download":' in ACCESS
    assert 'cache_set_json_if_absent(' in ACCESS
    assert 'TICKET_STORE_UNAVAILABLE' in ACCESS


def test_affairs_router_exposes_audited_versioned_preview_and_download():
    for marker in [
        '@router.post("/student-affairs/material-center/files/{file_id}/ticket"',
        '@router.get("/student-affairs/material-center/files/{file_id}/preview"',
        '@router.get("/student-affairs/material-center/files/{file_id}/download"',
        'material_tickets.issue_ticket(file_id, int(raw_version_id), action, user)',
        'material_tickets.consume_ticket(file_id, "preview", ticket, user)',
        'material_tickets.consume_ticket(file_id, "download", ticket, user)',
        'audit_action="STUDENT_AFFAIRS_VERSIONED_MATERIAL_PREVIEW"',
        'audit_action="STUDENT_AFFAIRS_VERSIONED_MATERIAL_DOWNLOAD"',
        '"fileVersionId": str(version_id)',
        'inline=True',
    ]:
        assert marker in ROUTER, marker
