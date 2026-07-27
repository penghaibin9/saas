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


def repair_generated_mobile_syntax() -> None:
    path = Path("backend/app/services/mobile_affairs_service.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '                "allowedActions": actions := (\n',
        '                "allowedActions": (actions := (\n',
        1,
    )
    text = text.replace(
        '                ),\n                "canResubmit": "RESUBMIT" in actions,\n',
        '                )),\n                "canResubmit": "RESUBMIT" in actions,\n',
        1,
    )
    path.write_text(text, encoding="utf-8")


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

    mobile = Path("backend/app/services/mobile_affairs_service.py").read_text(encoding="utf-8")
    if '"allowedActions": (actions := (' not in mobile:
        raise RuntimeError("mobile leave allowedActions syntax was not repaired")


if __name__ == "__main__":
    print("CUTOVER_STAGE first_cut", flush=True)
    base.first_cut()
    patch_remaining_callers()
    print("CUTOVER_STAGE second_cut", flush=True)
    base.second_cut()
    print("CUTOVER_STAGE third_cut", flush=True)
    base.third_cut()
    repair_generated_mobile_syntax()
    print("CUTOVER_STAGE audit", flush=True)
    base.audit()
    audit_versions()
    print("leave cutover follow-up audit passed", flush=True)
