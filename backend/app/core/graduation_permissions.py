"""毕业设计中心动作级权限目录与请求依赖。

新接口按 FastAPI endpoint 名称显式登记，不再从 URL 猜动作。旧 URL 映射仅供
尚未迁移的 GET/HEAD 兼容；任何未登记写请求一律 fail-closed。
"""
from __future__ import annotations

from fastapi import Depends, Request

from app.core.exceptions import no_permission
from app.core.permissions import enforce_permission
from app.core.security import get_current_user


GRADUATION_PERMISSION_CODES = frozenset({
    "graduationDesign.dashboard.view",
    *{f"graduationDesign.batch.{x}" for x in ("view", "create", "update", "start", "close", "archive")},
    *{f"graduationDesign.student.{x}" for x in ("view", "import", "export", "manage")},
    *{f"graduationDesign.topic.{x}" for x in ("view", "create", "review", "assign", "match", "export")},
    *{f"graduationDesign.taskbook.{x}" for x in ("view", "issue", "update", "confirmOnBehalf", "export")},
    *{f"graduationDesign.proposal.{x}" for x in ("view", "review", "defense", "remind", "export")},
    *{f"graduationDesign.guidance.{x}" for x in ("view", "create", "update")},
    "graduationDesign.guide.manage",
    "graduationDesign.midterm.review",
    *{f"graduationDesign.final.{x}" for x in ("view", "review", "remind", "export")},
    *{f"graduationDesign.plagiarism.{x}" for x in ("view", "start", "result", "disputeReview")},
    *{f"graduationDesign.review.{x}" for x in ("view", "assign", "submit", "return")},
    *{f"graduationDesign.defense.{x}" for x in (
        "view", "groupManage", "publish", "notify", "score", "scoreConfirm", "secondRound",
    )},
    "graduationDesign.defense.manage",
    *{f"graduationDesign.grade.{x}" for x in (
        "view", "calculate", "review", "publish", "withdraw", "appealReview",
    )},
    *{f"graduationDesign.risk.{x}" for x in ("view", "scan", "accept", "process", "close")},
    *{f"graduationDesign.archive.{x}" for x in ("view", "preview", "file", "export")},
    *{f"graduationDesign.template.{x}" for x in ("view", "manage")},
    "graduationDesign.audit.view",
})


def _group(code: str, *endpoint_names: str) -> dict[str, str]:
    if code not in GRADUATION_PERMISSION_CODES:
        raise RuntimeError(f"未注册毕业设计权限码: {code}")
    return {name: code for name in endpoint_names}


