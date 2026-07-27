from __future__ import annotations

from pathlib import Path
import re


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


def validate_first_cut() -> None:
    campus_api = Path("backend/app/api/v1/campus_service.py").read_text(encoding="utf-8")
    campus_service = Path("backend/app/services/campus_service_service.py").read_text(encoding="utf-8")
    if "请假旧接口已退出" not in campus_api:
        raise RuntimeError("legacy campus-service leave API block is not retired")
    if any(route in campus_api for route in ('@router.get("/leaves', '@router.post("/leaves')):
        raise RuntimeError("legacy /campus-service/leaves routes still exist")
    if "请假旧实现已退出" not in campus_service:
        raise RuntimeError("legacy campus-service leave service block is not retired")
    patch_remaining_callers()


def remove_fake_test_adapters() -> None:
    for path in (
        "backend/affairs_test_compat.py",
        "backend/affairs_test_diagnostics.py",
        "backend/affairs_test_legacy_inputs.py",
    ):
        Path(path).unlink(missing_ok=True)
    pytest_path = Path("backend/pytest.ini")
    text = pytest_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.strip().startswith("addopts =")]
    pytest_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    final = pytest_path.read_text(encoding="utf-8")
    if any(name in final for name in ("affairs_test_compat", "affairs_test_diagnostics", "affairs_test_legacy_inputs")):
        raise RuntimeError("pytest fake compatibility plugin remains enabled")


def validate_third_cut() -> None:
    leave_text = Path("backend/app/services/affairs_leave_service.py").read_text(encoding="utf-8")
    mobile_text = Path("backend/app/services/mobile_affairs_service.py").read_text(encoding="utf-8")
    contract_text = Path("backend/app/services/affairs_four_end_contract.py").read_text(encoding="utf-8")
    required = {
        "formal leave allowedActions": "def _allowed_actions(" in leave_text,
        "formal leave version": '"version": int(x.version or 0)' in leave_text,
        "formal leave DTO actions": '"allowedActions": _allowed_actions(x.affairs_status)' in leave_text,
        "mobile leave service import": "from app.services import affairs_leave_service as leave_svc" in mobile_text,
        "mobile leave actions": "actions = leave_svc._allowed_actions(x.affairs_status)" in mobile_text,
        "mobile leave version": '"version": int(x.version or 0)' in mobile_text,
        "mobile leave DTO actions": '"allowedActions": actions' in mobile_text,
        "no core row monkey patch": "def _patch_core_rows" not in contract_text,
        "no leave_my monkey patch capture": "original_leave_my" not in contract_text,
        "no leave_my monkey patch assignment": "aff.leave_my = leave_my" not in contract_text,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        raise RuntimeError("leave runtime patch absorption is incomplete: " + ", ".join(missing))


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


def collect_legacy_hits() -> list[str]:
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
    roots = [
        Path("backend/app"), Path("backend/tests"), Path("frontend/src"), Path("frontend/tests"),
        Path("student-portal/src"), Path("miniapp/src"),
    ]
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
    return hits


def audit_all() -> None:
    audit_versions()
    hits = collect_legacy_hits()
    Path("leave-test-audit.txt").write_text("\n".join(hits) + ("\n" if hits else ""), encoding="utf-8")
    if hits:
        raise RuntimeError("legacy leave production/test contracts remain:\n" + "\n".join(hits[:200]))


if __name__ == "__main__":
    print("CUTOVER_STAGE first_cut", flush=True)
    validate_first_cut()
    print("CUTOVER_STAGE second_cut", flush=True)
    remove_fake_test_adapters()
    print("CUTOVER_STAGE third_cut", flush=True)
    validate_third_cut()
    print("CUTOVER_STAGE audit", flush=True)
    audit_all()
    print("leave cutover follow-up audit passed", flush=True)
