"""Enterprise resume-PDF Authority over immutable internship application snapshots.

The PDF is a derived, one-time file artifact. It never becomes a second application truth: the
immutable snapshot remains the evidence authority and the generated file is bound back to that
snapshot. Enterprise callers must first pass canonical application ownership before this service
will resolve or generate the artifact.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models.file import FileBinding, FileObject
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.modules.internship.services import internship_enterprise_application_decision_service as decision_svc
from app.services import file_service
from app.services.file_access_service import register_file_resolver, upsert_file_binding
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED
from app.services.storage import get_backend

PDF_BIZ_TYPE = "INTERNSHIP_APPLICATION_PROFILE_PDF"
PDF_RELATION_TYPE = "DERIVED_RESUME_PDF"
_SYSTEM_ACTOR = {"userType": "SYSTEM", "realName": "实习材料系统"}
_CJK_FONT = "STSong-Light"


@register_file_resolver(PDF_BIZ_TYPE)
def _deny_generic_resume_pdf_access(_db, _file_obj, _bindings, _user, _action) -> bool:
    """This highly-sensitive artifact is readable only through the owned-application business route."""
    return False


def _safe(value) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, (list, tuple, set)):
        value = "、".join(str(item) for item in value if item not in (None, "")) or "—"
    return escape(str(value)).replace("\n", "<br/>")


def _styles():
    # ReportLab ships the CID font adapter; no repository font file is required or redistributed.
    try:
        pdfmetrics.getFont(_CJK_FONT)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(_CJK_FONT))
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("InternshipResumeTitle", parent=base["Title"], fontName=_CJK_FONT, fontSize=18, leading=24, spaceAfter=10),
        "heading": ParagraphStyle("InternshipResumeHeading", parent=base["Heading2"], fontName=_CJK_FONT, fontSize=12, leading=18, spaceBefore=8, spaceAfter=5),
        "body": ParagraphStyle("InternshipResumeBody", parent=base["BodyText"], fontName=_CJK_FONT, fontSize=9.5, leading=15),
        "muted": ParagraphStyle("InternshipResumeMuted", parent=base["BodyText"], fontName=_CJK_FONT, fontSize=8, leading=12),
    }


def render_snapshot_profile_pdf(snapshot: InternshipApplicationMaterialSnapshot) -> bytes:
    """Render only frozen profile/school facts; never render contact values or volunteer choices."""
    profile_snapshot = dict(snapshot.profile_snapshot_json or {})
    profile = dict(profile_snapshot.get("profile") or {})
    items = list(profile_snapshot.get("items") or [])
    school = dict(snapshot.school_fact_snapshot_json or {})
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"实习投递档案 V{int(snapshot.submission_version or 0)}",
        author="Internship Material Authority",
    )
    story = [
        Paragraph("实习投递档案", styles["title"]),
        Paragraph(
            f"本文件由第 {_safe(snapshot.submission_version)} 次不可变投递快照生成；学生后续修改档案不会改变本文件对应的历史证据。",
            styles["muted"],
        ),
        Spacer(1, 6),
        Paragraph("学校身份信息", styles["heading"]),
    ]
    identity_rows = [
        [Paragraph("姓名", styles["body"]), Paragraph(_safe(school.get("realName")), styles["body"]), Paragraph("学号", styles["body"]), Paragraph(_safe(school.get("studentNo")), styles["body"])],
        [Paragraph("学院", styles["body"]), Paragraph(_safe(school.get("collegeName")), styles["body"]), Paragraph("专业", styles["body"]), Paragraph(_safe(school.get("majorName")), styles["body"])],
        [Paragraph("年级", styles["body"]), Paragraph(_safe(school.get("grade")), styles["body"]), Paragraph("班级", styles["body"]), Paragraph(_safe(school.get("className")), styles["body"])],
    ]
    identity = Table(identity_rows, colWidths=[24 * mm, 55 * mm, 24 * mm, 55 * mm], hAlign="LEFT")
    identity.setStyle([
        ("FONTNAME", (0, 0), (-1, -1), _CJK_FONT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    story.extend([identity, Paragraph("实习档案摘要", styles["heading"])])
    summary_rows = [
        ("档案标题", profile.get("headline")),
        ("自我介绍", profile.get("selfIntro")),
        ("个人优势", profile.get("strengths")),
        ("技能标签", profile.get("skillTags") or []),
        ("可到岗日期", profile.get("availableFrom")),
        ("期望地点", profile.get("expectedLocations") or []),
    ]
    for label, value in summary_rows:
        story.append(Paragraph(f"<b>{_safe(label)}</b>　{_safe(value)}", styles["body"]))

    story.append(Paragraph("经历与证明", styles["heading"]))
    if not items:
        story.append(Paragraph("暂无经历或证明材料。", styles["body"]))
    else:
        for index, item in enumerate(items, start=1):
            row = dict(item or {})
            item_type = row.get("itemType") or row.get("type") or "档案项目"
            title = row.get("title") or row.get("name") or f"项目 {index}"
            organization = row.get("organization") or ""
            description = row.get("description") or ""
            verification = row.get("verificationStatus") or row.get("verification_status") or ""
            story.append(Paragraph(f"<b>{index}. {_safe(title)}</b>　[{_safe(item_type)}]", styles["body"]))
            if organization:
                story.append(Paragraph(f"机构/来源：{_safe(organization)}", styles["muted"]))
            if description:
                story.append(Paragraph(_safe(description), styles["body"]))
            if verification:
                story.append(Paragraph(f"核验状态：{_safe(verification)}", styles["muted"]))
            story.append(Spacer(1, 4))

    story.extend([
        Spacer(1, 8),
        Paragraph(f"投递版本：{int(snapshot.submission_version or 0)}　档案版本：{int(snapshot.profile_version or 0)}", styles["muted"]),
        Paragraph(f"证据哈希：{_safe(snapshot.snapshot_hash)}", styles["muted"]),
    ])
    doc.build(story)
    data = buffer.getvalue()
    if not data.startswith(b"%PDF"):
        raise AppException("DATA_CONFLICT", "实习档案 PDF 生成失败", http_status=409)
    return data


def _existing_bound_pdf_in_tx(db, snapshot: InternshipApplicationMaterialSnapshot) -> FileObject | None:
    if not snapshot.generated_profile_pdf_file_id:
        return None
    row = db.scalar(select(FileObject).where(
        FileObject.id == int(snapshot.generated_profile_pdf_file_id),
        FileObject.tenant_id == snapshot.tenant_id,
        FileObject.biz_type == PDF_BIZ_TYPE,
        FileObject.biz_id == str(snapshot.id),
        FileObject.is_deleted.is_(False),
    ))
    binding = db.scalar(select(FileBinding).where(
        FileBinding.tenant_id == snapshot.tenant_id,
        FileBinding.file_id == int(snapshot.generated_profile_pdf_file_id),
        FileBinding.biz_type == PDF_BIZ_TYPE,
        FileBinding.biz_id == str(snapshot.id),
        FileBinding.relation_type == PDF_RELATION_TYPE,
        FileBinding.status == "ACTIVE",
        FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    ))
    if not row or not binding:
        raise AppException("DATA_CONFLICT", "实习档案 PDF 指针与文件绑定不一致", http_status=409)
    scan_status = str(row.scan_status or SCAN_NOT_REQUIRED).upper()
    if not is_downloadable_status(row.status) or scan_status not in READY_SCAN_STATES:
        raise AppException("FILE_NOT_READY", "实习档案 PDF 当前不可用", http_status=409)
    if str(row.mime_type or "").lower() != "application/pdf":
        raise AppException("DATA_CONFLICT", "实习档案 PDF 文件类型异常", http_status=409)
    return row


def ensure_snapshot_profile_pdf_in_tx(db, snapshot: InternshipApplicationMaterialSnapshot) -> FileObject:
    existing = _existing_bound_pdf_in_tx(db, snapshot)
    if existing:
        return existing
    data = render_snapshot_profile_pdf(snapshot)
    meta = file_service.store_bytes(
        data,
        f"internship-application-snapshot-{snapshot.id}-v{snapshot.submission_version}.pdf",
        PDF_BIZ_TYPE,
        "application/pdf",
        biz_id=None,
        user=_SYSTEM_ACTOR,
        visibility="PRIVATE",
        security_level="HIGHLY_SENSITIVE",
        db=db,
    )
    raw_file_id = str(meta.get("fileId") or "")
    if not raw_file_id.isdigit():
        raise AppException("DATA_CONFLICT", "文件中心未返回有效的实习档案 PDF fileId", http_status=409)
    file_id = int(raw_file_id)
    upsert_file_binding(
        raw_file_id,
        biz_type=PDF_BIZ_TYPE,
        biz_id=str(snapshot.id),
        relation_type=PDF_RELATION_TYPE,
        subject_type="BUSINESS_OBJECT",
        subject_id=str(snapshot.id),
        batch_id=str(snapshot.batch_id),
        scope_json={
            "module": "internship",
            "campaignId": str(snapshot.campaign_id),
            "studentId": str(snapshot.student_id),
            "submissionVersion": int(snapshot.submission_version or 0),
        },
        user=_SYSTEM_ACTOR,
        db=db,
    )
    snapshot.generated_profile_pdf_file_id = file_id
    db.flush()
    row = _existing_bound_pdf_in_tx(db, snapshot)
    if not row:
        raise AppException("DATA_CONFLICT", "实习档案 PDF 生成后未建立正式绑定", http_status=409)
    return row


def resolve_enterprise_resume_pdf_in_tx(db, *, context, application_id: int) -> tuple[FileObject, InternshipApplicationMaterialSnapshot]:
    """Authorize enterprise ownership first, then lock the exact snapshot before idempotent generation."""
    application, _position = decision_svc._owned_application_in_tx(
        db, context=context, application_id=application_id, lock=False,
    )
    snapshot = db.scalar(select(InternshipApplicationMaterialSnapshot).where(
        InternshipApplicationMaterialSnapshot.id == application.material_snapshot_id,
        InternshipApplicationMaterialSnapshot.tenant_id == context.tenant_id,
        InternshipApplicationMaterialSnapshot.campaign_id == context.campaign_id,
        InternshipApplicationMaterialSnapshot.student_id == application.student_id,
    ).with_for_update())
    if not snapshot:
        raise not_found("投递材料快照不存在")
    return ensure_snapshot_profile_pdf_in_tx(db, snapshot), snapshot


def materialize_pdf_for_delivery(file_obj: FileObject) -> Path:
    """Fetch the already-authorized object to a local proxy path for sanctioned byte delivery."""
    key = str(file_obj.object_key or file_obj.file_key or "").strip()
    if not key:
        raise not_found("实习档案 PDF 不存在")
    path = get_backend().fetch_local(key)
    if not path or not Path(path).is_file():
        raise not_found("实习档案 PDF 不存在")
    return Path(path)