# Endpoint 名称是代码符号，重构时测试会发现缺项；不依赖 URL 文本。
GRADUATION_ENDPOINT_PERMISSIONS: dict[str, str] = {
    **_group("graduationDesign.dashboard.view", "dashboard", "gd_stats_overview", "gd_stats_college_comparison"),
    **_group("graduationDesign.batch.view", "batches", "batch_detail", "batch_stats", "batch_export"),
    **_group("graduationDesign.batch.create", "batch_create"),
    **_group("graduationDesign.batch.update", "batch_update", "batch_stages", "batch_rules", "batch_void"),
    **_group("graduationDesign.batch.start", "batch_activate"),
    **_group("graduationDesign.batch.close", "batch_close"),
    **_group("graduationDesign.batch.archive", "batch_archive"),
    **_group("graduationDesign.student.view", "students", "student_detail", "gd_students",
             "gd_student_detail", "gd_student_groups", "gd_student_stats", "get_context",
             "download_graduation_material"),
    **_group("graduationDesign.student.import", "gd_import_template", "gd_import_xlsx",
             "gd_import_dry_run", "gd_import_errors_xlsx", "gd_import_confirm"),
    **_group("graduationDesign.student.export", "gd_export"),
    **_group("graduationDesign.student.manage", "create_gd_student", "update_gd_student",
             "student_stage", "student_risk", "student_eligibility", "student_group",
             "batch_student_group", "student_defense_group", "student_grad_qual",
             "gd_mentor_stats", "gd_mentors", "gd_mentor_detail", "gd_mentor_conflicts",
             "gd_mentor_unassigned_students", "gd_mentor_assignments", "gd_mentor_evals",
             "gd_mentor_create", "gd_mentor_update", "gd_mentor_review", "gd_mentor_disable",
             "gd_mentor_enable", "gd_mentor_archive", "gd_mentor_eval_create",
             "gd_mentor_batch_archive"),
    **_group("graduationDesign.student.import", "gd_mentor_import_template", "gd_mentor_import_xlsx",
             "gd_mentor_import_dry_run", "gd_mentor_import_errors_xlsx", "gd_mentor_import_confirm"),
    **_group("graduationDesign.student.export", "gd_mentor_export"),
    **_group("graduationDesign.topic.assign", "gd_mentor_assign", "gd_mentor_change",
             "gd_mentor_assignment_cancel", "gd_mentor_batch_assign"),
    **_group("graduationDesign.topic.view", "topics", "gd_topics", "gd_topic_detail",
             "gd_topic_stats", "gd_topic_category_stats", "gd_topic_history",
             "gd_topic_assigned_students", "gd_topic_round_active", "gd_topic_rounds",
             "gd_topic_round_choices", "gd_topic_round_choices_pending",
             "gd_topic_round_capacity_conflicts", "gd_topic_round_stats",
             "gd_topic_change_requests", "gd_topic_change_request_detail"),
    **_group("graduationDesign.topic.create", "create_gd_topic", "update_gd_topic",
             "update_gd_topic_attachments", "update_gd_topic_capacity", "submit_gd_topic_review",
             "disable_gd_topic", "enable_gd_topic", "archive_gd_topic",
             "gd_topic_import_template", "gd_topic_import_xlsx", "gd_topic_import_dry_run",
             "gd_topic_import_errors_xlsx", "gd_topic_import_confirm",
             "gd_topic_choice_import_template", "gd_topic_choice_import_xlsx",
             "gd_topic_choice_import_dry_run", "gd_topic_choice_import_errors",
             "gd_topic_choice_import_confirm"),
    **_group("graduationDesign.topic.review", "review_gd_topic", "confirm_gd_topic_choice",
             "reject_gd_topic_choice", "review_gd_topic_change_request"),
    **_group("graduationDesign.topic.assign", "assign_topic", "unassign_topic", "assign_advisor",
             "submit_gd_topic_choices", "gd_topic_round_withdraw", "create_gd_topic_change_request"),
    **_group("graduationDesign.topic.match", "create_gd_topic_round", "open_gd_topic_round",
             "close_gd_topic_round", "match_gd_topic_round", "gd_topic_round_archive"),
    **_group("graduationDesign.topic.export", "gd_topic_export", "gd_topic_history_export",
             "gd_topic_rounds_export", "gd_topic_choices_export"),
    **_group("graduationDesign.taskbook.view", "gd_taskbooks", "gd_taskbook_detail", "gd_taskbook_stats"),
    **_group("graduationDesign.taskbook.issue", "gd_taskbook_issue"),
    **_group("graduationDesign.taskbook.update", "gd_taskbook_change"),
    **_group("graduationDesign.taskbook.confirmOnBehalf", "gd_taskbook_confirm"),
    **_group("graduationDesign.taskbook.export", "gd_taskbook_export", "gd_taskbook_export_pdf"),
    **_group("graduationDesign.proposal.view", "proposals", "proposal_detail", "proposal_stats"),
    **_group("graduationDesign.proposal.review", "proposal_review"),
    **_group("graduationDesign.proposal.defense", "proposal_defense"),
    **_group("graduationDesign.proposal.remind", "proposal_remind"),
    **_group("graduationDesign.proposal.export", "proposal_export"),
    **_group("graduationDesign.guidance.view", "gd_guidances", "gd_guidance_plans", "gd_guidance_stats",
             "gd_student_evals"),
    **_group("graduationDesign.guidance.create", "gd_guidance_create", "gd_guidance_plan_create",
             "gd_student_eval_create"),
    **_group("graduationDesign.guidance.update", "gd_guidance_void", "gd_guidance_plan_checkin",
             "gd_guidance_plan_cancel", "gd_student_eval_submit"),
    **_group("graduationDesign.midterm.review", "gd_midterms", "gd_midterm_detail", "gd_midterm_stats",
             "gd_midterm_check", "gd_midterm_rectify_submit", "gd_midterm_rectify_review"),
    **_group("graduationDesign.final.view", "finals", "final_stats"),
    **_group("graduationDesign.final.review", "final_review"),
    **_group("graduationDesign.final.remind", "final_remind"),
    **_group("graduationDesign.final.export", "final_export"),
    **_group("graduationDesign.plagiarism.view", "gd_plagiarism_list", "gd_plagiarism_stats"),
    **_group("graduationDesign.plagiarism.start", "gd_plagiarism_submit", "gd_plagiarism_dispute"),
    **_group("graduationDesign.plagiarism.result", "gd_plagiarism_result"),
    **_group("graduationDesign.plagiarism.disputeReview", "gd_plagiarism_dispute_review"),
    **_group("graduationDesign.review.view", "gd_review_list", "gd_review_stats"),
    **_group("graduationDesign.review.assign", "gd_review_assign"),
    **_group("graduationDesign.review.submit", "gd_review_submit"),
    **_group("graduationDesign.review.return", "gd_review_return"),
    **_group("graduationDesign.review.view", "peer_list", "peer_stats"),
    **_group("graduationDesign.review.assign", "peer_assign"),
    **_group("graduationDesign.review.submit", "peer_submit", "peer_rectify"),
    **_group("graduationDesign.defense.view", "defense_groups", "defense_detail", "defense_eligible",
             "gd_defense_score_list", "gd_defense_score_stats", "defense_export"),
    **_group("graduationDesign.defense.groupManage", "defense_create", "defense_update",
             "defense_assign", "defense_unassign", "expert_list", "expert_create", "expert_status"),
    **_group("graduationDesign.defense.publish", "defense_publish"),
    **_group("graduationDesign.defense.notify", "defense_notify"),
    **_group("graduationDesign.defense.score", "gd_defense_score_entry"),
    **_group("graduationDesign.defense.scoreConfirm", "gd_defense_score_confirm",
             "gd_defense_score_revoke_confirmation", "gd_defense_absence_entry"),
    **_group("graduationDesign.defense.secondRound", "gd_defense_score_second"),
    **_group("graduationDesign.grade.view", "gd_grades", "gd_grade_detail", "gd_grade_stats"),
    **_group("graduationDesign.grade.calculate", "gd_grade_calculate"),
    **_group("graduationDesign.grade.review", "gd_grade_review"),
    **_group("graduationDesign.grade.publish", "gd_grade_publish"),
    **_group("graduationDesign.grade.withdraw", "gd_grade_withdraw"),
    **_group("graduationDesign.grade.appealReview", "appeal_list", "appeal_review"),
    **_group("graduationDesign.grade.view", "gd_excellent_outcome_candidates", "gd_excellent_outcomes",
             "gd_excellent_outcome_nominate"),
    **_group("graduationDesign.grade.review", "gd_excellent_outcome_major_review"),
    **_group("graduationDesign.grade.publish", "gd_excellent_outcome_college_review"),
    **_group("graduationDesign.defense.view", "gd_defense_delays", "gd_defense_delay_advisor_review"),
    **_group("graduationDesign.defense.groupManage", "gd_defense_delay_major_review",
             "gd_defense_delay_college_review", "gd_defense_delay_schedule"),
    **_group("graduationDesign.risk.view", "gd_risks", "gd_risk_stats", "gd_risk_last_scan"),
    **_group("graduationDesign.risk.scan", "gd_risk_scan"),
    **_group("graduationDesign.risk.accept", "gd_risk_accept"),
    **_group("graduationDesign.risk.process", "gd_risk_process"),
    **_group("graduationDesign.risk.close", "gd_risk_close"),
    **_group("graduationDesign.archive.view", "gd_archives", "gd_archive_detail", "gd_archive_stats"),
    **_group("graduationDesign.archive.preview", "gd_archive_generate", "gd_archive_batch_generate_preview",
             "gd_archive_batch_file_preview"),
    **_group("graduationDesign.archive.file", "gd_archive_submit", "gd_archive_file",
             "gd_archive_reject", "gd_archive_batch_generate", "gd_archive_batch_file"),
    **_group("graduationDesign.archive.export", "gd_archive_export"),
    **_group("graduationDesign.template.view", "list_templates", "variables", "stats", "detail"),
    **_group("graduationDesign.template.manage", "create", "update", "set_status", "set_default"),
    **_group("graduationDesign.audit.view", "audit_logs"),
}

