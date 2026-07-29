"""学生 PC 教材签收必须使用本人独立工作区和真实签收接口。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_textbook_route_uses_dedicated_page():
    router = _read("student-portal/src/router/index.js")

    assert "StudentTextbookView.vue" in router
    assert "academicSection('academic/textbook'" not in router


def test_textbook_workspace_requires_real_record_and_server_refresh():
    source = _read("student-portal/src/views/academic/StudentTextbookView.vue")

    assert "portalApi.academicTextbook()" in source
    assert "portalApi.academicTextbookSign(id)" in source
    assert "record.recordId || record.distributionRecordId || record.id" in source
    assert "await load()" in source
    assert "提交后不可由学生端撤回" in source
    assert "接口失败时显示成功" in source
    assert "window.prompt" not in source


def test_textbook_workspace_never_equates_receipt_with_payment_or_grade():
    source = _read("student-portal/src/views/academic/StudentTextbookView.vue")

    assert "签收仅确认教材实物已交付本人" in source
    assert "不代表费用已经缴清或课程成绩认定" in source
