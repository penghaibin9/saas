from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "app/services/approval_attachment_preview_service.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "app/api/v1/approval.py").read_text(encoding="utf-8")


def test_approval_attachment_reader_is_task_and_source_business_scoped():
    for marker in [
        "runtime.get_task(task_id, user=user)",
        "WorkflowTask.tenant_id == _tid()",
        "WorkflowInstance.tenant_id == _tid()",
        "FileBinding.tenant_id == _tid()",
        "FileBinding.biz_type == source_biz_type",
        "FileBinding.biz_id == source_biz_id",
        "FileBinding.is_current.is_(True)",
        'FileBinding.status == "ACTIVE"',
        "FileObject.tenant_id == _tid()",
        "get_backend().fetch_local(file_obj.file_key)",
    ]:
        assert marker in ACCESS, marker


def test_approval_attachment_preview_and_download_are_distinct_ticket_actions():
    for marker in [
        'if value not in {"preview", "download"}',
        'PREVIEW_TTL_SECONDS = 180',
        'DOWNLOAD_TTL_SECONDS = 60',
        '"singleUse": normalized == "download"',
        '"taskId": str(task_id)',
        '"fileId": int(file_id)',
        '"actor": _actor(user)',
        'str(payload.get("taskId") or "") != str(task_id)',
        'str(payload.get("actor") or "") != _actor(user)',
        'if normalized == "download":',
        'cache_set_json_if_absent(',
        'TICKET_STORE_UNAVAILABLE',
    ]:
        assert marker in ACCESS, marker


def test_approval_attachment_router_uses_audited_inline_reader_and_single_use_download():
    for marker in [
        '@router.get("/tasks/{task_id}/attachments"',
        '@router.post("/tasks/{task_id}/files/{file_id}/ticket"',
        '@router.get("/tasks/{task_id}/files/{file_id}/preview"',
        '@router.get("/tasks/{task_id}/files/{file_id}/download"',
        'attachmentsvc.consume_ticket(task_id, file_id, "preview", ticket, user)',
        'attachmentsvc.consume_ticket(task_id, file_id, "download", ticket, user)',
        'audit_action="APPROVAL_ATTACHMENT_PREVIEW"',
        'audit_action="APPROVAL_ATTACHMENT_DOWNLOAD"',
        'inline=True',
    ]:
        assert marker in ROUTER, marker


def test_approval_attachment_service_never_emits_generic_or_public_storage_urls():
    assert "/api/v1/files/" not in ACCESS
    assert "presigned" not in ACCESS.lower()
    assert '"url": f"/api/v1/approvals/tasks/' in ACCESS
