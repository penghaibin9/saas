"""学生台账、调宿节点与处分投影静态回归合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_student_service_ledger_identity_is_read_only_and_versioned():
    text = read("backend/app/services/affairs_student_ledger_guard.py")
    assert 'path.startswith("/api/v1/campus-service/students/")' in text
    assert '"name", "studentNo", "studentId", "classId", "className"' in text
    assert "atomic_versioned_update" in text
    assert 'StudentProfile.tenant_id == _tid()' not in text  # target scope is enforced through require_student
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
    text = read("backend/app/services/affairs_discipline_integrity_guard.py")
    assert "def ensure_service_student" in text
    assert "shadow.identity_snapshot(db, profile)" in text
    assert "return int(record.id)" in text
    assert "return int(student_id)" not in text
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
