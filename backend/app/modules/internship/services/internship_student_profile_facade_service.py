"""Student profile HTTP projections and private current-profile PDF preview."""
from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.core.exceptions import AppException
from app.modules.internship.services import internship_application_material_snapshot_service as material_svc
from app.modules.internship.services import internship_student_profile_item_service as item_svc
from app.modules.internship.services import internship_student_profile_service as profile_svc
from app.modules.internship.services import internship_student_selection_service as selection_svc
from app.services import file_service
from app.services.db_service import _tid, session

_CJK_FONT = "STSong-Light"


def get_profile_items(*, user: dict) -> list[dict]:
    return list(profile_svc.get_my_profile(user).get("items") or [])


def get_profile_completeness(*, user: dict) -> dict:
    tenant_id = _tid(); student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, _record = selection_svc._resolve_context_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        projection = profile_svc.build_profile_projection_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        readiness = material_svc.evaluate_material_readiness(projection, campaign.application_material_policy_json)
        missing = list(readiness.get("missing") or [])
        percent = 100 if readiness.get("ready") else max(0, 100 - min(90, len(missing) * 20))
        return {"percent": percent, "blockers": missing, "readyToSubmit": bool(readiness.get("ready"))}


def add_profile_item(*, user: dict, body: dict) -> dict:
    return profile_svc.add_my_item(body or {}, user)


def update_profile_item(*, user: dict, item_id: int, body: dict) -> dict:
    return item_svc.update_my_item(item_id, body or {}, user)


def delete_profile_item(*, user: dict, item_id: int) -> dict:
    return item_svc.delete_my_item(item_id, user=user)


def get_profile_preview(*, user: dict) -> dict:
    preview = selection_svc.get_my_material_preview(user=user)
    snapshot = dict(preview.get("profileSnapshot") or {})
    school = dict(preview.get("schoolFactSnapshot") or {}); profile = dict(snapshot.get("profile") or {})
    school_fields = [{"key": key, "label": label, "value": school.get(key) or "", "source": "SCHOOL"} for key, label in (
        ("realName", "姓名"), ("studentNo", "学号"), ("collegeName", "学院"), ("majorName", "专业"), ("grade", "年级"), ("className", "班级"),
    )]
    student_fields = [{"key": key, "label": label, "value": profile.get(key) or "", "source": "STUDENT"} for key, label in (
        ("headline", "档案标题"), ("selfIntro", "自我介绍"), ("strengths", "个人优势"), ("skillTags", "技能标签"), ("availableFrom", "可到岗日期"), ("expectedLocations", "期望地点"),
    )]
    return {**preview, "schoolFields": school_fields, "studentFields": student_fields, "sharedFields": school_fields + student_fields}


def _safe(value) -> str:
    if value in (None, ""): return "—"
    if isinstance(value, (list, tuple, set)): value = "、".join(str(item) for item in value if item not in (None, "")) or "—"
    return escape(str(value)).replace("\n", "<br/>")


def _render_current_profile_pdf(preview: dict) -> bytes:
    try: pdfmetrics.getFont(_CJK_FONT)
    except KeyError: pdfmetrics.registerFont(UnicodeCIDFont(_CJK_FONT))
    styles = getSampleStyleSheet()
    title = ParagraphStyle("StudentProfilePreviewTitle", parent=styles["Title"], fontName=_CJK_FONT, fontSize=18, leading=24)
    body = ParagraphStyle("StudentProfilePreviewBody", parent=styles["BodyText"], fontName=_CJK_FONT, fontSize=9.5, leading=15)
    muted = ParagraphStyle("StudentProfilePreviewMuted", parent=styles["BodyText"], fontName=_CJK_FONT, fontSize=8, leading=12)
    buffer = BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    snapshot = dict(preview.get("profileSnapshot") or {}); profile = dict(snapshot.get("profile") or {}); school = dict(preview.get("schoolFactSnapshot") or {})
    story = [
        Paragraph("实习档案预览", title), Paragraph("仅供学生本人确认当前档案展示效果；这不是企业投递的不可变快照。", muted), Spacer(1, 8),
        Paragraph(f"姓名：{_safe(school.get('realName'))}　学号：{_safe(school.get('studentNo'))}", body),
        Paragraph(f"学院：{_safe(school.get('collegeName'))}　专业：{_safe(school.get('majorName'))}", body),
        Paragraph(f"年级：{_safe(school.get('grade'))}　班级：{_safe(school.get('className'))}", body), Spacer(1, 8),
        Paragraph(f"档案标题：{_safe(profile.get('headline'))}", body), Paragraph(f"自我介绍：{_safe(profile.get('selfIntro'))}", body),
        Paragraph(f"个人优势：{_safe(profile.get('strengths'))}", body), Paragraph(f"技能标签：{_safe(profile.get('skillTags') or [])}", body),
        Paragraph(f"可到岗日期：{_safe(profile.get('availableFrom'))}", body), Paragraph(f"期望地点：{_safe(profile.get('expectedLocations') or [])}", body),
    ]
    for index, item in enumerate(list(snapshot.get("items") or []), start=1):
        row = dict(item or {}); story.append(Paragraph(f"{index}. {_safe(row.get('title'))} [{_safe(row.get('itemType'))}] {_safe(row.get('organization'))}", body))
    story.extend([Spacer(1, 10), Paragraph(f"当前档案版本：{int(preview.get('profileVersion') or 0)}　预览哈希：{_safe(preview.get('previewHash'))}", muted)])
    doc.build(story); data = buffer.getvalue()
    if not data.startswith(b"%PDF"): raise AppException("DATA_CONFLICT", "实习档案 PDF 预览生成失败", http_status=409)
    return data


def create_profile_pdf_preview(*, user: dict, body: dict) -> dict:
    payload = dict(body or {}); preview = selection_svc.get_my_material_preview(user=user)
    expected_hash = str(payload.get("materialPreviewHash") or payload.get("previewHash") or "").strip()
    if not expected_hash or expected_hash != str(preview.get("previewHash") or ""):
        raise AppException("DATA_CONFLICT", "档案预览已变化，请刷新企业视角材料预览后重试", http_status=409)
    mode = material_svc.normalize_contact_sharing_policy({"mode": payload.get("contactSharingMode") or "MASKED_ONLY"})
    tenant_id = _tid(); student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, _record = selection_svc._resolve_context_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        material_svc._assert_contact_mode_allowed(mode, campaign.application_material_policy_json)
    meta = file_service.store_bytes(
        _render_current_profile_pdf(preview), f"internship-profile-preview-student-{student_id}-v{int(preview.get('profileVersion') or 0)}.pdf",
        "INTERNSHIP", "application/pdf", biz_id=str(student_id), user=user, visibility="PRIVATE", security_level="NORMAL",
    )
    file_id = str(meta.get("fileId") or "")
    if not file_id: raise AppException("DATA_CONFLICT", "文件中心未返回档案 PDF fileId", http_status=409)
    return {"fileId": file_id, "previewHash": preview.get("previewHash"), "profileVersion": int(preview.get("profileVersion") or 0), "contactSharingMode": mode["mode"]}
