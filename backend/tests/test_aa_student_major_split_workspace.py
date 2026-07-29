"""学生 PC 专业分流必须使用本人独立志愿工作区。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_major_split_route_uses_dedicated_page():
    router = _read("student-portal/src/router/index.js")

    assert "StudentMajorSplitView.vue" in router
    assert "academicSection('academic/major-split'" not in router


def test_major_split_workspace_uses_real_batch_and_choice_contract():
    source = _read("student-portal/src/views/academic/StudentMajorSplitView.vue")

    assert "portalApi.academicMajorSplit()" in source
    assert "portalApi.academicMajorSplitSubmit" in source
    assert "batchId:" in source
    assert "choices" in source
    assert "optionId" in source
    assert "priority: index + 1" in source
    assert "await load()" in source
    assert "最终仍由服务器校验" in source


def test_major_split_workspace_blocks_duplicate_choices_and_fake_result():
    source = _read("student-portal/src/views/academic/StudentMajorSplitView.vue")

    assert "new Set(choices).size === choices.length" in source
    assert "志愿提交不等于录取" in source
    assert "客户端不自行计算录取结论" in source
    assert "window.prompt" not in source
