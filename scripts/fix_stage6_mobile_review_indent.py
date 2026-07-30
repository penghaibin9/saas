from __future__ import annotations

from pathlib import Path

PATH = Path("backend/app/services/mobile_teacher_service.py")
text = PATH.read_text(encoding="utf-8")

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

compile(text, str(PATH), "exec")
PATH.write_text(text, encoding="utf-8")
print("Stage 6 mobile review delegation indentation fixed")
