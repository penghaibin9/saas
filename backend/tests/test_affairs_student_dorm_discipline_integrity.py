"""学生台账、调宿节点与处分投影静态回归合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_student_service_ledger_identity_is_read_only_and_versioned():
    text = read("backend/app/services/affairs_student_ledger_guard.py")
    assert 'path.startswith("/api/v1/campus-service/students/")' in text
    # 身份字段的只读约束由主档比较器统一执行，不再绑定旧字段元组字面量。
    assert "shadow.assert_identity_immutable" in text
    assert "没有可保存的服务字段" in text
    assert 'payload["careLevel"]' in text
    assert 'payload["building"]' in text
    assert 'payload["room"]' in text
    assert 'payload["counselor"]' in text
    assert "atomic_versioned_update" in text
    assert 'StudentProfile.tenant_id == _tid()' not in text
    assert 'build_affairs_context(get_current_user_ctx() or {}, db).require_student' in text
    assert 'CsServiceStudent.tenant_id == _tid()' in text


def test_dorm_transfer_is_node_role_and_assignee_bound():
    text = read("backend/app/services/affairs_dorm_node_guard.py")
    assert "学生只能提交本人的调宿申请" in text
    assert 'node == "COUNSELOR_REVIEW"' in text
    assert 'node == "DORM_MANAGER_REVIEW"' in text
    assert "_require_pending_assignee" in text
    assert "当前节点仅目标楼栋宿管可审批" in text
    assert "StudentStageEvent" in text
    assert "DORM.TRANSFER.EXECUTED" in text


def test_discipline_projection_never_uses_profile_id_as_shadow_id():
    """NEW-P0-03：处分投影绝不能拿 StudentProfile.id 当 CsServiceStudent.id。

    原断言钉的是另一版实现的源码字符串（函数名 ensure_service_student、
    `shadow.identity_snapshot(db, profile)` 等），与包 11 实际交付的实现对不上，
    自交付起就没绿过。真正要守的是能力，改为按能力断言：

    - 存在「取或建服务台账」的函数，且返回的是 CsServiceStudent 实体本身；
    - 台账身份字段一律取自学籍主档，不采信调用方入参；
    - 绝不出现 `return int(student_id)` 这种「拿学籍 id 冒充台账 id」的降级；
    - 投影去重提示仍在。
    """
    import inspect

    from app.services import affairs_discipline_integrity_guard as guard

    text = read("backend/app/services/affairs_discipline_integrity_guard.py")

    ensure = getattr(guard, "_ensure_cs_student", None)
    assert callable(ensure), "缺少「取或建服务台账」的函数，投影将无处挂载"

    source = inspect.getsource(ensure)
    # 核心红线：任何形式的「学籍 id 当台账 id 用」都不允许。
    assert "return int(student_id)" not in text
    assert "else int(student_id)" not in text
    # 身份必须来自主档快照，不能采信调用方传进来的姓名/学号。
    assert "profile.real_name" in source and "profile.student_no" in source
    # 必须锁住主档与台账，避免并发建出两条台账。
    assert "with_for_update" in source
    # 返回值是台账实体（调用点再取 .id），不是学籍 id。
    assert "return existing" in source or "return record" in source
    assert "该处分已存在投影" in text


def test_discipline_revised_appeal_changes_case_and_projection():
    backend = read("backend/app/services/affairs_discipline_integrity_guard.py")
    frontend = read("frontend/src/modules/studentAffairs/views/discipline/DisciplineAppealView.vue")
    api = read("frontend/src/modules/studentAffairs/api/disciplineIntegrity.api.js")
    assert "变更处分必须提交 revisedDiscType" in backend
    assert "case.disc_type = revised_type" in backend
    assert "projection.disc_type = revised_type" in backend
    assert "DISCIPLINE_REVISED" in backend
    assert "变更后的处分类型" in frontend
    assert "revisedDiscType" in frontend
    assert "version: dialog.version" in frontend
    assert "body.revisedDiscType" in api
    assert "description=\"" not in frontend


def test_router_installs_discipline_and_dorm_overrides_in_safe_order():
    source = read("backend/app/api/v1/router.py")
    discipline = source.index("install_discipline_integrity_guard()")
    review = source.index("install_affairs_four_end_review_guard()")
    dorm = source.index("install_dorm_node_guard()")
    terminal = source.index("install_affairs_four_end_terminal_guard(api_router)")
    assert discipline < review < dorm < terminal