GRADUATION_ENDPOINT_PERMISSION_OVERRIDES = {
    "graduation_batch.batch_archive": "graduationDesign.batch.archive",
    "graduation_student.batch_archive": "graduationDesign.student.manage",
}


def graduation_permission_for(method: str, path: str) -> str | None:
    """Legacy path resolver for diagnostics only; it has no generic fallback."""
    method = (method or "GET").upper()
    path = (path or "").rstrip("/")
    rules = (
        ("POST", "/graduation/proposals/", "/review", "graduationDesign.proposal.review"),
        ("POST", "/graduation/defense-groups/", "/publish", "graduationDesign.defense.publish"),
        ("POST", "/graduation/gd-grades/", "/publish", "graduationDesign.grade.publish"),
        ("POST", "/graduation/gd-plagiarism/", "/result", "graduationDesign.plagiarism.result"),
        ("POST", "/graduation/gd-plagiarism/", "/dispute/review", "graduationDesign.plagiarism.disputeReview"),
        ("POST", "/graduation/gd-student-evals/", "", "graduationDesign.guide.manage"),
        ("POST", "/graduation/gd-guidance-plans/", "/checkin", "graduationDesign.guide.manage"),
        ("POST", "/graduation/gd-defense-scores/", "/confirm", "graduationDesign.defense.manage"),
        ("POST", "/graduation/gd-defense-scores/", "/second-defense", "graduationDesign.defense.manage"),
        ("POST", "/graduation/gd-defense-scores/entry", "", "graduationDesign.defense.score"),
    )
    for expected_method, contains, suffix, code in rules:
        if method == expected_method and contains in path and (not suffix or path.endswith(suffix)):
            return code
    if method == "POST" and path.endswith("/graduation/batches"):
        return "graduationDesign.batch.create"
    if method == "GET" and path.endswith("/graduation/dashboard"):
        return "graduationDesign.dashboard.view"
    if method == "GET" and path.endswith("/graduation/gd-guidance-plans"):
        return "graduationDesign.view"
    export_domains = {
        "/proposals/export": "graduationDesign.proposal.export",
        "/finals/export": "graduationDesign.final.export",
        "/gd-taskbooks/": "graduationDesign.taskbook.export",
    }
    if method == "POST":
        for fragment, code in export_domains.items():
            if fragment in path and (path.endswith("/export") or path.endswith("/export-pdf")):
                return code
    return None


