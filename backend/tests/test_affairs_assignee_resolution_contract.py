"""学工受理人解析静态合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_counselor_priority_and_college_fail_closed():
    source = (ROOT / "backend/app/services/affairs_assignee_service.py").read_text(encoding="utf-8")
    assert 'duty_type == "TEMP", 0' in source
    assert 'duty_type == "PRIMARY", 1' in source
    assert 'duty_type == "CO", 2' in source
    college_block = source.split('if node == "COLLEGE_REVIEW":', 1)[1]
    assert "if not college:" in college_block
    assert "return []" in college_block
    assert "return candidates" in source
