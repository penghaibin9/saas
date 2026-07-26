"""毕业设计第七轮：学校 PC 成绩复核/发布契约。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/modules/graduation/views/GraduationDefenseGradeView.vue"


def _view_text() -> str:
    return VIEW.read_text(encoding="utf-8")


def test_pc_grade_publish_button_uses_reviewed_state():
    text = _view_text()
    assert "grade.status === 'REVIEWED'" in text
    assert "grade.status === 'CALCULATED' && grade.reviewedAt" not in text


def test_pc_grade_batch_tabs_include_reviewed_state():
    text = _view_text()
    assert "{ value: 'REVIEWED', label: '已复核' }" in text
    calculated = text.index("{ value: 'CALCULATED', label: '已核算' }")
    reviewed = text.index("{ value: 'REVIEWED', label: '已复核' }")
    published = text.index("{ value: 'PUBLISHED', label: '已发布' }")
    assert calculated < reviewed < published
