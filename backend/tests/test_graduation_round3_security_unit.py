from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from app.core.context import set_current_user
from app.core.exceptions import AppException
from app.core.graduation_permissions import graduation_permission_for_endpoint
from app.core.permissions import has_permission
from app.api.v1.router import api_router
from app.modules.graduation.services import graduation_identity
from app.services import excel, xlsx_util


def _admin_context():
    return {
        "tenantId": "1001",
        "userId": "2001",
        "loginName": "admin",
        "realName": "管理员",
        "currentRoleCode": "GRADUATION_ADMIN",
        "userType": "TEACHER",
        "dataScope": "ALL",
    }


def test_every_graduation_endpoint_has_an_explicit_permission():
    def walk_routes(routes, prefix=""):
        for route in routes:
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                include_context = getattr(route, "include_context", None)
                include_prefix = getattr(include_context, "prefix", "") if include_context else ""
                yield from walk_routes(original_router.routes, f"{prefix}{include_prefix}")
                continue
            yield f"{prefix}{getattr(route, 'path', '')}", route

    missing = []
    endpoints = 0
    for path, route in walk_routes(api_router.routes):
        if path.startswith("/graduation") or path.startswith("/gd-"):
            endpoints += 1
            if not graduation_permission_for_endpoint(getattr(route, "endpoint", None)):
                missing.append((path, getattr(route.endpoint, "__name__", "")))
    assert endpoints >= 200
    assert missing == []


def test_real_role_separation_matrix():
    reviewer = {"currentRoleCode": "GD_REVIEWER", "userType": "TEACHER"}
    expert = {"currentRoleCode": "GD_DEFENSE_EXPERT", "userType": "TEACHER"}
    secretary = {"currentRoleCode": "GD_DEFENSE_SECRETARY", "userType": "TEACHER"}
    grade_admin = {"currentRoleCode": "GD_GRADE_ADMIN", "userType": "TEACHER"}

    assert has_permission(reviewer, "graduationDesign.review.submit")
    assert not has_permission(reviewer, "graduationDesign.grade.calculate")
    assert has_permission(expert, "graduationDesign.defense.score")
    assert not has_permission(expert, "graduationDesign.defense.scoreConfirm")
    assert has_permission(secretary, "graduationDesign.defense.scoreConfirm")
    assert not has_permission(secretary, "graduationDesign.defense.score")
    assert has_permission(grade_admin, "graduationDesign.grade.publish")
    assert not has_permission(grade_admin, "graduationDesign.review.submit")


def test_same_name_never_covers_a_defense_seat():
    row = SimpleNamespace(
        status="SCORED", judge_mentor_id=101, expert_id=None, judge_name="张伟",
    )
    assert graduation_identity.score_row_covers_seat(
        row, {"mentorId": 101, "expertId": None, "name": "张伟"},
    )
    assert not graduation_identity.score_row_covers_seat(
        row, {"mentorId": 202, "expertId": None, "name": "张伟"},
    )
    assert not graduation_identity.score_row_covers_seat(
        SimpleNamespace(status="SCORED", judge_mentor_id=None, expert_id=None, judge_name="张伟"),
        {"mentorId": None, "expertId": None, "name": "张伟"},
    )


def test_graduation_import_preview_token_binds_actor_and_rows():
    set_current_user(_admin_context())
    spec = excel.ImportSpec(
        module_key="graduationDesign",
        biz_type="round3-test",
        template_name="test",
        columns=[excel.ColumnSpec("studentNo", "学号", required=True)],
        permission_key="graduationDesign.student.import",
        persist_rows=lambda rows: {"created": len(rows)},
    )
    rows = [{"studentNo": "S001"}]
    preview = excel.pre_validate(spec, rows)
    assert preview["passed"] is True
    assert preview["previewToken"]
    assert excel.confirm_import(spec, rows, preview["previewToken"])["created"] == 1
    with pytest.raises(AppException):
        excel.confirm_import(spec, [{"studentNo": "S002"}], preview["previewToken"])


def test_xlsx_safety_rejects_external_links_and_accepts_plain_xlsx():
    wb = Workbook()
    wb.active.append(["学号"])
    wb.active.append(["S001"])
    buffer = io.BytesIO()
    wb.save(buffer)
    plain = buffer.getvalue()
    xlsx_util.validate_xlsx_package(plain)

    source = zipfile.ZipFile(io.BytesIO(plain))
    unsafe_buffer = io.BytesIO()
    with source, zipfile.ZipFile(unsafe_buffer, "w") as target:
        for member in source.infolist():
            target.writestr(member, source.read(member.filename))
        target.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
    with pytest.raises(AppException):
        xlsx_util.validate_xlsx_package(unsafe_buffer.getvalue())
