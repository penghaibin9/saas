"""学生PC教务服务安全门面：个人成绩只能生成查询件，禁止冒充学校正式成绩单。"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services.mobile_student_service import _require_student

from . import academic_service as _legacy
from . import common_service as common


def __getattr__(name):
    return getattr(_legacy, name)


def transcript_print(user: dict, body: dict | None = None) -> dict:
    """生成带审计和水印的个人成绩查询件，不提供签章或验真能力。

    兼容旧门户仅传 ``bizId`` 的打印请求；新页面传 ``reason`` 时仍执行不少于
    5 个字的用途校验。权限必须先于业务参数校验，避免非学生请求通过参数错误
    掩盖真实的 403 边界。
    """
    student_user = _require_student(user)
    data = body or {}
    supplied_reason = str(data.get("reason") or "").strip()
    legacy_biz_id = str(data.get("bizId") or "").strip()

    if supplied_reason:
        if len(supplied_reason) < 5:
            raise AppException("VALIDATION_ERROR", "开具事由必填且不少于5个字")
        reason = supplied_reason
    elif legacy_biz_id:
        reason = "本人查询使用"
    else:
        raise AppException("VALIDATION_ERROR", "开具事由必填且不少于5个字")

    document = _legacy.transcript(student_user)
    log = common.print_log(student_user, {
        "bizType": "GRADE_QUERY_COPY",
        "bizId": legacy_biz_id or reason,
        "docName": "个人成绩查询件",
        "reason": reason,
    })
    return {
        **log,
        "docName": "个人成绩查询件",
        "documentType": "PERSONAL_GRADE_QUERY_COPY",
        "official": False,
        "verifiable": False,
        "verificationCode": None,
        "renderPolicy": "TEXT_ONLY",
        "notice": "本文件仅供本人查询，不等同于学校盖章、电子签章或可验真的正式成绩单。",
        "printReason": reason,
        "document": document,
    }
