from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"sensitive repair anchor missing: {path}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_risk_detail_roles() -> None:
    replace_once(
        "backend/app/services/affairs_risk_service.py",
        '''def _can_view_mental(user) -> bool:
    return has_permission(user or {}, "studentAffairs.risk.psyDetail.view")
''',
        '''_MENTAL_DETAIL_ROLES = {"PSYCHOLOGY_TEACHER", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}


def _can_view_mental(user) -> bool:
    """心理风险原始明细使用独立角色白名单，禁止 studentAffairs.* 通配放大权限。

    STUDENT_AFFAIRS_ADMIN 与 COUNSELOR 即使拥有风险处置能力，也只能查看摘要；
    PSYCHOLOGY_TEACHER 还必须经过 PSY_STUDENT 数据范围校验。
    """
    role = str((user or {}).get("currentRoleCode") or "").upper()
    return role in _MENTAL_DETAIL_ROLES
''',
    )


def patch_static_contracts() -> None:
    path = Path("backend/tests/test_affairs_sensitive_role_contract.py")
    path.write_text('''from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_risk_mental_detail_does_not_use_wildcard_permission():
    source = read("backend/app/services/affairs_risk_service.py")
    block = source.split("_MENTAL_DETAIL_ROLES", 1)[1].split("def _sensitive_view_audit", 1)[0]
    assert '{"PSYCHOLOGY_TEACHER", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}' in block
    assert 'has_permission(user or {}, "studentAffairs.risk.psyDetail.view")' not in block
    assert "STUDENT_AFFAIRS_ADMIN" not in block.split("def _can_view_mental", 1)[1]
    assert "COUNSELOR" not in block.split("def _can_view_mental", 1)[1]


def test_formal_mental_service_keeps_sa_admin_out_of_raw_detail():
    source = read("backend/app/services/affairs_mental_service.py")
    assert '_PSY_DETAIL_ROLES = {"PSYCHOLOGY_TEACHER", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}' in source
    assert "STUDENT_AFFAIRS_ADMIN 不在此列" in source
''', encoding="utf-8")


if __name__ == "__main__":
    patch_risk_detail_roles()
    patch_static_contracts()
    print("student affairs sensitive scope round6 passed", flush=True)
