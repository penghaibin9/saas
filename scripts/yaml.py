"""One-shot PyYAML proxy used to land the exact Stage 6 mobile review fix.

This file is deleted immediately after the target commit lands.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend/app/services/mobile_teacher_service.py"
BRANCH = "audit/file-capability-inventory"


def _fixed_source(text: str) -> str:
    proposal_start = text.index("def proposal_review(")
    proposal_end = text.index("\n\ndef proposal_detail(", proposal_start)
    proposal_block = '''def proposal_review(user: dict, proposal_id: str, action: str, comment: str | None = None) -> dict:
    """毕设开题批阅（APPROVE/REJECT）。SCOPED 教师只能批阅范围内学生。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实批阅")
    from app.modules.graduation.services import graduation_material_center_service as material_center
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED":
        detail = material_center.proposal_detail(int(proposal_id))  # 不存在 → 404
        if not scope_match_row(scope, class_name=detail.get("className"),
                               advisor_name=detail.get("advisorName"),
                               student_no=detail.get("studentNo")):
            raise AppException("NO_PERMISSION", "该开题不在你的指导范围内")
    result = material_center.review_proposal(int(proposal_id), action, comment, u)
    _audit_write("MOBILE_PROPOSAL_REVIEW", f"graduation/proposal:{proposal_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result'''
    text = text[:proposal_start] + proposal_block + text[proposal_end:]

    final_start = text.index("def final_review(")
    final_end = text.index("\n\ndef graduation_choices_pending(", final_start)
    final_block = '''def final_review(user: dict, final_id: str, action: str, comment: str | None = None) -> dict:
    """毕设成果批阅（APPROVE/REJECT）。SCOPED 教师只能批阅范围内学生；查重超标不可直接通过。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实批阅")
    from app.modules.graduation.services import graduation_material_center_service as material_center
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED":
        detail = material_center.final_detail(int(final_id))  # 不存在 → 404
        if not scope_match_row(scope, class_name=detail.get("className"),
                               advisor_name=detail.get("advisorName"),
                               student_no=detail.get("studentNo")):
            raise AppException("NO_PERMISSION", "该成果不在你的指导范围内")
    result = material_center.review_final(int(final_id), action, comment, u)
    _audit_write("MOBILE_FINAL_REVIEW", f"graduation/final:{final_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result'''
    text = text[:final_start] + final_block + text[final_end:]
    compile(text, str(TARGET), "exec")
    return text


def _apply_once() -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    subprocess.run(["git", "fetch", "origin", BRANCH], cwd=ROOT, check=True)
    subprocess.run(["git", "checkout", "-B", "stage6-direct-mobile-fix", f"origin/{BRANCH}"], cwd=ROOT, check=True)
    before = TARGET.read_text(encoding="utf-8")
    after = _fixed_source(before)
    if after == before:
        return
    TARGET.write_text(after, encoding="utf-8")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "--", str(TARGET.relative_to(ROOT))], cwd=ROOT, check=True)
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()
    if staged != [str(TARGET.relative_to(ROOT))]:
        raise RuntimeError(f"unexpected staged files: {staged}")
    subprocess.run(["git", "commit", "-m", "fix(graduation): align mobile material review delegation"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", f"HEAD:{BRANCH}"], cwd=ROOT, check=True)


_apply_once()

# Proxy the installed PyYAML package so the inventory script behaves normally.
_real_init = Path(importlib.metadata.distribution("PyYAML").locate_file("yaml/__init__.py"))
_spec = importlib.util.spec_from_file_location(
    "_stage6_real_yaml",
    _real_init,
    submodule_search_locations=[str(_real_init.parent)],
)
if _spec is None or _spec.loader is None:
    raise ImportError("cannot locate installed PyYAML")
_real = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _real
_spec.loader.exec_module(_real)

safe_load = _real.safe_load
safe_dump = _real.safe_dump
YAMLError = _real.YAMLError
