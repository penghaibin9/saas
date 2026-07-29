from pathlib import Path
import re


def _whitespace_tolerant_pattern(value: str) -> str:
    """Ignore indentation changes without consuming the indentation of the following line."""
    parts = re.split(r"(\n|[ \t]+)", value)
    out = []
    for part in parts:
        if part == "\n":
            # May absorb trailing spaces before the newline, never leading spaces after it.
            out.append(r"[ \t]*\n")
        elif part and all(char in " \t" for char in part):
            out.append(r"[ \t]+")
        else:
            out.append(re.escape(part))
    return "".join(out)


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old in text:
        file.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    pattern = _whitespace_tolerant_pattern(old)
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise RuntimeError(
            f"round8 anchor missing/ambiguous: {path}: matches={len(matches)} old={old[:120]!r}"
        )
    match = matches[0]
    file.write_text(text[:match.start()] + new + text[match.end():], encoding="utf-8")


def patch_mobile() -> None:
    path = "backend/tests/test_affairs_mobile.py"
    replace_once(
        path,
        "from __future__ import annotations\n\nfrom affairs_contract_test_support",
        "from __future__ import annotations\n\nfrom datetime import datetime, timedelta\n\nfrom affairs_contract_test_support",
    )
    replace_once(
        path,
        '''    ids = {"A": a.id, "zhang": zhang.id, "li": li.id}
    db.commit()
    db.close()
    return ids
''',
        '''    ids = {"A": a.id, "zhang": zhang.id, "li": li.id}
    db.commit()
    db.close()
    ensure_workflow_assignees([ids["zhang"], ids["li"]])
    return ids
''',
    )
    replace_once(
        path,
        '''def _make_leave(client, hdr, sid, approve=False):
    lid = client.post(f"{BASE}/leave", headers=hdr, json={
        "studentId": str(sid), "leaveType": "PERSONAL", "startTime": "2026-03-01",
        "endTime": "2026-03-02", "reason": "回家有事"}).json()["data"]["id"]
    if approve:
        client.post(f"{BASE}/leave/{lid}/approve", headers=hdr)
    return lid
''',
        '''def _make_leave(client, hdr, sid, approve=False):
    start = datetime.utcnow() + timedelta(days=10)
    end = start + timedelta(days=1)
    lid = client.post(f"{BASE}/leave", headers=hdr, json={
        "studentId": str(sid), "leaveType": "PERSONAL",
        "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime": end.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": "学生因家庭事务申请短期请假"}).json()["data"]["id"]
    if approve:
        post_versioned(client, f"{BASE}/leave/{lid}/approve", headers=hdr)
    return lid
''',
    )


def patch_profile() -> None:
    path = "backend/tests/test_affairs_profile.py"
    replace_once(
        path,
        "from __future__ import annotations\n\nfrom affairs_contract_test_support",
        "from __future__ import annotations\n\nfrom datetime import datetime, timedelta\n\nfrom affairs_contract_test_support",
    )
    replace_once(
        path,
        '''    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids
''',
        '''    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    ensure_workflow_assignees([ids["sa"], ids["sb"]])
    return ids
''',
    )
    replace_once(
        path,
        '''def _leave_closed(client, hdr, sid):
    lid = client.post(f"{BASE}/leave", headers=hdr, json={
        "studentId": str(sid), "leaveType": "PERSONAL", "startTime": "2026-03-01",
        "endTime": "2026-03-02", "reason": "回家有事"}).json()["data"]["id"]
    client.post(f"{BASE}/leave/{lid}/approve", headers=hdr)
    client.post(f"{BASE}/leave/{lid}/cancel", headers=hdr, json={"proofNote": "已返校"})
    client.post(f"{BASE}/leave/{lid}/cancel-confirm", headers=hdr, json={"note": "确认返校"})
''',
        '''def _leave_closed(client, hdr, sid):
    start = datetime.utcnow() + timedelta(days=10)
    end = start + timedelta(days=1)
    lid = client.post(f"{BASE}/leave", headers=hdr, json={
        "studentId": str(sid), "leaveType": "PERSONAL",
        "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime": end.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": "学生因家庭事务申请短期请假"}).json()["data"]["id"]
    post_versioned(client, f"{BASE}/leave/{lid}/approve", headers=hdr)
    post_versioned(client, f"{BASE}/leave/{lid}/cancel", headers=hdr,
                   json={"proofNote": "学生已经返校并提交销假说明"})
    post_versioned(client, f"{BASE}/leave/{lid}/cancel-confirm", headers=hdr,
                   json={"note": "辅导员确认学生已经安全返校"})
''',
    )


