from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.v1.teacher_mobile_employment import (
    MaterialEvidenceBody,
    RecommendationBody,
    VerificationReviewBody,
    router as employment_router,
)
from app.core.exceptions import AppException
from app.services import teacher_mobile_employment_service as employment_service

ROOT = Path(__file__).resolve().parents[2]


def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class _ScalarDb:
    def __init__(self, *values):
        self.values = list(values)

    def scalar(self, _stmt):
        if not self.values:
            raise AssertionError("unexpected scalar lookup")
        return self.values.pop(0)


def test_t7_router_is_single_object_strict_and_resolves_expected_paths():
    app = FastAPI()
    app.include_router(employment_router, prefix="/teacher-mobile")
    paths = set(app.openapi()["paths"])
    assert "/teacher-mobile/employment/overview" in paths
    assert "/teacher-mobile/employment/students/{student_id}/recommendations" in paths
    assert "/teacher-mobile/employment/students/{student_id}/verification" in paths
    assert "/teacher-mobile/employment/materials/{material_id}/evidence" in paths
    assert "/teacher-mobile/employment/verifications/{verification_id}/review" in paths
    assert not any("/bulk" in path or "/batch" in path for path in paths)

    recommendation = RecommendationBody(jobId=7, reason="专业匹配且通勤可接受", expectedStudentVersion=3)
    assert recommendation.jobId == 7
    try:
        RecommendationBody(jobId=7, reason="太短", expectedStudentVersion=3, ids=[1, 2])
    except ValidationError:
        pass
    else:
        raise AssertionError("recommendation body must reject extras")

    assert MaterialEvidenceBody(fileId="123", expectedVersion=2).expectedVersion == 2
    try:
        VerificationReviewBody(action="RETURN", expectedVersion=2, ids=[1])
    except ValidationError:
        pass
    else:
        raise AssertionError("verification body must reject batch ids")


def test_t7_recommendation_is_first_class_fact_not_followup_alias():
    model = _src("backend/app/models/employment_recommendation.py")
    service = _src("backend/app/services/teacher_mobile_employment_service.py")
    assert 'class EmpRecommendation' in model
    assert '__tablename__ = "t_emp_recommendation"' in model
    assert 'job_id: Mapped[int]' in model
    assert 'teacher_user_id:' in model
    assert 'reason: Mapped[str]' in model
    assert 'recommendation = EmpRecommendation(' in service
    assert 'db.add(recommendation)' in service
    assert 'db.flush()' in service
    assert '"recommendationId": str(recommendation.id)' in service
    # Follow-up may exist only after the first-class recommendation has been created.
    assert service.index('db.add(recommendation)') < service.index('db.add(EmpFollowup(')
    assert 'way="RECOMMEND"' in service
    assert 'expectedStudentVersion' in _src("backend/app/api/v1/teacher_mobile_employment.py")


def test_t7_verification_requires_formal_file_binding_and_optimistic_lock():
    """核验的证据门槛与乐观锁仍然成立，但实现位置已上移。

    V3 施工手册 TP-E02：核验的业务规则（状态机 / 证据门槛 / 乐观锁 / 审计）
    原本只写在教师小程序服务里，导致教师 PC 走的是另一套更弱的门槛。现已收敛到
    共享 domain 命令 `employment_destination_verification_service`，两个端共用。
    因此这些不变量改为在共享权威上断言；小程序服务只保留「本端授权 + 委派」。
    """
    service = _src("backend/app/services/teacher_mobile_employment_service.py")
    authority = _src(
        "backend/app/modules/employment/services/employment_destination_verification_service.py")

    # 文件证据侧的绑定/ACL 仍归小程序服务自己实现
    assert '_FORMAL_BIZ_TYPE = "EMPLOYMENT_MATERIAL"' in service
    assert 'bind_file_to_business(' in service
    assert 'module_code=_FORMAL_MODULE' in service
    assert 'subject_type="STUDENT"' in service
    assert '@register_file_resolver(_FORMAL_BIZ_TYPE)' in service
    assert 'legacyFileNameOnly' in service

    # 授权仍必须由本端范围权威完成（不得让 PC 口径顶替移动端口径，反之亦然）
    assert '_scope_emp(db, verification_id, user, lock=True)' in service
    assert 'verification_authority.review(' in service

    # 核验业务规则在共享权威上仍然成立
    assert '至少需要 1 份已审核通过且具有正式 FileBinding' in authority
    assert 'count_formal_approved_materials(db, emp) <= 0' in authority
    assert 'def assert_expected_version(' in authority
    assert '缺少 expectedVersion' in authority
    assert 'emp.verify_status = after' in authority
    assert 'if action == RETURN and len(text) < _MIN_RETURN_COMMENT' in authority
    # 共享权威明确声明自己不做授权，避免以后有人拿它当授权层用
    assert '**本模块不做授权判定。**' in authority