def graduation_permission_for_endpoint(endpoint) -> str | None:
    endpoint_name = getattr(endpoint, "__name__", "")
    module_name = getattr(endpoint, "__module__", "").rsplit(".", 1)[-1]
    return (
        GRADUATION_ENDPOINT_PERMISSION_OVERRIDES.get(f"{module_name}.{endpoint_name}")
        or GRADUATION_ENDPOINT_PERMISSIONS.get(endpoint_name)
    )


def require_graduation_request_permission(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    endpoint = request.scope.get("endpoint")
    endpoint_name = getattr(endpoint, "__name__", "")
    is_context = endpoint_name == "get_context"
    if role in {"GD_COLLEGE_ADMIN", "COLLEGE_ADMIN"} and not is_context:
        if not (user.get("collegeId") or user.get("collegeIds")):
            raise no_permission("缺少学院数据范围（collegeId），请配置后重新登录。")
    if role == "GD_MAJOR_ADMIN" and not is_context:
        if not (user.get("majorId") or user.get("majorIds")):
            raise no_permission("缺少专业数据范围（majorId），请配置后重新登录。")

    code = graduation_permission_for_endpoint(endpoint)
    if not code:
        method = (request.method or "GET").upper()
        if method not in {"GET", "HEAD", "OPTIONS"}:
            raise no_permission(f"毕业设计写接口未登记动作权限：{endpoint_name or 'unknown'}")
        raise no_permission(f"毕业设计读接口未登记动作权限：{endpoint_name or 'unknown'}")
    request.state.permission_code = code
    from app.core.context import set_current_permission_code
    set_current_permission_code(code)
    return enforce_permission(user, code)
