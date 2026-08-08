"""A3 / P0-05：就业中心正式路由真实化静态合同。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_formal_employment_facade_has_no_mock_or_fallback_reachability():
    src = _read("frontend/src/modules/employment/api/employment.api.js")
    forbidden = (
        "@/mocks/employment",
        "shouldTryReal",
        "db.employmentStudents",
        "db.materialReviews",
        "db.followUpRecords",
        "db.auditLogs",
    )
    for token in forbidden:
        assert token not in src, f"正式就业 facade 禁止回流：{token}"
    assert "request('/employment/dashboard')" in src
    assert "request('/employment/options')" in src
    assert "request('/export/domain/employment'" in src


def test_unimplemented_employment_actions_fail_closed_and_are_not_advertised():
    src = _read("frontend/src/modules/employment/api/employment.api.js")
    assert "批量提醒尚未接入正式消息发送链" in src
    assert "材料批量审核尚无正式批量事务合同" in src
    assert "就业导入尚未接入正式文件任务链" in src
    assert "employment.record.batchRemind': unsupportedAction" in src
    assert "materialList: []" in src


def test_employment_router_uses_scoped_runtime_for_formal_pages():
    src = _read("backend/app/modules/employment/routers/employment.py")
    assert "employment_runtime_service as svc" in src
    assert '@router.get("/options"' in src
    assert '@router.get("/materials/{mid}"' in src
    assert "svc.get_material_detail(mid, user=user)" in src
    assert "svc.get_dashboard(user=user)" in src
    assert "svc.list_students(" in src and "user=user" in src
    assert "idempotency_guard" in src and "require_store=True" in src


def test_employment_runtime_is_fail_closed_and_scopes_before_pagination():
    src = _read("backend/app/modules/employment/services/employment_runtime_service.py")
    assert "build_affairs_context" in src
    assert 'ctx.scope_type in {"NONE", "SELF", "DORM_BUILDING"}' in src
    assert "EmpStudent.id == -1" in src
    assert "count_stmt" in src
    assert ".offset((max(1, page) - 1) * ps).limit(ps)" in src
    assert "_assert_material" in src and "_assert_followup" in src


def test_employment_bound_rows_use_current_master_facts_for_scope_and_class_filter():
    src = _read("backend/app/modules/employment/services/employment_runtime_service.py")
    assert "EmpStudent.student_id.is_not(None)" in src
    assert "EmpStudent.student_id.is_(None)" in src
    assert "def _class_filter_condition" in src
    assert "StudentProfile.class_id == cid" in src
    assert "cond.append(_class_filter_condition(class_id))" in src


def test_employment_student_detail_is_read_in_same_scoped_session():
    src = _read("backend/app/modules/employment/services/employment_runtime_service.py")
    block = src[src.index("def get_student_detail"):src.index("def create_student")]
    assert "student = _assert_emp_id(db, sid, user)" in block
    assert "return base.get_student_detail" not in block
    assert "EmpMaterial.is_deleted.is_(False)" in block
    assert "EmpFollowup.is_deleted.is_(False)" in block
    assert 'EmpAuditTrail.biz_type == "RECORD"' in block


def test_employment_scoped_writes_are_atomic_not_check_then_second_transaction():
    src = _read("backend/app/modules/employment/services/employment_runtime_service.py")
    # 创建复用同一 session；其余正式写直接在 runtime 的 scope-checked session 内落库。
    assert "base.create_student(body, db=db)" in src
    for delegated in (
        "return base.update_student(",
        "return base.void_student(",
        "return base.batch_mark_destination(",
        "return base.approve_material(",
        "return base.return_material(",
        "return base.mark_employed(",
        "return base.mark_key_help(",
        "return base.assign_teacher(",
        "return base.create_followup(",
        "return base.void_followup(",
    ):
        assert delegated not in src
    assert "rows = _assert_emp_ids(db, ids, user)" in src
    assert "material, emp = _assert_material(db, mid, user)" in src
    assert "followup, _ = _assert_followup(db, fid, user)" in src


def test_employment_export_reuses_scoped_runtime():
    src = _read("backend/app/services/domain_export_service.py")
    assert 'if domain == "employment":' in src
    assert "employment_runtime_service.list_students(" in src
    assert "user=user" in src


def test_employment_routes_use_backend_permission_codes():
    src = _read("frontend/src/modules/employment/employment.routes.js")
    expected = (
        "employment.dashboard.view",
        "employment.student.view",
        "employment.material.view",
        "employment.unemployed.view",
        "employment.followup.view",
    )
    for code in expected:
        assert code in src
    assert "employment.record.view" not in src
    assert "employment.material.review" not in src
    assert "employment.followup.create" not in src


def test_employment_export_requires_real_purpose():
    dialog = _read("frontend/src/modules/employment/components/ExportDialog.vue")
    facade = _read("frontend/src/modules/employment/api/employment.api.js")
    assert "options.purposeRequired" in dialog
    assert "this.purpose.trim().length < 5" in dialog
    assert "purpose: this.purpose.trim()" in dialog
    assert "purpose.length < 5" in facade
    assert "当前账号数据范围内全部" in facade
