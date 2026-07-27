from __future__ import annotations

from pathlib import Path
import re

from scripts.maintenance import student_affairs_leave_cutover as base


def patch_remaining_callers() -> None:
    for path in Path("student-portal/src").rglob("*.vue"):
        text = path.read_text(encoding="utf-8")
        updated = re.sub(
            r"portalApi\.affairsServiceApply\(\{\s*serviceKey:\s*['\"]LEAVE['\"]\s*,\s*\.\.\.([^}]+)\}\)",
            r"portalApi.affairsLeaveApply({ ...\1 })",
            text,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")

    for path in Path("miniapp/src").rglob("*.vue"):
        text = path.read_text(encoding="utf-8")
        updated = re.sub(
            r"studentApi\.submitServiceApply\(\{\s*serviceKey:\s*['\"]LEAVE['\"]\s*,\s*\.\.\.([^}]+)\}\)",
            r"studentApi.applyLeave(\1)",
            text,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    print("CUTOVER_STAGE first_cut", flush=True)
    base.first_cut()
    patch_remaining_callers()
    print("CUTOVER_STAGE second_cut", flush=True)
    base.second_cut()
    print("CUTOVER_STAGE third_cut", flush=True)
    base.third_cut()
    print("CUTOVER_STAGE audit", flush=True)
    base.audit()
    print("leave cutover follow-up audit passed", flush=True)