def patch_optimistic_and_todo() -> None:
    path = "backend/tests/test_affairs_optimistic_lock_round1.py"
    replace_once(
        path,
        '''    ids = {"sa": sa.id, "owner": owner.id}
    db.close()
    return ids
''',
        '''    ids = {"sa": sa.id, "owner": owner.id}
    db.close()
    ensure_workflow_assignees(ids["sa"])
    ensure_owner_scope("ol_owner01", ids["sa"])
    return ids
''',
    )
    replace_once(
        path,
        '''    missing = post_versioned(client, f"{BASE}/risk/records/{rid}/process", headers=hdr,
                           json={"content": "缺少 version 也应拦截不少于"})
''',
        '''    missing = client.post(f"{BASE}/risk/records/{rid}/process", headers=hdr,
                          json={"content": "缺少 version 也应拦截不少于"})
''',
    )

    todo = "backend/tests/test_affairs_todo_drilldown.py"
    replace_once(
        todo,
        "import inspect\n\nTID",
        "import inspect\n\nfrom affairs_contract_test_support import ensure_workflow_assignees\n\nTID",
    )
    replace_once(
        todo,
        '''    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids
''',
        '''    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    ensure_workflow_assignees([ids["sa"], ids["sb"]])
    return ids
''',
    )


def patch_risk_and_mental() -> None:
    risk = "backend/tests/test_affairs_risk.py"
    replace_once(
        risk,
        '''    missing = post_versioned(client, f"{BASE}/risk/records/{rid}/process", headers=hdr,
                          json={"content": "不带 version 的处置"})
''',
        '''    missing = client.post(f"{BASE}/risk/records/{rid}/process", headers=hdr,
                          json={"content": "不带 version 的处置"})
''',
    )
    replace_once(risk, '"reason": "工作交接"', '"reason": "工作职责调整后办理交接"')

    mental = "backend/tests/test_affairs_mental.py"
    replace_once(mental, 'json={"content": "重复升级", "version": r["version"]}',
                 'json={"content": "重复升级请求确认", "version": r["version"]}')


def patch_mysql_trust_test() -> None:
    path = "backend/tests/test_affairs_round1_trust.py"
    replace_once(
        path,
        "def test_cockpit_domain_error_not_fake_zero():",
        "def test_cockpit_domain_error_not_fake_zero(db_mode):",
    )


def patch_contract() -> None:
    Path("backend/tests/test_affairs_runtime_contract_round8.py").write_text('''from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_mobile_and_profile_leave_inputs_are_time_safe():
    for name in ("test_affairs_mobile.py", "test_affairs_profile.py"):
        text = read("backend/tests/" + name)
        assert "datetime.utcnow() + timedelta(days=10)" in text
        assert "学生因家庭事务申请短期请假" in text
        assert "ensure_workflow_assignees" in text
        assert '"2026-03-01"' not in text


def test_missing_version_negative_cases_stay_explicit():
    risk = read("backend/tests/test_affairs_risk.py")
    lock = read("backend/tests/test_affairs_optimistic_lock_round1.py")
    assert 'missing = client.post(f"{BASE}/risk/records/{rid}/process"' in risk
    assert 'missing = client.post(f"{BASE}/risk/records/{rid}/process"' in lock


def test_cockpit_failure_contract_uses_mysql_fixture():
    text = read("backend/tests/test_affairs_round1_trust.py")
    assert "def test_cockpit_domain_error_not_fake_zero(db_mode):" in text
''', encoding="utf-8")


if __name__ == "__main__":
    patch_mobile()
    patch_profile()
    patch_optimistic_and_todo()
    patch_risk_and_mental()
    patch_mysql_trust_test()
    patch_contract()
    print("student affairs runtime round8 passed", flush=True)
