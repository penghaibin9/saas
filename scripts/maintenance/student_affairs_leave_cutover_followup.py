from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re


def _load_base():
    script = Path(__file__).with_name("student_affairs_leave_cutover.py")
    spec = spec_from_file_location("student_affairs_leave_cutover", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载施工脚本：{script}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_base()


def patch_remaining_callers() -> None:
    for path in Path("student-portal/src").rglob("*.vue"):
        text = path.read_text(encoding="utf-8")
        updated = re.sub(
            r"portalApi\.affairsServiceApply\(\{\s*serviceKey:\s*['\"]LEAVE['\"]\s*,\s*(.*?)\}\)",
            r"portalApi.affairsLeaveApply({\1})",
            text,
            flags=re.S,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")

    affairs_view = Path("student-portal/src/views/affairs/AffairsView.vue")
    if affairs_view.exists():
        text = affairs_view.read_text(encoding="utf-8")
        text = text.replace(
            "await portalApi.affairsLeaveResubmit(leaveId, { reason: lv.reason || leaveForm.reason || '' })",
            "await portalApi.affairsLeaveResubmit(leaveId, { reason: lv.reason || leaveForm.reason || '', version: lv.version })",
        )
        text = text.replace(
            "await portalApi.affairsLeaveCancel(leaveId, { proofNote: '学生本人申请销假' })",
            "await portalApi.affairsLeaveCancel(leaveId, { proofNote: '学生本人申请销假', version: lv.version })",
        )
        text = text.replace(
            "      newEndTime: extendForm.newEndTime,\n      reason: extendForm.reason.trim()\n",
            "      newEndTime: extendForm.newEndTime,\n      reason: extendForm.reason.trim(),\n      version: lv.version\n",
        )
        affairs_view.write_text(text, encoding="utf-8")

    for path in Path("miniapp/src").rglob("*.vue"):
        text = path.read_text(encoding="utf-8")
        updated = re.sub(
            r"studentApi\.submitServiceApply\(\{\s*serviceKey:\s*['\"]LEAVE['\"]\s*,\s*(.*?)\}\)",
            r"studentApi.applyLeave({\1})",
            text,
            flags=re.S,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def first_cut_rerunnable() -> None:
    campus_api = Path("backend/app/api/v1/campus_service.py").read_text(encoding="utf-8")
    campus_service = Path("backend/app/services/campus_service_service.py").read_text(encoding="utf-8")
    already_cut = (
        "请假旧接口已退出" in campus_api
        and "请假旧实现已退出" in campus_service
    )
    if not already_cut:
        base.first_cut()
    patch_remaining_callers()


def second_cut_rerunnable() -> None:
    base.second_cut()
    pytest_ini = Path("backend/pytest.ini").read_text(encoding="utf-8")
    if "affairs_test_compat" in pytest_ini or "affairs_test_diagnostics" in pytest_ini:
        raise RuntimeError("pytest fake compatibility plugin remains enabled")


def third_cut_rerunnable() -> None:
    leave_text = Path("backend/app/services/affairs_leave_service.py").read_text(encoding="utf-8")
    mobile_text = Path("backend/app/services/mobile_affairs_service.py").read_text(encoding="utf-8")
    contract_text = Path("backend/app/services/affairs_four_end_contract.py").read_text(encoding="utf-8")

    leave_terminal = (
        "def _allowed_actions(" in leave_text
        and '"version": int(x.version or 0)' in leave_text
        and '"allowedActions": _allowed_actions(x.affairs_status)' in leave_text
    )
    mobile_terminal = (
        "from app.services import affairs_leave_service as leave_svc" in mobile_text
        and "actions = leave_svc._allowed_actions(x.affairs_status)" in mobile_text
        and '"version": int(x.version or 0)' in mobile_text
        and '"allowedActions": actions' in mobile_text
    )
    contract_terminal = (
        "def _patch_core_rows" not in contract_text
        and "original_leave_my" not in contract_text
        and "aff.leave_my = leave_my" not in contract_text
    )

    if not (leave_terminal and mobile_terminal and contract_terminal):
        base.third_cut()

    leave_text = Path("backend/app/services/affairs_leave_service.py").read_text(encoding="utf-8")
    mobile_text = Path("backend/app/services/mobile_affairs_service.py").read_text(encoding="utf-8")
    contract_text = Path("backend/app/services/affairs_four_end_contract.py").read_text(encoding="utf-8")
    if not (
        "def _allowed_actions(" in leave_text
        and '"version": int(x.version or 0)' in leave_text
        and '"allowedActions": _allowed_actions(x.affairs_status)' in leave_text
        and "actions = leave_svc._allowed_actions(x.affairs_status)" in mobile_text
        and '"allowedActions": actions' in mobile_text
        and "def _patch_core_rows" not in contract_text
        and "original_leave_my" not in contract_text
    ):
        raise RuntimeError("leave runtime patch absorption is incomplete")


def audit_versions() -> None:
    path = Path("student-portal/src/views/affairs/AffairsView.vue")
    if path.exists():
        text = path.read_text(encoding="utf-8")
        required = (
            "affairsLeaveApply({",
            "affairsLeaveResubmit(leaveId, { reason: lv.reason || leaveForm.reason || '', version: lv.version })",
            "affairsLeaveCancel(leaveId, { proofNote: '学生本人申请销假', version: lv.version })",
            "version: lv.version",
        )
        for needle in required:
            if needle not in text:
                raise RuntimeError(f"student portal leave version contract missing: {needle}")


def audit_test_contracts() -> None:
    forbidden = (
        "/campus-service/leaves",
        "serviceKey: 'LEAVE'",
        'serviceKey: "LEAVE"',
        "/admin/campus-service/leave",
        "affairs_test_compat",
        "affairs_test_diagnostics",
        "affairs_test_legacy_inputs",
    )
    hits: list[str] = []
    roots = [Path("backend/tests"), Path("frontend/tests"), Path("student-portal/src"), Path("miniapp/src")]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".js", ".mjs", ".ts", ".vue"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in forbidden:
                if needle in text:
                    hits.append(f"{path}: {needle}")
    Path("leave-test-audit.txt").write_text("\n".join(hits) + ("\n" if hits else ""), encoding="utf-8")
    if hits:
        raise RuntimeError("legacy leave test/caller contracts remain:\n" + "\n".join(hits[:100]))


if __name__ == "__main__":
    print("CUTOVER_STAGE first_cut", flush=True)
    first_cut_rerunnable()
    print("CUTOVER_STAGE second_cut", flush=True)
    second_cut_rerunnable()
    print("CUTOVER_STAGE third_cut", flush=True)
    third_cut_rerunnable()
    print("CUTOVER_STAGE audit", flush=True)
    base.audit()
    audit_versions()
    audit_test_contracts()
    print("leave cutover follow-up audit passed", flush=True)
