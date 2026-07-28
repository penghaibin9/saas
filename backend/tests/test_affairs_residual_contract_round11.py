from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_risk_positive_inputs_meet_formal_length_contract():
    text = read("backend/tests/test_affairs_risk.py")
    assert '"reason": "情况恶化"' not in text
    assert '"reason": "风险情况持续恶化需要升级"' in text
    assert '"reason": "工作职责调整后办理交接"' in text


def test_missing_version_negative_case_remains_direct_request():
    text = read("backend/tests/test_affairs_risk.py")
    assert 'missing = client.post(f"{BASE}/risk/records/{rid}/process"' in text
    assert 'missing = post_versioned(client, f"{BASE}/risk/records/{rid}/process"' not in text
