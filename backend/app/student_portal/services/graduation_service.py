"""学生 PC 门户 · 毕业设计（第2期）。

任务书读取复用 mobile_student_service；电子确认统一委托毕业设计任务书权威确认服务，
以“学生 + 任务书版本 + 规范化内容哈希”原子落签名、状态和审计，不重复维护签署事务。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import mobile_student_service as stu
from app.student_portal.services import common_service as common


def taskbook(user: dict) -> dict:
    """查看本人任务书（复用 graduation_taskbook）。"""
    return stu.graduation_taskbook(user)


def taskbook_sign(user: dict, body: dict) -> dict:
    """学生 PC 任务书确认统一走带版本和内容哈希的权威服务。"""
    from app.modules.graduation.services.graduation_taskbook_confirmation_service import (
        confirm_with_evidence,
    )

    payload = body or {}
    return confirm_with_evidence(
        user,
        expected_version=(
            payload.get("taskbookVersion")
            or payload.get("expectedVersion")
        ),
        confirm=bool(payload.get("confirm")),
    )


def taskbook_print(user: dict, body: dict) -> dict:
    """任务书打印留痕（PORTAL_PRINT + 水印）。"""
    body = body or {}
    return common.print_log(user, {"bizType": "GRADUATION_TASKBOOK",
                                   "bizId": str(body.get("bizId") or ""),
                                   "docName": "毕业设计任务书"})


# ── 开题报告：长文档撰写 + 附件提交（复用现有 mobile 开题流程） ──

def proposal(user: dict) -> dict:
    """查看本人开题报告状态（可提交/可重交/驳回意见/历史）。"""
    return stu.graduation_proposal(user)


def submit_proposal(user: dict, body: dict) -> dict:
    """提交/重交开题报告：长文本正文（研究背景/方案/预期成果）+ 附件 file_id 列表。

    附件先经 POST /files 得到 file_id，再随本接口以 attachments=[file_id,...] 携带。
    """
    body = body or {}
    background = str(body.get("background") or "").strip()
    plan = str(body.get("plan") or "").strip()
    outcome = str(body.get("outcome") or "").strip()
    attachments = body.get("attachments") or []
    if not background:
        raise AppException("VALIDATION_ERROR", "选题背景不能为空")
    if not plan:
        raise AppException("VALIDATION_ERROR", "研究方案与进度不能为空")
    if not isinstance(attachments, list):
        raise AppException("VALIDATION_ERROR", "附件格式不正确")
    return stu.graduation_submit_proposal(user, {
        "background": background, "plan": plan, "outcome": outcome, "attachments": attachments})


# ── 中期检查：批注对照与整改（复用现有 mobile 中期流程） ──

def midterm(user: dict) -> dict:
    """查看本人中期检查（含导师批注/问题清单/整改状态）。"""
    return stu.graduation_midterm(user)


def midterm_rectify(user: dict, body: dict) -> dict:
    """对照导师批注逐条整改并回复（整改说明非空；仅 RECTIFYING 态可提交）。"""
    body = body or {}
    content = str(body.get("content") or "").strip()
    if not content:
        raise AppException("VALIDATION_ERROR", "整改说明不能为空")
    return stu.graduation_midterm_rectify(user, content)


# ── 成果提交（大附件）+ 查重报告展示（复用现有 mobile 成果流程） ──

def final(user: dict) -> dict:
    """查看本人论文成果状态（可提交初稿/定稿 + 各版本 + 查重率 + 退回意见）。"""
    return stu.graduation_final(user)


def submit_final(user: dict, body: dict) -> dict:
    """提交/重交论文成果（初稿/定稿）：必须上传论文附件（大文件走 POST /files）。

    查重率由服务端产出，客户端不得自报（复用 graduation_submit_final 的服务端逻辑）。
    """
    body = body or {}
    final_type = str(body.get("finalType") or "初稿").strip()
    if final_type not in ("初稿", "定稿"):
        raise AppException("VALIDATION_ERROR", "finalType 必须是 初稿 或 定稿")
    attachments = body.get("attachments") or []
    if not isinstance(attachments, list) or not attachments:
        raise AppException("VALIDATION_ERROR", "请先上传论文/成果附件再提交")
    return stu.graduation_submit_final(user, {"finalType": final_type, "attachments": attachments})


# ── 答辩安排 + 成绩 + 成绩申诉（复用现有 mobile 流程） ──

def defense(user: dict) -> dict:
    """查看本人答辩安排（时间/地点/评委，仅已发布）。"""
    return stu.graduation_defense(user)


def grade(user: dict) -> dict:
    """查看本人毕设成绩（未发布仅提示流转中，不露分数）。"""
    return stu.graduation_grade(user)


def grade_appeal(user: dict, body: dict) -> dict:
    """对已发布成绩发起更正申诉（须成绩已发布；理由不少于 5 字）。"""
    body = body or {}
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise AppException("VALIDATION_ERROR", "申诉理由不能为空")
    return stu.graduation_grade_appeal(user, reason)
