"""毕业设计第七轮：学校 PC 成绩复核/发布契约。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/modules/graduation/views/GraduationDefenseGradeView.vue"
API = ROOT / "frontend/src/modules/graduation/api/graduation-defense-grade.api.js"
ROUTER = ROOT / "backend/app/modules/graduation/routers/graduation_sensitive_router.py"
SERVICE = ROOT / "backend/app/modules/graduation/services/graduation_grade_service.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pc_grade_publish_button_uses_reviewed_state():
    text = _text(VIEW)
    assert "grade.status === 'REVIEWED'" in text
    assert "grade.status === 'CALCULATED' && grade.reviewedAt" not in text


def test_pc_grade_batch_tabs_include_reviewed_state():
    text = _text(VIEW)
    assert "{ value: 'REVIEWED', label: '已复核' }" in text
    calculated = text.index("{ value: 'CALCULATED', label: '已核算' }")
    reviewed = text.index("{ value: 'REVIEWED', label: '已复核' }")
    published = text.index("{ value: 'PUBLISHED', label: '已发布' }")
    assert calculated < reviewed < published


def test_reviewed_filter_reaches_backend_sql():
    api = _text(API)
    router = _text(ROUTER)
    service = _text(SERVICE)
    assert "getGrades(params = {}) { return callList(GRADE, params) }" in api
    assert "status: Optional[str] = None" in router
    assert "grade.list_grades(page, pageSize, keyword=keyword, status=status, batch_id=batchId)" in router
    assert "GraduationGrade.status == status" in service