def test_t7_pc_material_approval_closed_loop_now_requires_formal_evidence():
    """PC 材料审核的闭环保留，但证据门槛已与教师小程序拉齐（TP-E04 决断）。

    #183 保留了「PC 材料通过即完成去向核验」这条既有闭环。问题在于：小程序侧
    要求正式 FileBinding + 安全扫描才允许 VERIFIED，而 PC 侧只要点一下材料通过
    就行，哪怕那份材料只有历史 file_name 文本。同一 canonical 状态两条门槛，
    老师用哪个端操作决定证据强度——这是端间事实分叉。

    本轮决断：不拆闭环（真实上传过材料的正常流程完全不受影响），而是给 PC 这条
    路径加上同一道证据门槛。证据不足时材料照常 APPROVED（材料审核是独立的业务
    行为），但 verify_status 不再被隐式推进。
    """
    route = _src("backend/app/modules/employment/routers/employment.py")
    material_authority = _src("backend/app/modules/employment/services/employment_runtime_material_service.py")
    assert 'employment_runtime_material_service as material_runtime' in route
    assert 'material_runtime.approve_material(mid, body.comment, user=user)' in route

    approve_block = material_authority[material_authority.index('def approve_material'):]
    # 材料审核本身仍然完成
    assert 'emp.material_status = "APPROVED"' in approve_block
    # 闭环仍在，但被证据门槛守住
    assert 'formal = verification.material_is_formal_evidence(db, material)' in approve_block
    assert 'if formal and verify_before != "VERIFIED":' in approve_block
    assert 'emp.verify_status = "VERIFIED"' in approve_block
    # 结果如实回传，前端不得再统一宣称"已核验"
    assert '"destinationVerified": verified_now' in approve_block
    assert '"formalEvidence": formal' in approve_block

    # 教师小程序侧仍走同一共享 domain 命令，两端结论一致
    mini = _src("backend/app/services/teacher_mobile_employment_service.py")
    assert 'verification_authority.review(' in mini


def test_t7_bound_profile_scope_never_falls_back_to_stale_employment_snapshot(monkeypatch):
    emp = SimpleNamespace(
        student_id=42,
        student_no="20260001",
        class_name="历史班级",
        college_name="历史学院",
    )
    profile = SimpleNamespace(id=42)
    db = _ScalarDb(emp, profile)

    monkeypatch.setattr(employment_service, "_tid", lambda: 100)
    monkeypatch.setattr(
        employment_service.teacher_guard,
        "resolve_teacher_scope",
        lambda _user: {"mode": "CLASS", "classNames": {"历史班级"}},
    )
    monkeypatch.setattr(
        employment_service.teacher_guard,
        "can_teacher_view_student",
        lambda _user, _profile, *, scope, db: False,
    )

    def _must_not_use_legacy_snapshot(*_args, **_kwargs):
        raise AssertionError("bound StudentProfile must not fall back to employment snapshot scope")

    monkeypatch.setattr(employment_service.teacher_guard, "scope_match_row", _must_not_use_legacy_snapshot)

    with pytest.raises(AppException) as exc_info:
        employment_service._scope_emp(db, 7, {"userId": "9"})

    assert exc_info.value.code == "NO_PERMISSION"
    assert exc_info.value.http_status == 403
    assert db.values == []


def test_t7_migration_extends_current_single_head_and_metadata_registers_model():
    migration = _src("backend/alembic/versions/20260820_teacher_emp_recommendation.py")
    metadata = _src("backend/app/db/base.py")
    assert 'revision = "20260820_teacher_emp_reco"' in migration
    assert 'down_revision = "20260818_acad_bc_final"' in migration
    assert 'op.create_table(' in migration and '"t_emp_recommendation"' in migration
    assert 'employment_recommendation as _employment_recommendation' in metadata


def test_t7_teacher_aggregator_mounts_employment_without_touching_student_mobile_router():
    aggregator = _src("backend/app/api/v1/teacher_mobile_students.py")
    assert 'teacher_mobile_employment import router as employment_router' in aggregator
    assert 'router.include_router(employment_router)' in aggregator
    t7_route = _src("backend/app/api/v1/teacher_mobile_employment.py")
    assert 'prefix="/employment"' in t7_route
    assert 'require_module("employment")' in t7_route
