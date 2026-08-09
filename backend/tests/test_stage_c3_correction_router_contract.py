"""Stage C3 operator-accessible post-archive correction contracts."""
from __future__ import annotations


def test_post_archive_correction_routes_are_registered_on_public_bundle():
    from app.modules.academic_affairs.routers.academic_affairs_bundle import build_router

    # FastAPI 0.141 keeps app.include_router(...) as a lazy _IncludedRouter. The
    # academic-affairs bundle is the formal unit consumed by route_registration, so
    # assert its concrete route table rather than an internal application expansion.
    bundle = build_router()
    paths = {route.path for route in bundle.routes if getattr(route, "path", None)}
    assert "/academic-affairs/archive/batches/{batch_id}/manifest/verify" in paths
    assert "/academic-affairs/archive/batches/{batch_id}/corrections" in paths
    assert "/academic-affairs/archive/corrections/{case_id}" in paths
    assert "/academic-affairs/archive/corrections/{case_id}/approve" in paths


def test_post_archive_correction_public_service_is_stage_c3_immutable_service():
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as immutable
    from app.modules.academic_affairs.services import academic_affairs_archive_service as public

    assert public.list_correction_cases is immutable.list_correction_cases
    assert public.get_correction_case is immutable.get_correction_case
    assert public.create_correction_case is immutable.create_correction_case
    assert public.approve_correction_case is immutable.approve_correction_case
    assert public.verify_manifest is immutable.verify_manifest
