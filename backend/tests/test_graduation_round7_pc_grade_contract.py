"""毕业设计第七轮：学校 PC 成绩复核/发布契约。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/modules/graduation/views/GraduationDefenseGradeView.vue"
API = ROOT / "frontend/src/modules/graduation/api/graduation-defense-grade.api.js"
ROUTER = ROOT / "backend/app/modules/graduation/routers/graduation_sensitive_router.py"
SERVICE = ROOT / "backend/app/modules/graduation/services/graduation_grade_service.py"
READ_MODEL = ROOT / "backend/app/modules/graduation/services/graduation_grade_read_service.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pc_grade_publish_button_uses_reviewed_state():
    text = _text(VIEW)
    assert "grade.status === 'REVIEWED'" in text
    assert "grade.status === 'CALCULATED' && grade.reviewedAt" not in text


def test_pc_grade_batch_queue_exposes_reviewed_as_pending_publish():
    text = _text(VIEW)
    assert "{ value: 'REVIEW', label: '待复核', status: 'CALCULATED' }" in text
    assert "{ value: 'PUBLISH', label: '待发布', status: 'REVIEWED' }" in text
    assert "status === 'CALCULATED'" in text
    assert "status === 'REVIEWED'" in text


def test_reviewed_and_missing_filters_reach_sql_read_model():
    api = _text(API)
    router = _text(ROUTER)
    service = _text(SERVICE)
    read_model = _text(READ_MODEL)
    assert "getGrades(params = {}) { return callList(GRADE, params) }" in api
    assert "status: Optional[str] = None" in router
    assert "missingType: Optional[str] = None" in router
    assert "grade.list_grades(" in router
    assert "status=status" in router
    assert "missing_type=missingType" in router
    # 成绩列表唯一实现为 SQL 读模型，由 service 模块显式绑定（不再依赖包初始化替换）
    assert "from app.modules.graduation.services.graduation_grade_read_service import list_grades" in service
    assert "GraduationGrade.status == status" in read_model
    assert "_missing_clause(missing_type)" in read_model
    assert "def list_grades" not in service, "旧的 Python 过滤实现已删除，不得重新出现第二份实现"
