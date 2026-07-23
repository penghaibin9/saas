"""学生 PC 门户 · 岗位实习（第5期）。

实习学生入口在 mobile_student_service 已很完整（打卡/周报/请假/协议确认/自评/过程报告/变更）。
PC 门户接出并补 PC 重活：月报/总结长文档（复用过程报告）、三方协议打印、实习成绩申诉。
严格本人由底层 _require_student + resolve_student 收口。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import mobile_student_service as stu
from app.services.mobile_student_service import _require_student
from app.student_portal.services import common_service as common


def my(user: dict) -> dict:
    """我的实习（本人）。"""
    return stu.internship_my(user)


def weekly_submit(user: dict, body: dict) -> dict:
    """实习周报提交（本人，字段校验由底层完成）。"""
    return stu.internship_weekly_submit(user, body or {})


def leave_list(user: dict) -> dict:
    """本人实习请假列表。"""
    from app.modules.internship.services import internship_leave_service as lv
    return lv.my_leaves(user)


def leave_apply(user: dict, body: dict) -> dict:
    """实习请假申请（本人）。"""
    from app.modules.internship.services import internship_leave_service as lv
    return lv.apply(user, body or {})


def leave_return(user: dict, leave_id: str, body: dict) -> dict:
    """本人销假。"""
    from app.modules.internship.services import internship_leave_service as lv
    return lv.return_my(user, leave_id, body or {})


def checkin(user: dict, body: dict) -> dict:
    """PC 门户打卡（复用移动端落库；无定位时记为已记录，不自动定罪）。"""
    return stu.internship_checkin(user, body or {})


def self_eval_submit(user: dict, body: dict) -> dict:
    """实习自评提交（本人）。"""
    from app.modules.internship.services import internship_student_eval_service as se
    payload = body or {}
    # 门户表单字段映射到学生自评服务口径
    if payload.get("performance") or payload.get("reflection"):
        payload = {
            "selfSummary": (payload.get("performance") or payload.get("selfSummary") or "").strip(),
            "selfHarvest": (payload.get("reflection") or payload.get("selfHarvest") or "").strip(),
            "problems": payload.get("problems") or "",
        }
    return se.student_submit(user, payload)


def report_submit(user: dict, body: dict) -> dict:
    """实习月报/总结长文档提交（复用过程报告：reportType + periodKey + content 长文本）。"""
    body = body or {}
    if not str(body.get("reportType") or "").strip():
        raise AppException("VALIDATION_ERROR", "报告类型（reportType）必填")
    if not str(body.get("content") or "").strip():
        raise AppException("VALIDATION_ERROR", "报告内容不能为空")
    return stu.internship_process_report_submit(user, body)


def agreement_print(user: dict, body: dict) -> dict:
    """三方协议打印留痕（PORTAL_PRINT + 水印）。"""
    _require_student(user)
    return common.print_log(user, {"bizType": "INTERNSHIP_AGREEMENT",
                                   "bizId": str((body or {}).get("bizId") or ""),
                                   "docName": "实习三方协议"})


def score_appeal(user: dict, body: dict) -> dict:
    """实习成绩申诉（书面理由，复用通用事务申请）。"""
    body = body or {}
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少 5 个字")
    return stu.campus_service_apply(user, {"serviceKey": "INTERNSHIP_SCORE_APPEAL", "reason": reason})


def makeup_list(user: dict) -> dict:
    """本人补卡申请列表。"""
    from app.modules.internship.services import internship_makeup_service as mk
    return mk.my_makeups(user)


def makeup_apply(user: dict, body: dict) -> dict:
    """补卡申请（本人）。"""
    from app.modules.internship.services import internship_makeup_service as mk
    b = body or {}
    return mk.apply(user, checkin_date=b.get("checkinDate") or b.get("date") or "",
                    reason=b.get("reason") or "", makeup_type=b.get("makeupType") or "MISSING",
                    internship_id=b.get("internshipId"))


def makeup_withdraw(user: dict, makeup_id) -> dict:
    from app.modules.internship.services import internship_makeup_service as mk
    return mk.withdraw(user, makeup_id)


def intention_my(user: dict) -> dict:
    return stu.internship_intention_my(user)


def intention_save(user: dict, body: dict) -> dict:
    return stu.internship_intention_save(user, body or {})


def applications_my(user: dict) -> dict:
    return {"items": stu.internship_application_list(user)}


def application_submit(user: dict, body: dict) -> dict:
    """保存草稿并提交（门户一键）。"""
    b = body or {}
    saved = stu.internship_application_save(user, b)
    app_id = str((saved or {}).get("id") or b.get("id") or "")
    if not app_id:
        raise AppException("VALIDATION_ERROR", "申请保存失败，无法提交")
    if (saved or {}).get("status") in ("SUBMITTED", "APPROVED"):
        return saved
    return stu.internship_application_submit(user, app_id)


def change_list(user: dict) -> dict:
    return {"items": stu.internship_change_list(user)}


def change_apply(user: dict, body: dict) -> dict:
    return stu.internship_change_apply(user, body or {})
