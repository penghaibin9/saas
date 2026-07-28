from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"sensitive repair anchor missing: {path}: {old[:100]!r}")
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


def patch_mental_guard() -> None:
    path = "backend/app/services/affairs_sensitive_audit_guard.py"
    replace_once(
        path,
        '''def explicit_detail_permission(user, student_id, scope_ids) -> bool:
    """角色名称不能代替权限；通配与自定义角色均复用统一权限执行层。"""
    if not has_permission(user, "studentAffairs.risk.psyDetail.view"):
        return False
    if scope_ids is None:
        return True
    return int(student_id) in {int(x) for x in scope_ids}


''',
        '''# 明细角色与逐生范围由 affairs_mental_service._can_view_detail 正式实现；
# 本守卫只负责把审计改为 fail-closed，禁止再次覆盖角色边界。

''',
    )
    replace_once(
        path,
        '''def install() -> None:
    from app.services import affairs_mental_service as mental
    mental._sensitive_view_audit = strict_sensitive_view_audit
    mental._can_view_detail = explicit_detail_permission
''',
        '''def install() -> None:
    from app.services import affairs_mental_service as mental
    mental._sensitive_view_audit = strict_sensitive_view_audit
''',
    )


def patch_talk_formal_contract() -> None:
    service = "backend/app/services/affairs_talk_service.py"
    replace_once(
        service,
        '_PSY_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "PSYCHOLOGY_TEACHER"}',
        '_PSY_ROLES = {"SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN", "PSYCHOLOGY_TEACHER"}',
    )
    replace_once(
        service,
        '''        "relatedRiskId": str(x.related_risk_id or ""), "relatedContactId": str(x.related_contact_id or ""),
        "status": x.status, "statusLabel": L_TALK.get(x.status, x.status), "version": x.version,
    }
''',
        '''        "relatedRiskId": str(x.related_risk_id or ""), "relatedContactId": str(x.related_contact_id or ""),
        "status": x.status, "statusLabel": L_TALK.get(x.status, x.status), "version": x.version,
        "allowedActions": (
            (["FOLLOW", "CLOSE"]
             + ([] if x.related_risk_id else ["TO_RISK"])
             + ([] if x.related_contact_id else ["TO_HOME_SCHOOL"]))
            if x.status in ("COMPLETED", "FOLLOW_UP") else []
        ),
    }
''',
    )

    guard = "backend/app/services/affairs_talk_guard.py"
    replace_once(
        guard,
        '''    old_row = talk._talk_row
    old_create = talk.create_talk
''',
        '''    old_create = talk.create_talk
''',
    )
    replace_once(
        guard,
        '''    def can_view_psy(user) -> bool:
        return has_permission(user or {}, "studentAffairs.risk.psyDetail.view")

    def talk_row(row, user, student=None):
        data = old_row(row, user, student)
        if row.status in ("COMPLETED", "FOLLOW_UP"):
            actions = ["FOLLOW", "CLOSE"]
            if not row.related_risk_id:
                actions.append("TO_RISK")
            if not row.related_contact_id:
                actions.append("TO_HOME_SCHOOL")
            data["allowedActions"] = actions
        else:
            data["allowedActions"] = []
        return data

''',
        '''''',
    )
    replace_once(
        guard,
        '''            return talk_row(row, user, student)
''',
        '''            return talk._talk_row(row, user, student)
''',
    )
    replace_once(
        guard,
        '''    talk._students_by_ids = students_by_ids
    talk._can_view_psy = can_view_psy
    talk._talk_row = talk_row
    talk.create_talk = create_talk
''',
        '''    talk._students_by_ids = students_by_ids
    talk.create_talk = create_talk
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


def test_formal_mental_service_keeps_sa_admin_out_of_raw_detail():
    source = read("backend/app/services/affairs_mental_service.py")
    guard = read("backend/app/services/affairs_sensitive_audit_guard.py")
    assert '_PSY_DETAIL_ROLES = {"PSYCHOLOGY_TEACHER", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}' in source
    assert "STUDENT_AFFAIRS_ADMIN 不在此列" in source
    assert "mental._can_view_detail =" not in guard
    assert "mental._sensitive_view_audit = strict_sensitive_view_audit" in guard


def test_talk_sensitive_role_and_actions_live_in_formal_service():
    service = read("backend/app/services/affairs_talk_service.py")
    guard = read("backend/app/services/affairs_talk_guard.py")
    assert '_PSY_ROLES = {"SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN", "PSYCHOLOGY_TEACHER"}' in service
    assert '"allowedActions"' in service
    assert "talk._can_view_psy =" not in guard
    assert "talk._talk_row =" not in guard
''', encoding="utf-8")


if __name__ == "__main__":
    patch_risk_detail_roles()
    patch_mental_guard()
    patch_talk_formal_contract()
    patch_static_contracts()
    print("student affairs sensitive scope round6 passed", flush=True)
