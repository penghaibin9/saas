"""Source-level regression contracts for the 2026-08-19 prelaunch hardening pass.

These tests deliberately target wiring/security/query shape. Existing domain tests continue to own
business-state correctness; this file prevents a later refactor from silently reconnecting the old
unsafe/whole-batch paths.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from starlette.responses import Response

from app.modules.graduation.routers import graduation_grade
from app.modules.internship.dependencies import enterprise_context
from app.modules.internship.routers import internship_enterprise_browser_auth as enterprise_browser
from app.modules.internship.routers import internship_match
from app.modules.internship.services import internship_intention_read_service as intention_read
from app.modules.internship.services import internship_major_match_run_service as major_match
from app.modules.internship.services import internship_scope

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_enterprise_browser_refresh_is_http_only_per_tab_and_claim_bound():
    source = inspect.getsource(enterprise_browser)
    assert 'httponly=True' in source
    assert 'samesite="strict"' in source
    assert 'secure=bool(settings.is_prod)' in source
    assert '_COOKIE_PATH = "/api/v1/internship/enterprise-portal/auth"' in source
    assert 'browserChannel' in source
    assert 'browserSessionIdHash' in source
    assert 'consume_refresh_if_matches(' in source
    assert 'auth_svc.validate_enterprise_claims(claims)' in source
    assert 'data.pop("refreshToken"' in source
    assert 'issue_refresh(dict(claims))' in source
    assert enterprise_browser._cookie_name("tab-a") != enterprise_browser._cookie_name("tab-b")

    response = Response()
    enterprise_browser._set_refresh_cookie(response, "secret-refresh", "tab-a")
    header = response.headers.get("set-cookie", "").lower()
    assert "httponly" in header
    assert "samesite=strict" in header
    assert "path=/api/v1/internship/enterprise-portal/auth" in header
    assert "secret-refresh" in header


def test_enterprise_browser_logout_revokes_entire_auth_session_family():
    browser_source = inspect.getsource(enterprise_browser)
    principal_source = inspect.getsource(enterprise_context.get_enterprise_principal)
    assert "auth_session_blocked(auth_session_id)" in browser_source
    assert "block_auth_session(auth_session_id)" in browser_source
    assert "access_claims" in browser_source and "refresh_claims" in browser_source
    assert "auth_session_blocked(auth_session_id)" in principal_source
    assert "企业浏览器会话已登出失效" in principal_source
    assert '"authSessionId": auth_session_id or None' in inspect.getsource(enterprise_context)


def test_internship_intention_public_list_uses_sql_scope_count_and_page_only():
    router_source = inspect.getsource(internship_match.intentions)
    service_source = inspect.getsource(intention_read.list_intentions)
    assert "intention_read_svc.list_intentions" in router_source
    assert "apply_internship_record_scope(base, user)" in service_source
    assert "select(func.count())" in service_source
    assert ".offset((page_no - 1) * size)" in service_source
    assert ".limit(size)" in service_source
    assert "db.scalars(q.order_by" not in service_source


def test_internship_sql_scope_preserves_legacy_college_fallback():
    source = inspect.getsource(internship_scope.apply_internship_record_scope)
    assert "func.coalesce(" in source
    assert "direct_college.college_name" in source
    assert "major_college.college_name" in source
    assert "class_college.college_name" in source
    assert "StudentProfile.tenant_id == _tid()" in source


def test_major_match_bulk_loads_and_indexes_eligibility_before_mutation():
    router_source = inspect.getsource(internship_match.run_major)
    source = inspect.getsource(major_match.run_major_match)
    assert "major_match_run_svc.run_major_match" in router_source
    assert "student_ids =" in source
    assert "major_ids =" in source
    assert "eligible_by_major" in source
    assert "ranked_by_preference" in source
    assert "legacy._upsert_match(" in source
    assert "scored.sort(key=lambda item: -item[0])" in source
    assert "db.commit()" in source


def test_graduation_public_grade_list_is_wired_to_existing_sql_reader():
    source = inspect.getsource(graduation_grade.gd_grades)
    assert "items, total = grade_read_svc.list_grades(" in source
    assert "items, total = svc.list_grades(" not in source


def test_systemd_release_builds_serves_and_verifies_enterprise_portal():
    install = _text("scripts/deploy/install-systemd-release.sh")
    verify = _text("scripts/deploy/verify-systemd-release.sh")
    nginx = _text("deploy/nginx/school-lifecycle.systemd.conf.example")
    for required in (
        'cd "$RELEASE_DIR/enterprise-portal"',
        'VITE_BASE=/enterprise/',
        '$SOURCE_ROOT/enterprise-portal/dist/index.html',
        '/var/www/school-lifecycle/enterprise',
        '$APP_ROOT/current/enterprise-portal/dist',
    ):
        assert required in install
    assert '/enterprise/' in nginx
    assert '/var/www/school-lifecycle' in nginx
    assert 'enterprise-portal/dist/index.html:企业协同 PC' in verify
    assert '/var/www/school-lifecycle/enterprise' in verify
    assert 'for path in / /portal/ /miniapp/ /enterprise/;' in verify


def test_unknown_500_logs_stack_without_request_secrets():
    source = _text("backend/app/core/exceptions.py")
    assert 'logging.getLogger("app.error")' in source
    assert 'exc_info=(type(exc), exc, exc.__traceback__)' in source
    assert 'request.method' in source and 'request.url.path' in source
    handler = source.split('@app.exception_handler(Exception)', 1)[1]
    assert 'request.body' not in handler
    assert 'request.headers' not in handler
    assert 'request.cookies' not in handler


def test_production_construction_placeholder_is_closed_and_dev_only():
    source = _text("frontend/src/views/admin/planned/PlannedPlaceholderView.vue")
    assert 'import.meta.env.PROD' in source
    assert "this.$router.replace('/workbench')" in source
    assert 'canSeeConstruction' in source
    assert 'import.meta.env.DEV' in source
    assert 'v-if="canSeeConstruction && info"' in source
