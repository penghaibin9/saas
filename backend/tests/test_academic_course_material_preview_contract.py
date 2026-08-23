from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "app/modules/academic_affairs/services/academic_affairs_course_material_preview_access.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "app/modules/academic_affairs/routers/course_material_preview_router.py").read_text(encoding="utf-8")
BUNDLE = (ROOT / "app/modules/academic_affairs/routers/academic_affairs_bundle.py").read_text(encoding="utf-8")


def test_course_material_reader_uses_course_and_material_business_scope():
    for marker in [
        "course_svc.get_course(int(course_id), user)",
        "AaCourseMaterial.course_id == int(course_id)",
        "AaCourseMaterial.tenant_id == _tid()",
        'AaCourseMaterial.status == "ACTIVE"',
        "AaCourseMaterial.is_deleted.is_(False)",
        "FileObject.id == int(file_id)",
        "FileObject.tenant_id == _tid()",
        "FileObject.is_deleted.is_(False)",
        "get_backend().fetch_local(file_obj.file_key)",
    ]:
        assert marker in ACCESS, marker


def test_course_material_ticket_is_bound_to_tenant_course_material_file_actor_and_action():
    for marker in [
        'PREVIEW_TTL_SECONDS = 180',
        'DOWNLOAD_TTL_SECONDS = 60',
        '"tenantId": int(_tid())',
        '"courseId": int(course_id)',
        '"materialId": int(material_id)',
        '"fileId": int(file_obj.id)',
        '"actor": _actor(user)',
        '"action": normalized',
        '"singleUse": normalized == "download"',
        'if normalized == "download":',
        'cache_set_json_if_absent(',
        'TICKET_STORE_UNAVAILABLE',
    ]:
        assert marker in ACCESS, marker


def test_course_material_router_exposes_audited_inline_preview_and_separate_download():
    for marker in [
        '@router.get("/courses/{courseId}/materials/reader"',
        '@router.post("/courses/{courseId}/materials/{materialId}/ticket"',
        '@router.get("/courses/{courseId}/materials/{materialId}/preview"',
        '@router.get("/courses/{courseId}/materials/{materialId}/download"',
        'preview_svc.consume_ticket(courseId, materialId, "preview", ticket, user)',
        'preview_svc.consume_ticket(courseId, materialId, "download", ticket, user)',
        'audit_action="ACADEMIC_COURSE_MATERIAL_PREVIEW"',
        'audit_action="ACADEMIC_COURSE_MATERIAL_DOWNLOAD"',
        'inline=True',
    ]:
        assert marker in ROUTER, marker
    assert '"course_material_preview_router"' in BUNDLE


def test_course_reader_never_exposes_generic_file_urls():
    assert "/api/v1/files/" not in ACCESS
    assert "presigned" not in ACCESS.lower()
    assert '"businessTicket": True' in ACCESS
