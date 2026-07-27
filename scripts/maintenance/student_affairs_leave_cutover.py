from __future__ import annotations

from pathlib import Path
import re


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError(f"missing anchor: {label}")
    return text.replace(old, new, 1)


def first_cut() -> None:
    p = "student-portal/src/services/portalApi.js"
    s = read(p)
    s = replace_once(
        s,
        "  affairsLeave: () => request('/portal/affairs/leave'),\n",
        "  affairsLeave: () => request('/portal/affairs/leave'),\n  affairsLeaveApply: (body) => request('/portal/affairs/leave', { method: 'POST', body }),\n",
        "portal leave apply",
    )
    write(p, s)

    p = "student-portal/src/views/affairs/AffairsFourEndView.vue"
    s = read(p)
    s = replace_once(
        s,
        "portalApi.affairsServiceApply({ serviceKey: 'LEAVE', ...leaveForm })",
        "portalApi.affairsLeaveApply({ ...leaveForm })",
        "student pc legacy leave call",
    )
    write(p, s)

    p = "miniapp/src/services/realApi.js"
    s = read(p)
    anchor = "export const affairsLeaveMy = () => realRequest('/mobile/affairs/leave/my')"
    s = replace_once(
        s,
        anchor,
        anchor
        + "\nexport const affairsLeaveApply = (body) =>\n  realRequest('/mobile/affairs/leave', { method: 'POST', data: body || {} })",
        "miniapp leave apply",
    )
    write(p, s)

    p = "miniapp/src/services/studentApi.js"
    s = read(p)
    s = replace_once(
        s,
        "  getMyLeaves: () => real.affairsLeaveMy(),\n",
        "  getMyLeaves: () => real.affairsLeaveMy(),\n  applyLeave: (body) => real.affairsLeaveApply(body),\n",
        "studentApi applyLeave",
    )
    write(p, s)

    p = "miniapp/src/pages/student/affairs/leave.vue"
    s = read(p)
    s = replace_once(
        s,
        "studentApi.submitServiceApply({ serviceKey: 'LEAVE', ...payload })",
        "studentApi.applyLeave(payload)",
        "miniapp legacy leave call",
    )
    write(p, s)

    p = "frontend/src/config/navPlan.js"
    s = read(p)
    for old, new in {
        "'/admin/campus-service/leave'": "'/admin/student-affairs/leave'",
        "'/admin/campus-service/leave-extensions'": "'/admin/student-affairs/leave/followup'",
        "'/admin/campus-service/leave-ledger'": "'/admin/student-affairs/leave/ledger'",
        "'/admin/campus-service/leave-stats'": "'/admin/student-affairs/leave/stats'",
    }.items():
        if old not in s and new not in s:
            raise RuntimeError(f"missing nav path: {old}")
        s = s.replace(old, new)
    write(p, s)

    p = "frontend/src/config/adminMenu.js"
    s = read(p)
    s = s.replace(
        "path: '/admin/campus-service', label: '学工中心 / 在校服务'",
        "path: '/admin/student-affairs/leave', label: '学工中心 / 请假销假'",
    )
    write(p, s)

    p = "backend/app/api/v1/campus_service.py"
    s = read(p)
    s, count = re.subn(
        r"\n# 请假\n.*?\n# 资助\n",
        "\n# 请假旧接口已退出；正式接口统一为 /student-affairs/leave/*。\n\n# 资助\n",
        s,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError("failed to remove legacy campus leave routes")
    write(p, s)

    p = "backend/app/services/campus_service_service.py"
    s = read(p)
    replacement = """
# ═══ 请假旧实现已退出 ═══
# 请假唯一实现：app.services.affairs_leave_service。历史 CsLeave 数据仍保留。

def _parse_versioned_item(raw):
    if isinstance(raw, dict):
        return raw.get("id"), raw.get("version")
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return raw[0], raw[1]
    return raw, None


# ═══ 资助 ═══
"""
    s, count = re.subn(
        r"\n# ═══ 请假 ═══\n.*?\n# ═══ 资助 ═══\n",
        replacement,
        s,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError("failed to remove legacy campus leave service")
    s = re.sub(
        r"\n\s*leaves = db\.scalars\(select\(CsLeave\).*?\.all\(\)\n",
        "\n",
        s,
        count=1,
        flags=re.S,
    )
    s = s.replace('                "leaves": [_leave_row(x, s) for x in leaves],\n', "")
    write(p, s)


def second_cut() -> None:
    for path in (
        "backend/affairs_test_compat.py",
        "backend/affairs_test_diagnostics.py",
        "backend/affairs_test_legacy_inputs.py",
    ):
        Path(path).unlink(missing_ok=True)
    p = "backend/pytest.ini"
    lines = [line for line in read(p).splitlines() if not line.strip().startswith("addopts =")]
    write(p, "\n".join(lines).rstrip() + "\n")


def third_cut() -> None:
    p = "backend/app/services/affairs_leave_service.py"
    s = read(p)
    if "def _allowed_actions(" not in s:
        anchor = "def _row(x, s=None) -> dict:\n"
        helper = '''def _allowed_actions(status: str | None) -> list[str]:
    state = str(status or "")
    if state in _REVIEW_NODES:
        return ["APPROVE", "RETURN", "REJECT"]
    if state == "APPROVED":
        return ["SUBMIT_CANCEL", "SUBMIT_EXTENSION", "PROXY_CANCEL"]
    if state == "WAIT_CANCEL_LEAVE":
        return ["CONFIRM_CANCEL", "RETURN_CANCEL"]
    if state == "EXTENSION_REVIEW":
        return ["APPROVE_EXTENSION", "REJECT_EXTENSION"]
    if state == "OVERDUE":
        return ["SUBMIT_CANCEL", "SUBMIT_EXTENSION", "HANDLE_OVERDUE"]
    if state == "RETURNED":
        return ["EDIT_RETURNED", "RESUBMIT"]
    return []


'''
        s = replace_once(s, anchor, helper + anchor, "leave row helper")
    if '"allowedActions": _allowed_actions(x.affairs_status),' not in s:
        s = replace_once(
            s,
            '        "id": str(x.id), "studentId": str(x.student_id or ""),\n',
            '        "id": str(x.id), "studentId": str(x.student_id or ""),\n        "version": int(x.version or 0), "allowedActions": _allowed_actions(x.affairs_status),\n',
            "formal leave dto",
        )
    write(p, s)

    p = "backend/app/services/mobile_affairs_service.py"
    s = read(p)
    old = '''                "reason": x.reason or "",
                "returnReason": getattr(x, "return_reason", None) or "",
                "canResubmit": (x.affairs_status or "") == "RETURNED",
                "canCancel": (x.affairs_status or "") in ("APPROVED", "OVERDUE"),
                "canExtend": (x.affairs_status or "") in ("APPROVED", "OVERDUE"),
'''
    new = '''                "reason": x.reason or "",
                "returnReason": getattr(x, "return_reason", None) or "",
                "version": int(x.version or 0),
                "allowedActions": actions := (
                    ["EDIT_RETURNED", "RESUBMIT"] if (x.affairs_status or "") == "RETURNED" else
                    (["SUBMIT_CANCEL", "SUBMIT_EXTENSION"] if (x.affairs_status or "") in ("APPROVED", "OVERDUE") else [])
                ),
                "canResubmit": "RESUBMIT" in actions,
                "canCancel": "SUBMIT_CANCEL" in actions,
                "canExtend": "SUBMIT_EXTENSION" in actions,
'''
    s = replace_once(s, old, new, "mobile leave dto")
    write(p, s)

    p = "backend/app/services/affairs_four_end_contract.py"
    s = read(p)
    s = re.sub(
        r"\ndef _patch_core_rows\(\) -> None:.*?\n\ndef _patch_student_views\(\) -> None:",
        "\n\ndef _patch_student_views() -> None:",
        s,
        count=1,
        flags=re.S,
    )
    s = s.replace("    original_leave_my = aff.leave_my\n", "")
    s = s.replace('        "leave_my": original_leave_my,\n', "")
    s = re.sub(
        r"\n    def leave_my\(user\):.*?\n    def aid_my\(user\):",
        "\n    def aid_my(user):",
        s,
        count=1,
        flags=re.S,
    )
    s = s.replace("    aff.leave_my = leave_my\n", "")
    s = s.replace("    _patch_core_rows()\n", "")
    write(p, s)


def audit() -> None:
    roots = {
        "student-portal/src": ["serviceKey: 'LEAVE'", "/campus-service/leaves"],
        "miniapp/src": ["serviceKey: 'LEAVE'", "/campus-service/leaves"],
    }
    for root, needles in roots.items():
        for file in Path(root).rglob("*"):
            if not file.is_file() or file.suffix not in {".js", ".vue", ".ts"}:
                continue
            text = file.read_text(encoding="utf-8", errors="ignore")
            for needle in needles:
                if needle in text:
                    raise RuntimeError(f"legacy leave call remains: {file}: {needle}")
    for path in (
        "backend/affairs_test_compat.py",
        "backend/affairs_test_diagnostics.py",
        "backend/affairs_test_legacy_inputs.py",
    ):
        if Path(path).exists():
            raise RuntimeError(f"fake test adapter remains: {path}")


if __name__ == "__main__":
    first_cut()
    second_cut()
    third_cut()
    audit()
    print("leave cutover audit passed")
