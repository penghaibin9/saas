"""学生PC教务服务安全门面：个人成绩只能生成查询件，禁止冒充学校正式成绩单。"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import academic_service as _legacy
from . import common_service as common


def __getattr__(name):
    return getattr(_legacy, name)


def transcript_print(user: dict, body: dict | None = None) -> dict:
    """生成带审计和水印的个人成绩查询件，不提供签章或验真能力。"""
    data = body or {}
    reason = str(data.get("reason") or data.get("bizId") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "开具事由必填且不少于5个字")

    document = _legacy.transcript(user)
    log = common.print_log(user, {
        "bizType": "GRADE_QUERY_COPY",
        "bizId": reason,
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
