from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, got {count}")
    p.write_text(text.replace(old, new), encoding="utf-8")


manifest = "backend/app/modules/academic_affairs/services/academic_affairs_archive_manifest_service.py"
replace_exact(
    manifest,
    '''        if result["result"] != "PASS":
            blocked.append(f"{code}:{result['ruleCode']}")
''',
    '''        if result["result"] in archive_service._BLOCKING_RESULTS:
            blocked.append(f"{code}:{result['ruleCode']}")
''',
)

test_path = Path("backend/tests/test_aa_archive_d_w1_contract.py")
text = test_path.read_text(encoding="utf-8")
append = r'''


def _manifest_domains(*, graduation_state: str):
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    states = {}
    for code, _label in service._DOMAINS:
        state = graduation_state if code == "GRADUATION" else "PASS"
        states[code] = {
            "recordCount": 0,
            "present": state == "PASS",
            "result": state,
            "blockingCount": 1 if state in {"BLOCKED", "UNKNOWN"} else 0,
            "ruleCode": f"{code}_D_W1_TEST",
            "summary": f"{code}:{state}",
            "evidence": [],
        }
    return states


def test_d_w1_manifest_allows_not_applicable_as_nonblocking(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest

    monkeypatch.setattr(
        manifest.archive_service,
        "_evaluate_domains",
        lambda _db, _term_id, _term_code: _manifest_domains(graduation_state="NOT_APPLICABLE"),
    )
    batch = SimpleNamespace(term_id=9, term_code="2025-2026-2")
    counts, hashes, max_ids = manifest._live_manifest_parts(SimpleNamespace(), batch)
    assert counts["GRADUATION"] == 0
    assert hashes["GRADUATION"]
    assert max_ids["GRADUATION"] is None


def test_d_w1_manifest_blocks_unknown_before_formal_archive(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest

    monkeypatch.setattr(
        manifest.archive_service,
        "_evaluate_domains",
        lambda _db, _term_id, _term_code: _manifest_domains(graduation_state="UNKNOWN"),
    )
    batch = SimpleNamespace(term_id=9, term_code="2025-2026-2")
    with pytest.raises(AppException) as exc:
        manifest._live_manifest_parts(SimpleNamespace(), batch)
    assert exc.value.http_status == 409
    assert "GRADUATION:GRADUATION_D_W1_TEST" in exc.value.details["blockingRules"]
'''
if "test_d_w1_manifest_allows_not_applicable_as_nonblocking" in text:
    raise SystemExit("manifest tests already present")
test_path.write_text(text + append, encoding="utf-8")
print("Academic D-W1 manifest four-state alignment applied")
