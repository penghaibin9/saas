from __future__ import annotations

# 仅用于把旧请假测试改成真实页面合同；禁止作为 pytest 运行时请求适配器加载。
from pathlib import Path
import re


TEST_FILE = Path("backend/tests/test_affairs_leave.py")
ENTITY_ACTIONS = (
    "approve",
    "reject",
    "return",
    "resubmit",
    "cancel",
    "cancel-confirm",
    "proxy-cancel",
    "overdue-handle",
    "extension",
    "extension-approve",
)


def insert_explicit_version_helpers(text: str) -> str:
    if "def _leave_action(" in text:
        return text
    marker = "\n\ndef test_l1_apply_creates_workflow"
    if marker not in text:
        raise RuntimeError("missing test_l1 marker for leave helper insertion")
    helpers = '''


def _leave_detail(client, hdr, lid):
    response = client.get(f"/api/v1/student-affairs/leave/{lid}", headers=hdr)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _version(client, hdr, lid):
    return int(_leave_detail(client, hdr, lid)["version"])


def _leave_action(client, hdr, lid, action, body=None):
    """模拟真实页面：先读取当前记录版本，再显式提交本次写操作。"""
    payload = dict(body or {})
    if action == "extension-approve":
        payload.setdefault("action", "APPROVE")
    if action == "cancel-confirm":
        payload.setdefault("action", "CONFIRM")
    payload.setdefault("version", _version(client, hdr, lid))
    return client.post(
        f"/api/v1/student-affairs/leave/{lid}/{action}",
        headers=hdr,
        json=payload,
    )
'''
    return text.replace(marker, helpers + marker, 1)


def replace_standard_actions(text: str) -> str:
    action_re = "|".join(re.escape(action) for action in ENTITY_ACTIONS)

    # 写操作已经带 JSON body：保留业务字段，只由测试助手显式补入当前页面版本。
    with_body = re.compile(
        rf'''client\.post\(
            f"/api/v1/student-affairs/leave/\{{lid\}}/(?P<action>{action_re})",
            \s*headers=(?P<hdr>hdr|admin|couns),
            \s*json=(?P<body>\{{.*?\}})
        \)''',
        re.S | re.X,
    )
    text = with_body.sub(
        lambda match: (
            f'_leave_action(client, {match.group("hdr")}, lid, '
            f'"{match.group("action")}", {match.group("body")})'
        ),
        text,
    )

    # 无 body 的审批类动作也必须显式传 version；助手会补默认 APPROVE/CONFIRM action。
    without_body = re.compile(
        rf'''client\.post\(
            f"/api/v1/student-affairs/leave/\{{lid\}}/(?P<action>{action_re})",
            \s*headers=(?P<hdr>hdr|admin|couns)
        \)''',
        re.S | re.X,
    )
    text = without_body.sub(
        lambda match: (
            f'_leave_action(client, {match.group("hdr")}, lid, '
            f'"{match.group("action")}")'
        ),
        text,
    )
    return text


def replace_cross_scope_action(text: str) -> str:
    old = '''    r = client.post(f"/api/v1/student-affairs/leave/{lid}/proxy-cancel",
                    headers=_hdr(client, "counselor01"),
                    json={"actualReturnAt": "2026-03-02"})
'''
    new = '''    version = _version(client, admin, lid)
    r = client.post(f"/api/v1/student-affairs/leave/{lid}/proxy-cancel",
                    headers=_hdr(client, "counselor01"),
                    json={"actualReturnAt": "2026-03-02", "version": version})
'''
    if old in text:
        return text.replace(old, new, 1)
    if 'json={"actualReturnAt": "2026-03-02", "version": version}' in text:
        return text
    raise RuntimeError("missing cross-class proxy-cancel test anchor")


def audit(text: str) -> None:
    action_re = "|".join(re.escape(action) for action in ENTITY_ACTIONS)
    direct = re.findall(
        rf'client\.post\(f"/api/v1/student-affairs/leave/\{{lid\}}/({action_re})"',
        text,
    )
    # 唯一允许的直接写调用是越权测试：它显式从管理员详情读取 version，再用辅导员身份提交。
    if direct != ["proxy-cancel"]:
        raise RuntimeError(f"unexpected direct leave writes remain: {direct}")
    if "def _leave_action(" not in text or 'payload.setdefault("version", _version' not in text:
        raise RuntimeError("explicit leave version helper missing")
    if '"reason": "回家有事"' in text:
        raise RuntimeError("four-character legacy leave reason remains")
    if 'json={"actualReturnAt": "2026-03-02", "version": version}' not in text:
        raise RuntimeError("cross-class leave action lacks explicit version")


def main() -> None:
    text = TEST_FILE.read_text(encoding="utf-8")
    text = text.replace('"reason": "回家有事"', '"reason": "回家处理家庭事务"')
    text = insert_explicit_version_helpers(text)
    text = replace_standard_actions(text)
    text = replace_cross_scope_action(text)
    audit(text)
    TEST_FILE.write_text(text, encoding="utf-8")
    print("affairs leave tests now use explicit versions")


if __name__ == "__main__":
    main()
