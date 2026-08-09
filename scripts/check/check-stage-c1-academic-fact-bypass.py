#!/usr/bin/env python3
"""Stage C1/C2/C3 static gate: academic facts, historical consumers and immutable history.

The scanner checks production ``backend/app`` for direct writes to current academic
projection fields. Compatibility implementations may remain importable only when a
formal facade boundary is asserted below; otherwise they are not exempt.

Stage C2 proves selection eligibility, historical program resolution and transcript
identity cross the ``StudentAcademicFact`` boundary. Stage C3 proves student graduation
progress and formal precheck share one read-only evaluator, formal graduation/archive
history is append-only, post-archive correction is operator-accessible, and ordinary
ARCHIVED -> mutable-state rollback cannot reappear.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
ACADEMIC_FIELDS = {"student_status", "college_id", "major_id", "class_id", "grade"}
ALLOW_DIRECT_FILES = {
    "backend/app/modules/academic_affairs/services/academic_affairs_student_fact_service.py",
}
NONFORMAL_LEGACY_FILES = {
    "backend/app/modules/academic_affairs/services/academic_affairs_major_split_service.py",
    "backend/app/modules/academic_affairs/services/academic_affairs_org_service.py",
}
PROFILE_HELPER_CALLS = {"_get_profile", "resolve_student", "_student_profile"}


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def contains_student_profile(node: ast.AST | None) -> bool:
    return bool(node) and any(isinstance(item, ast.Name) and item.id == "StudentProfile" for item in ast.walk(node))


def is_known_profile_load(value: ast.AST, tracked: set[str]) -> bool:
    if contains_student_profile(value) and not (
        isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "StudentProfile"
    ):
        return True
    if isinstance(value, ast.Name) and value.id in tracked:
        return True
    if isinstance(value, ast.Call):
        func = value.func
        if isinstance(func, ast.Name) and func.id in PROFILE_HELPER_CALLS:
            return True
        if isinstance(func, ast.Attribute) and func.attr in PROFILE_HELPER_CALLS:
            return True
    return False


def infer_loaded_profile_vars(tree: ast.AST) -> set[str]:
    tracked: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Name) and is_known_profile_load(node.value, tracked) and target.id not in tracked:
                tracked.add(target.id)
                changed = True
    return tracked


def enclosing_function_lines(tree: ast.AST, function_name: str) -> tuple[int, int] | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return int(node.lineno), int(getattr(node, "end_lineno", node.lineno))
    return None


def _legacy_dead_code_line(relative: str, tree: ast.AST, line: int) -> bool:
    if relative != "backend/app/services/db_service.py":
        return False
    bounds = enclosing_function_lines(tree, "void_student")
    return bool(bounds and bounds[0] <= line <= bounds[1])


def scan_update_calls(tree: ast.AST, relative: str) -> list[str]:
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "update":
            continue
        if not contains_student_profile(node):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Dict):
                continue
            for key in child.keys:
                if isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name):
                    if key.value.id == "StudentProfile" and key.attr in ACADEMIC_FIELDS:
                        line = int(getattr(key, "lineno", node.lineno))
                        if not _legacy_dead_code_line(relative, tree, line):
                            violations.append(
                                f"{relative}:{line}: StudentProfile.{key.attr} direct update mapping"
                            )
    return violations


def scan_file(path: pathlib.Path) -> list[str]:
    relative = rel(path)
    if relative in ALLOW_DIRECT_FILES or relative in NONFORMAL_LEGACY_FILES:
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    except (UnicodeDecodeError, SyntaxError) as exc:
        return [f"{relative}: parse error: {exc}"]

    tracked = infer_loaded_profile_vars(tree)
    violations = scan_update_calls(tree, relative)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id in tracked and target.attr in ACADEMIC_FIELDS:
                        line = int(getattr(target, "lineno", 0) or 0)
                        if not _legacy_dead_code_line(relative, tree, line):
                            violations.append(
                                f"{relative}:{line or '?'}: direct {target.value.id}.{target.attr} write"
                            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
            if len(node.args) >= 2 and isinstance(node.args[0], ast.Name) and node.args[0].id in tracked:
                field = node.args[1].value if isinstance(node.args[1], ast.Constant) else None
                if field in ACADEMIC_FIELDS and not _legacy_dead_code_line(relative, tree, int(node.lineno)):
                    violations.append(f"{relative}:{node.lineno}: setattr({node.args[0].id}, {field}) bypass")
    return sorted(set(violations))


def formal_boundary_assertions() -> list[str]:
    service_dir = APP / "modules/academic_affairs/services"
    router_dir = APP / "modules/academic_affairs/routers"
    major_public = (service_dir / "academic_affairs_major_split_public_service.py").read_text(encoding="utf-8")
    org_public = (service_dir / "academic_affairs_org_fact_facade.py").read_text(encoding="utf-8")
    selection_final = (service_dir / "academic_affairs_selection_final_service.py").read_text(encoding="utf-8")
    program_resolver = (service_dir / "student_program_resolution_service.py").read_text(encoding="utf-8")
    transcript_history = (service_dir / "academic_affairs_transcript_historical_facade.py").read_text(encoding="utf-8")
    services_init = (service_dir / "__init__.py").read_text(encoding="utf-8")
    student_service = (APP / "services/student_service.py").read_text(encoding="utf-8")
    lifecycle = (APP / "services/student_academic_lifecycle_service.py").read_text(encoding="utf-8")
    graduation_immutable = (service_dir / "academic_affairs_graduation_immutable_service.py").read_text(encoding="utf-8")
    mobile_public = (service_dir / "mobile_academic_affairs_public_service.py").read_text(encoding="utf-8")
    archive_manifest = (service_dir / "academic_affairs_archive_manifest_service.py").read_text(encoding="utf-8")
    archive_guard = (service_dir / "academic_affairs_archive_immutable_guard.py").read_text(encoding="utf-8")
    archive_correction_router = (router_dir / "archive_correction_router.py").read_text(encoding="utf-8")
    router_bundle = (router_dir / "academic_affairs_bundle.py").read_text(encoding="utf-8")
    stage_c3_models = (APP / "models/academic_affairs_stage_c3.py").read_text(encoding="utf-8")
    archive_view = (
        ROOT / "frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue"
    ).read_text(encoding="utf-8")
    errors = []

    # Stage C1: one formal current-academic write path.
    if "def confirm(user, batch_id)" not in major_public or "append_student_academic_fact" not in major_public:
        errors.append("formal major-split confirm is not the Stage C1 AcademicFact override")
    if "academic_affairs_major_split_public_service as academic_affairs_major_split_service" not in services_init:
        errors.append("services package no longer binds formal major-split to public facade")
    if "def adjust_student_class(user, body)" not in org_public or "append_student_academic_fact" not in org_public:
        errors.append("formal class adjustment is not the Stage C1 AcademicFact override")
    if "academic_affairs_org_fact_facade as academic_affairs_org_service" not in services_init:
        errors.append("services package no longer binds formal org service to AcademicFact facade")
    if "db_service.void_student" in student_service:
        errors.append("formal student_service still calls legacy db_service.void_student direct-write")
    if "student_academic_lifecycle_service" not in student_service or "append_student_academic_fact" not in lifecycle:
        errors.append("formal student void is not bound to the Stage C1 AcademicFact lifecycle service")

    # Stage C2: formal consumers cross AcademicFact/as_of boundaries.
    if "academic_affairs_selection_final_service as academic_affairs_selection_service" not in services_init:
        errors.append("services package no longer binds formal selection to final facade")
    if "def _selection_academic_identity" not in selection_final or "resolve_student_academic_fact" not in selection_final:
        errors.append("formal selection facade no longer resolves StudentAcademicFact eligibility identity")
    if "academic_identity," not in selection_final or "_base._validate_enroll(" not in selection_final:
        errors.append("formal selection validation is no longer fed by the AcademicFact identity proxy")
    if "academicFactId=" not in selection_final or "selectionEffectiveAt=" not in selection_final:
        errors.append("formal selection audit no longer records the AcademicFact decision provenance")
    if "def resolve_student_program_at" not in program_resolver or "resolve_student_academic_fact" not in program_resolver:
        errors.append("historical program resolver no longer consumes StudentAcademicFact(as_of)")
    if "ACADEMIC_FACT_MISSING" not in program_resolver:
        errors.append("historical program resolver no longer fails closed when AcademicFact is missing")
    if "if as_of is not None:" not in program_resolver or "resolve_student_program_at(" not in program_resolver:
        errors.append("credit requirement historical path no longer uses the AcademicFact program resolver")
    if "academic_affairs_transcript_historical_facade.install()" not in services_init:
        errors.append("formal transcript no longer installs Stage C2 historical identity facade")
    if "resolve_student_academic_fact" not in transcript_history or "as_of=term.start_date" not in transcript_history:
        errors.append("historical transcript identity no longer resolves AcademicFact at term.start_date")
    if "NO_IMPLICIT_CURRENT_PROFILE" not in transcript_history:
        errors.append("cumulative transcript can again imply today's academic identity as historical header")

    # Stage C3: one read-only evaluator feeds both student progress and formal immutable runs.
    for model_name in (
        "class GraduationEvaluationRun",
        "class GraduationDecisionFact",
        "class ArchiveManifest",
        "class PostArchiveCorrectionCase",
    ):
        if model_name not in stage_c3_models:
            errors.append(f"Stage C3 immutable model missing: {model_name}")
    if "academic_affairs_graduation_immutable_service.install()" not in services_init:
        errors.append("formal graduation service no longer installs Stage C3 immutable evaluator")
    if "def _strict_overall" not in graduation_immutable or "all(" not in graduation_immutable:
        errors.append("formal graduation evaluator no longer fails closed on UNKNOWN/non-PASS evidence")
    if "GraduationEvaluationRun(" not in graduation_immutable or "run_no=run_no" not in graduation_immutable:
        errors.append("formal graduation precheck no longer appends immutable Run#N")
    if "formalRunCreated\": False" not in graduation_immutable:
        errors.append("graduation preview no longer explicitly proves it creates no formal run")
    if "GraduationDecisionFact(" not in graduation_immutable or "evaluation_run_id=run.id" not in graduation_immutable:
        errors.append("formal graduation decision no longer references immutable evaluation_run_id")
    if "def graduation_progress_my" not in mobile_public or "graduation.evaluate_student" not in mobile_public:
        errors.append("student PC/miniapp graduation progress no longer uses the shared read-only evaluator")
    if "json.loads(" in mobile_public and "item_results_json" in mobile_public:
        errors.append("student graduation progress reverted to mutable AaGraduationAuditResult item projection")
    if '"formalRunCreated": False' not in mobile_public:
        errors.append("student graduation refresh no longer asserts read-only/no-formal-run semantics")

    # Stage C3: permanent archive + versioned correction chain + usable controlled API.
    if "academic_affairs_archive_manifest_service.install()" not in services_init:
        errors.append("formal archive service no longer installs immutable manifest service")
    if "academic_affairs_archive_immutable_guard.install(academic_affairs_archive_service)" not in services_init:
        errors.append("formal archive service no longer blocks ordinary ARCHIVED unfreeze")
    if "TERM_ARCHIVED" not in archive_guard or "reject_archive_unfreeze" not in archive_guard:
        errors.append("ARCHIVED -> mutable-state rollback guard is missing")
    if "ArchiveManifest(" not in archive_manifest or "supersedes_id=previous.id" not in archive_manifest:
        errors.append("archive correction no longer appends a superseding manifest version")
    if '_CORRECTION_TYPES = {"GRADE", "GRADUATION"}' not in archive_manifest:
        errors.append("post-archive correction scope is no longer limited to GRADE/GRADUATION")
    if "case.created_by" not in archive_manifest or "second approval" not in archive_manifest.lower():
        errors.append("post-archive correction no longer enforces a distinct second approver")
    if '"archive_correction_router"' not in router_bundle:
        errors.append("post-archive correction router is no longer registered in public academic bundle")
    for required_path in (
        "/batches/{batch_id}/manifest/verify",
        "/batches/{batch_id}/corrections",
        "/corrections/{case_id}/approve",
    ):
        if required_path not in archive_correction_router:
            errors.append(f"post-archive correction API missing: {required_path}")
    if 'require_permission("academicAffairs.archive.manage")' not in archive_correction_router:
        errors.append("post-archive correction API lost archive.manage permission guard")
    for forbidden in ("api.unfreeze", "doUnfreeze", "特批解冻"):
        if forbidden in archive_view:
            errors.append(f"archive console resurrected ordinary unfreeze UI: {forbidden}")
    return errors


def main() -> int:
    violations = []
    for path in sorted(APP.rglob("*.py")):
        violations.extend(scan_file(path))
    violations.extend(formal_boundary_assertions())
    if violations:
        print("Stage C1/C2/C3 governance gate FAILED:")
        for item in violations:
            print(f"::error::{item}")
        return 1
    print(
        "Stage C1/C2/C3 governance gate OK: Profile academic direct-writes=0; "
        "selection/program/transcript history is fact-bound; student/formal graduation share one evaluator; "
        "archive history is immutable and correction uses controlled V2+ API"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
