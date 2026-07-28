from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_cockpit_test_does_not_require_fake_green_domains():
    test = read("backend/tests/test_affairs_cockpit.py")
    assert 'all(x["status"] == "OK" for x in d["domains"])' not in test
    assert '("club", "organization", "partyLeague")' in test
    assert 'domains[key]["status"] == "DEGRADED"' in test


def test_cockpit_service_keeps_explicit_degraded_contract():
    service = read("backend/app/services/affairs_cockpit_service.py")
    assert '"status": "DEGRADED"' in service
    assert "绝不能把缺口显示为 0" in service
    assert '"status": "ERROR"' in service
    assert '"total": None' in service
