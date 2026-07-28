from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"round10 anchor missing: {path}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_cockpit_test() -> None:
    replace_once(
        "backend/tests/test_affairs_cockpit.py",
        '''    assert all("route" in x and "status" in x for x in d["domains"])
    assert all(x["status"] == "OK" for x in d["domains"])
    assert all(x.get("total") is not None for x in d["domains"])
    assert "totals" in d and "disciplineReconcileConsistent" in d
''',
        '''    assert all("route" in x and "status" in x for x in d["domains"])
    domains = {item["key"]: item for item in d["domains"]}
    core = {"student", "class", "leave", "dorm", "risk", "aid", "funding",
            "discipline", "activity", "talk", "mental"}
    assert core <= set(domains)
    assert all(domains[key]["status"] == "OK" for key in core)
    assert all(domains[key].get("total") is not None for key in core)
    # 尚无独立聚合口径的模块必须明确降级，禁止假装成功并返回 0。
    for key in ("club", "organization", "partyLeague"):
        assert domains[key]["status"] == "DEGRADED"
        assert domains[key]["total"] is None
        assert domains[key]["message"]
    assert all(item["status"] != "ERROR" for item in d["domains"])
    assert "totals" in d and "disciplineReconcileConsistent" in d
''',
    )


def patch_contract() -> None:
    Path("backend/tests/test_affairs_cockpit_truth_contract.py").write_text('''from pathlib import Path


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
''', encoding="utf-8")


if __name__ == "__main__":
    patch_cockpit_test()
    patch_contract()
    print("student affairs cockpit round10 passed", flush=True)
