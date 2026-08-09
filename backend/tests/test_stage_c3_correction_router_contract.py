"""Stage C3 operator-accessible post-archive correction contracts."""
from __future__ import annotations


def test_post_archive_correction_routes_are_registered_on_public_bundle():
    from fastapi import FastAPI

    from app.modules.academic_affairs.routers.academic_affairs_bundle import build_router

    app = FastAPI()
    app.include_router(build_router())
    paths = {route.path for route in app.routes if getattr(route, "path", None)}
    assert "/academic-affairs/archive/batches/{batch_id}/manifest/verify" in paths
    assert "/academic-affairs/archive/batches/{batch_id}/corrections" in paths
    assert "/academic-affairs/archive/corrections/{case_id}/approve" in paths


def test_post_archive_correction_public_service_is_stage_c3_immutable_service():
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as immutable
    from app.modules.academic_affairs.services import academic_affairs_archive_service as public

    assert public.create_correction_case is immutable.create_correction_case
    assert public.approve_correction_case is immutable.approve_correction_case
    assert public.verify_manifest is immutable.verify_manifest
