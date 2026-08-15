"""Graduation real-MySQL tests replay the canonical SCHOOL_ADMIN Authority baseline.

Production stays fail-closed: this plugin only prepares a fresh pytest database after
``db_mode`` has cleared it.  The permission set comes from the same B8 production
resolver contract; no wildcard, static bypass, or application fallback is introduced.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest


def _is_graduation_test(request) -> bool:
    name = str(getattr(getattr(request, "node", None), "fspath", "") or "").replace("\\", "/")
    return name.rsplit("/", 1)[-1].startswith("test_graduation")


def _seed_school_admin_authority() -> None:
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models.permission_governance import (
        EFFECT_ALLOW,
        TEMPLATE_CATEGORY_SYSTEM_ROLE,
        TEMPLATE_PLANE_TENANT,
        TEMPLATE_PUBLISHED,
        RoleTemplate,
        RoleTemplatePermission,
    )
    from app.services.system_role_shadow_service import expected_system_role_permissions

    codes = tuple(expected_system_role_permissions("SCHOOL_ADMIN"))
    if not codes:
        raise RuntimeError("pytest SCHOOL_ADMIN Authority baseline resolved to an empty permission set")
    digest = hashlib.sha256(
        json.dumps(sorted(codes), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    source_sha = str(os.environ.get("GITHUB_SHA") or "pytest-school-admin-baseline")

    db = get_sessionmaker()()
    try:
        existing = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == "SCHOOL_ADMIN",
            RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
            RoleTemplate.template_category == TEMPLATE_CATEGORY_SYSTEM_ROLE,
            RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
            RoleTemplate.status == "ACTIVE",
            RoleTemplate.is_deleted.is_(False),
        ).limit(1)).first()
        if existing is not None:
            actual = set(db.scalars(select(RoleTemplatePermission.permission_code).where(
                RoleTemplatePermission.tenant_id == 0,
                RoleTemplatePermission.role_template_id == int(existing.id),
                RoleTemplatePermission.effect == EFFECT_ALLOW,
                RoleTemplatePermission.is_deleted.is_(False),
            )).all())
            if actual != set(codes):
                raise RuntimeError("pytest SCHOOL_ADMIN Authority baseline drifted from production B8 truth")
            return

        template = RoleTemplate(
            tenant_id=0,
            template_code="SCHOOL_ADMIN",
            template_name="SCHOOL_ADMIN",
            template_version=1,
            template_plane=TEMPLATE_PLANE_TENANT,
            template_category=TEMPLATE_CATEGORY_SYSTEM_ROLE,
            publish_status=TEMPLATE_PUBLISHED,
            permission_digest=digest,
            change_reason="pytest fresh-DB canonical SCHOOL_ADMIN Authority baseline",
            source_commit_sha=source_sha,
            delivered=True,
            bundle_codes_json={"items": []},
            permission_ceiling_json={"items": list(codes), "permissionDigest": digest},
            status="ACTIVE",
        )
        db.add(template)
        db.flush()
        db.add_all([
            RoleTemplatePermission(
                tenant_id=0,
                role_template_id=int(template.id),
                permission_code=code,
                effect=EFFECT_ALLOW,
            )
            for code in codes
        ])
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _graduation_school_admin_authority_baseline(request):
    if (
        not _is_graduation_test(request)
        or "db_mode" not in request.fixturenames
        or "auth_headers" not in request.fixturenames
    ):
        yield
        return

    # Force fresh-schema/data cleanup first, then replay only the Authority truth
    # required by the authenticated Graduation request in this individual test.
    request.getfixturevalue("db_mode")
    _seed_school_admin_authority()
    yield
