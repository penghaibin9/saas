"""学生 PC 门户 · 教务学业（第3期）。

教务学生自视图已很完整（mobile_academic_affairs_service：成绩单/课表/学籍/异动/选课/学分/预警/
补重修/毕业进度/学生评教）。PC 门户在其上接出并叠加 PC 重活（成绩单打印、学籍异动材料+签署等）。
首刀：我的成绩 / 成绩单查看 + 打印。严格本人由 aa._me（_require_student+resolve_student）收口。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import mobile_academic_affairs_service as aa
from app.services.mobile_student_service import _require_student
from app.student_portal.services import common_service as common


def transcript(user: dict) -> dict:
    """我的成绩单（本人已发布成绩 + GPA）。未发布不露分由教务成绩服务口径保证。"""
    return aa.transcript_my(user)


# ── 我的课表 + 选课（复用教务学生自视图） ──

def schedule(user: dict) -> dict:
    """我的课表（最新已发布，按行政班推导）。"""
    return aa.schedule_my(user)  # aa._me 收口本人+非学生403


def selection_courses(user: dict, batch_id=None) -> dict:
    """选课·可选课程（OPEN 批次 + 实时余量）。"""
    _require_student(user)
    return aa.selection_courses_my(user, batch_id)


def selection_enroll(user: dict, body: dict) -> dict:
    """选课·选课（selectionCourseId 必填，容量/冲突由教务选课服务校验）。"""
    _require_student(user)
    return aa.selection_enroll_my(user, body or {})


def selection_drop(user: dict, body: dict) -> dict:
    """选课·退课（selectionCourseId 必填）。"""
    _require_student(user)
    return aa.selection_drop_my(user, body or {})


def selection_records(user: dict, batch_id=None) -> dict:
    """选课·本人选课记录。"""
    _require_student(user)
    return aa.selection_records_my(user, batch_id)


# ── 学籍信息 + 学籍异动申请（复用教务学生自视图；PC 加打印审批表） ──

def status(user: dict) -> dict:
    """我的学籍状态 + 异动记录。"""
    return aa.status_my(user)  # aa._me 收口本人+非学生403


def submit_status_change(user: dict, body: dict) -> dict:
    """本人发起学籍异动申请（转专业/休学/复学等）。底层不收附件，PC 只提交核心字段。"""
    _require_student(user)
    body = body or {}
    change_type = str(body.get("changeType") or "").strip()
    reason = str(body.get("reason") or "").strip()
    if not change_type:
        raise AppException("VALIDATION_ERROR", "异动类型（changeType）必填")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "异动事由至少 5 个字")
    return aa.submit_status_change_my(user, body)


def status_change_print(user: dict, body: dict) -> dict:
    """打印学籍异动申请审批表（PORTAL_PRINT + 水印 + 可下载正文）。"""
    _require_student(user)
    body = body or {}
    st = status(user)
    log = common.print_log(user, {"bizType": "STATUS_CHANGE",
                                  "bizId": str(body.get("bizId") or body.get("changeType") or ""),
                                  "docName": "学籍异动申请审批表"})
    return {
        **log,
        "docName": "学籍异动申请审批表",
        "document": {
            "studentNo": st.get("studentNo"),
            "realName": st.get("realName") or user.get("realName"),
            "studentStatus": st.get("studentStatus"),
            "changeType": body.get("changeType"),
            "reason": body.get("reason"),
            "changes": st.get("changes") or [],
        },
    }


# ── 免修 / 缓考 / 补重修 + 毕业资格自查（复用教务学生自视图） ──

def exam(user: dict) -> dict:
    _require_student(user)
    return aa.exam_my(user)


def exam_defer(user: dict, status=None) -> dict:
    _require_student(user)
    return aa.exam_defer_my(user, status)


def exam_defer_apply(user: dict, body: dict) -> dict:
    _require_student(user)
    return aa.exam_defer_apply_my(user, body or {})


def exam_defer_resubmit(user: dict, defer_id) -> dict:
    _require_student(user)
    return aa.exam_defer_resubmit_my(user, defer_id)


def makeup(user: dict) -> dict:
    """我的补考重修 + 免修申请列表。"""
    _require_student(user)
    return aa.makeup_my(user)


def retake_apply(user: dict, body: dict) -> dict:
    """本人发起重修报名（课程名必填）。"""
    _require_student(user)
    body = body or {}
    if not str(body.get("courseName") or "").strip():
        raise AppException("VALIDATION_ERROR", "课程名必填")
    return aa.retake_apply_my(user, body)


def exemption_apply(user: dict, body: dict) -> dict:
    """本人发起免修申请（课程名必填）。"""
    _require_student(user)
    body = body or {}
    if not str(body.get("courseName") or "").strip():
        raise AppException("VALIDATION_ERROR", "课程名必填")
    return aa.exemption_apply_my(user, body)


def graduation_audit(user: dict) -> dict:
    """毕业资格自查：汇总毕业进度七项 + 学分修读 + 学业预警（只读）。"""
    _require_student(user)
    return {
        "progress": aa.graduation_progress_my(user),
        "credits": aa.credits_my(user),
        "warnings": aa.warning_my(user),
    }


def evaluation_tasks(user: dict) -> dict:
    """开放窗口内本班学生评教任务（匿名槽位，与小程序同口径）。"""
    _require_student(user)
    return aa.evaluation_tasks_my(user)


def evaluation_submit(user: dict, body: dict) -> dict:
    """学生匿名提交评教（本班校验在 mobile 服务）。"""
    _require_student(user)
    return aa.evaluation_submit_my(user, body or {})


def grade_recheck(user: dict) -> dict:
    _require_student(user)
    return aa.grade_recheck_my(user)


def grade_recheck_submit(user: dict, body: dict) -> dict:
    _require_student(user)
    body = body or {}
    if not body.get("acadGradeId"):
        raise AppException("VALIDATION_ERROR", "acadGradeId 必填")
    if len(str(body.get("reason") or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "复查事由至少 5 个字")
    return aa.grade_recheck_submit_my(user, body)


def exam_defer_options(user: dict) -> dict:
    _require_student(user)
    return aa.exam_defer_options_my(user)


def textbook(user: dict) -> dict:
    _require_student(user)
    return aa.textbook_my(user)


def textbook_sign(user: dict, record_id) -> dict:
    _require_student(user)
    return aa.textbook_sign_my(user, record_id)


def level_exam(user: dict) -> dict:
    _require_student(user)
    return aa.level_exam_my(user)


def level_register(user: dict, exam_id) -> dict:
    _require_student(user)
    return aa.level_register_my(user, exam_id)


def level_cancel(user: dict, exam_id) -> dict:
    _require_student(user)
    return aa.level_cancel_my(user, exam_id)


def major_split(user: dict) -> dict:
    _require_student(user)
    return aa.major_split_my(user)


def major_split_submit(user: dict, body: dict) -> dict:
    _require_student(user)
    return aa.major_split_submit_my(user, body or {})


def credits(user: dict) -> dict:
    _require_student(user)
    return aa.credits_my(user)


def warning(user: dict) -> dict:
    _require_student(user)
    return aa.warning_my(user)


def recognition(user: dict) -> dict:
    _require_student(user)
    return aa.recognition_my(user)


def recognition_submit(user: dict, body: dict) -> dict:
    _require_student(user)
    body = body or {}
    if not str(body.get("sourceCourseName") or "").strip() or not str(body.get("targetCourseName") or "").strip():
        raise AppException("VALIDATION_ERROR", "原课程与目标课程必填")
    try:
        score = float(body.get("sourceScore"))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "原成绩须为数字")
    if score < 60 or score > 100:
        raise AppException("VALIDATION_ERROR", "原成绩须在 60–100")
    return aa.recognition_submit_my(user, body)


def transcript_print(user: dict, body: dict) -> dict:
    """成绩单打印留痕（PORTAL_PRINT + 水印 + 可下载正文）。"""
    body = body or {}
    data = transcript(user)
    reason = str(body.get("reason") or body.get("bizId") or "").strip()
    log = common.print_log(user, {"bizType": "TRANSCRIPT",
                                  "bizId": reason,
                                  "docName": "成绩单"})
    return {**log, "docName": "成绩单", "printReason": reason, "document": data}


def schedule_print(user: dict, body: dict) -> dict:
    """课表打印留痕（PORTAL_PRINT + 水印 + 可下载正文）。"""
    _require_student(user)
    body = body or {}
    data = schedule(user)
    reason = str(body.get("reason") or body.get("bizId") or "个人课表").strip()
    log = common.print_log(user, {"bizType": "SCHEDULE",
                                  "bizId": reason,
                                  "docName": "个人课表"})
    return {**log, "docName": "个人课表", "printReason": reason, "document": data}
