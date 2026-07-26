"""本轮精确安全 Router 的动作权限登记。

使用 ``模块名.函数名`` 覆盖，避免多个 Router 都叫 ``detail/stats/submit`` 时串权限。
没有任何泛化 manage 回落；未登记接口继续 fail-closed。
"""
from __future__ import annotations

from app.core.graduation_permissions import (
    GRADUATION_ENDPOINT_PERMISSION_OVERRIDES,
    GRADUATION_PERMISSION_CODES,
)

_INSTALLED = False


def _register(module: str, code: str, *names: str) -> None:
    if code not in GRADUATION_PERMISSION_CODES:
        raise RuntimeError(f"未注册毕业设计权限码：{code}")
    for name in names:
        GRADUATION_ENDPOINT_PERMISSION_OVERRIDES[f"{module}.{name}"] = code


def install_graduation_permission_extensions() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    module = "graduation_sensitive_router"
    _register(module, "graduationDesign.student.view", "gd_student_stats")
    _register(module, "graduationDesign.dashboard.view", "gd_stats_overview", "gd_stats_college")
    _register(module, "graduationDesign.plagiarism.view", "plagiarism_stats", "plagiarism_list")
    _register(module, "graduationDesign.plagiarism.start", "plagiarism_submit", "plagiarism_dispute")
    _register(module, "graduationDesign.plagiarism.result", "plagiarism_result")
    _register(module, "graduationDesign.plagiarism.disputeReview", "plagiarism_dispute_review")
    _register(module, "graduationDesign.review.view", "review_stats", "review_list")
    _register(module, "graduationDesign.review.assign", "review_assign")
    _register(module, "graduationDesign.review.submit", "review_submit")
    _register(module, "graduationDesign.review.return", "review_return")
    _register(module, "graduationDesign.defense.view", "defense_stats", "defense_list")
    _register(module, "graduationDesign.defense.score", "defense_entry")
    _register(module, "graduationDesign.defense.scoreConfirm", "defense_absence", "defense_confirm", "defense_revoke")
    _register(module, "graduationDesign.defense.secondRound", "defense_second")
    _register(module, "graduationDesign.grade.view", "grade_stats", "grade_list", "grade_detail")
    _register(module, "graduationDesign.grade.calculate", "grade_calculate")
    _register(module, "graduationDesign.grade.review", "grade_review")
    _register(module, "graduationDesign.grade.publish", "grade_publish")
    _register(module, "graduationDesign.grade.withdraw", "grade_withdraw")
    _register(module, "graduationDesign.archive.preview", "archive_generate_preview", "archive_file_preview")
    _register(module, "graduationDesign.archive.file", "archive_generate_batch", "archive_file_batch")
    _register(module, "graduationDesign.student.import", "student_import_confirm")

    module = "graduation_archive_sensitive_router"
    _register(module, "graduationDesign.archive.view", "stats", "list_rows", "detail")
    _register(module, "graduationDesign.archive.export", "export_rows")
    _register(module, "graduationDesign.archive.preview", "generate")
    _register(module, "graduationDesign.archive.file", "submit", "file_record", "reject")

    module = "graduation_taskbook_sensitive_router"
    _register(module, "graduationDesign.taskbook.view", "stats", "list_rows", "detail")
    _register(module, "graduationDesign.taskbook.export", "export_rows", "export_pdf")
    _register(module, "graduationDesign.taskbook.issue", "issue")
    _register(module, "graduationDesign.taskbook.confirmOnBehalf", "confirm")
    _register(module, "graduationDesign.taskbook.update", "change")

    module = "graduation_process_sensitive_router"
    _register(module, "graduationDesign.guidance.view", "guidance_stats", "guidance_list", "plan_list")
    _register(module, "graduationDesign.guidance.create", "guidance_create", "plan_create")
    _register(module, "graduationDesign.guidance.update", "guidance_void", "plan_checkin", "plan_cancel")
    _register(module, "graduationDesign.midterm.review", "midterm_stats", "midterm_list", "midterm_detail",
              "midterm_check", "midterm_rectify", "midterm_rectify_review")

    module = "graduation_material_sensitive_router"
    _register(module, "graduationDesign.dashboard.view", "dashboard")
    _register(module, "graduationDesign.student.view", "legacy_students", "legacy_student_detail")
    _register(module, "graduationDesign.proposal.view", "proposal_stats", "proposals", "proposal_detail")
    _register(module, "graduationDesign.proposal.review", "proposal_review")
    _register(module, "graduationDesign.proposal.defense", "proposal_defense")
    _register(module, "graduationDesign.proposal.remind", "proposal_remind")
    _register(module, "graduationDesign.proposal.export", "proposal_export")
    _register(module, "graduationDesign.final.view", "final_stats", "finals", "final_detail")
    _register(module, "graduationDesign.final.review", "final_review")
    _register(module, "graduationDesign.final.remind", "final_remind")
    _register(module, "graduationDesign.final.export", "final_export")
    _register(module, "graduationDesign.defense.view", "defense_groups", "defense_eligible", "defense_detail")
    _register(module, "graduationDesign.defense.groupManage", "defense_create", "defense_update",
              "defense_assign", "defense_unassign")
    _register(module, "graduationDesign.defense.publish", "defense_publish")
    _register(module, "graduationDesign.defense.notify", "defense_notify")
    _register(module, "graduationDesign.defense.view", "defense_export")
    _register(module, "graduationDesign.audit.view", "audit_logs")
