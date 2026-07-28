"""选题志愿 Excel 导入契约一致性。

模板说明、预校验和最终落库必须使用同一状态规则：仅进行中的选题轮次可导入。
避免已关闭轮次在 dry-run 显示通过，到 confirm 才失败。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.models import GraduationTopicRound
from app.services.db_service import _tid, session

def validate_open_round(
    round_id: str, row: dict, row_no: int, *, base_validate,
) -> str | None:
    with session() as db:
        round_row = db.get(GraduationTopicRound, int(round_id))
        if not round_row or round_row.is_deleted or round_row.tenant_id != _tid():
            return "选题轮次不存在"
        if round_row.status != "OPEN":
            return "仅进行中的选题轮次可导入志愿"
    return base_validate(round_id, row, row_no)


def open_only_spec(round_id: str, *, base_spec, base_validate):
    spec = base_spec(round_id)
    spec.notes = [
        note.replace("轮次须为「进行中」或「已关闭」状态", "轮次须为「进行中」状态")
        for note in (spec.notes or [])
    ]
    spec.business_validate = lambda row, row_no: validate_open_round(
        round_id, row, row_no, base_validate=base_validate,
    )
    spec.template_version = "v2-open-round-only"
    return spec
