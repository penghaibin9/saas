"""Graduation topic scoped history and streaming XLSX hardening."""
from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import Iterable
from sqlalchemy import BigInteger, cast, func, or_, select
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.models import GraduationAuditTrail, GraduationTopic
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_release_topic_core_hardening import _topic_scope_select


def _install_topic_export_hardening() -> None:
    from app.modules.graduation.services import graduation_topic_service as svc
    def list_topic_history(page, page_size, keyword=None, topic_id=None, action=None):
        with session() as db:
            topic_scope = _topic_scope_select(db)
            # Compare on the numeric side.  MySQL 8 assigns different default
            # collations to CAST(... AS CHAR) and legacy VARCHAR audit columns,
            # which makes an otherwise valid topic-history join fail with 1267.
            # TOPIC audit ids are canonical numeric topic ids, so this also keeps
            # the join independent from database/server collation defaults.
            join_on = GraduationTopic.id == cast(GraduationAuditTrail.biz_id, BigInteger)
            filters = [
                GraduationAuditTrail.tenant_id == _tid(), GraduationAuditTrail.biz_type == "TOPIC",
                GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False),
                GraduationTopic.id.in_(topic_scope),
            ]
            if topic_id: filters.append(GraduationAuditTrail.biz_id == str(topic_id))
            if action: filters.append(GraduationAuditTrail.action == action)
            value = str(keyword or "").strip()
            if value:
                like = f"%{value}%"
                filters.append(or_(GraduationTopic.title.like(like), GraduationAuditTrail.action.like(like), GraduationAuditTrail.detail.like(like)))
            base = select(GraduationAuditTrail, GraduationTopic.title).join(GraduationTopic, join_on).where(*filters)
            total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
            size = min(200, max(1, int(page_size)))
            rows = db.execute(base.order_by(GraduationAuditTrail.occurred_at.desc(), GraduationAuditTrail.id.desc()).offset((max(1, int(page)) - 1) * size).limit(size)).all()
            items = [{
                "id": str(a.id), "topicId": a.biz_id or "", "topicTitle": title or "",
                "action": a.action or "", "operator": a.operator or "系统", "roleName": a.role_name or "",
                "detail": a.detail or "", "beforeVal": a.before_val or "", "afterVal": a.after_val or "",
                "occurredAt": _iso(a.occurred_at),
            } for a, title in rows]
            return items, total

    def _write_xlsx(filename: str, sheet: str, headers: list[str], rows: Iterable[list], *, title: str | None = None):
        from openpyxl import Workbook
        wb = Workbook(write_only=True); ws = wb.create_sheet(sheet)
        if title: ws.append([title] + [""] * (len(headers) - 1))
        ws.append(headers); row_count = 0
        for row in rows:
            ws.append(list(row)); row_count += 1
        buf = io.BytesIO(); wb.save(buf)
        return {"filename": filename, "contentBase64": base64.b64encode(buf.getvalue()).decode("ascii"), "rowCount": row_count, "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

    def export_topics_xlsx(keyword=None, batch_id=None, source_type=None, category=None, review_status=None, status=None, is_full=None, archive_view=None, has_requirements=None, has_attachments=None, missing_category=None):
        svc.enforce_permission(get_current_user_ctx() or {}, "graduationDesign.topic.export")
        if not batch_id: raise AppException("VALIDATION_ERROR", "导出前必须选择毕业设计批次")
        def rows():
            page = 1
            while True:
                items, _ = svc.list_topics(page, 200, keyword=keyword, batch_id=batch_id, source_type=source_type, category=category, review_status=review_status, status=status, is_full=is_full, archive_view=archive_view, has_requirements=has_requirements, has_attachments=has_attachments, missing_category=missing_category)
                if not items: break
                for it in items:
                    yield [it.get("topicNo", ""), it.get("title", ""), it.get("batchName", ""), it.get("sourceLabel", ""), it.get("advisorName", ""), it.get("majorName", ""), it.get("category", ""), svc.DIFF_LABEL.get(it.get("difficulty") or "", it.get("difficulty") or ""), it.get("enterpriseName", ""), f"{it.get('selected', 0)}/{it.get('capacity', 0)}", it.get("reviewLabel", ""), it.get("statusLabel", ""), it.get("requirements", ""), it.get("updatedAt", "")]
                if len(items) < 200: break
                page += 1
        operator = str((get_current_user_ctx() or {}).get("realName") or "系统")
        return _write_xlsx(f"题目库台账_{datetime.now():%Y%m%d_%H%M}.xlsx", "题目库台账", ["题目编号", "题目名称", "批次", "来源", "指导教师", "专业", "分类", "难度", "企业名称", "容量(已选/上限)", "审核状态", "题目状态", "题目要求", "更新时间"], rows(), title=f"题目库台账　导出时间：{datetime.now():%Y-%m-%d %H:%M}　导出人：{operator}")

    def export_topic_history_xlsx(keyword=None, topic_id=None, action=None):
        def rows():
            page = 1
            while True:
                items, _ = list_topic_history(page, 200, keyword=keyword, topic_id=topic_id, action=action)
                if not items: break
                for it in items: yield [it["occurredAt"], it["action"], it["topicTitle"], it["topicId"], it["operator"], it["roleName"], it["detail"], it["beforeVal"], it["afterVal"]]
                if len(items) < 200: break
                page += 1
        return _write_xlsx(f"题目操作历史_{datetime.now():%Y%m%d_%H%M}.xlsx", "题目操作历史", ["操作时间", "操作类型", "题目名称", "题目ID", "操作人", "角色", "详情", "变更前", "变更后"], rows())

    svc.list_topic_history = list_topic_history
    from app.modules.graduation.services.graduation_export_security import sanitize_xlsx_export
    svc.export_topics_xlsx = sanitize_xlsx_export(export_topics_xlsx)
    svc.export_topic_history_xlsx = sanitize_xlsx_export(export_topic_history_xlsx)
