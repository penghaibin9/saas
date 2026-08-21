"""SP-E08：就业去向登记表/协议的真实文件生成（不是打印审计留痕）。

问题
────────────────────────────────────────────────────────────
`student_portal/services/employment_service.py::destination_print()` 此前只调用
`common.print_log()` 写一条 PORTAL_PRINT 审计，**没有**生成任何真实文件——用户点
"打印"拿不到可下载的 PDF、没有 fileId、没有内容哈希，审计留痕不能代替文档。

定位
────────────────────────────────────────────────────────────
本模块是**派生文档生成器**：输入 `EmpStudent`（canonical 就业去向事实），输出真实
PDF 并落 File Center（fileId + sha256），走公共 `file_service.store_bytes()` +
`upsert_file_binding()`，不自建第二套文件存储。

复用而非重复生成
────────────────────────────────────────────────────────────
`EmpStudent.destination_document_file_id` / `destination_document_source_version`
记录"上一次生成时对应的事实版本"。事实（`EmpStudent.version`）没变就复用同一份
文件，不用每次点击都重新渲染、新增一条文件记录；事实变了（补充材料、核验通过/
退回）才重新生成——旧文件不删除，只是不再是"当前"指针指向的那份。

诚实原则
────────────────────────────────────────────────────────────
文档内容如实打印当前 `verify_status`（待核验/已核验/已退回），不冒充"未核验"的
声明为"已核验的正式协议"。
"""
from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from sqlalchemy import select

from app.core.exceptions import AppException
from app.models.employment import EmpStudent
from app.models.file import FileBinding, FileObject
from app.modules.employment.services.employment_service import L_DEST, L_VERIFY
from app.services import file_service
from app.services.file_access_service import register_file_resolver, upsert_file_binding
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED

DOC_BIZ_TYPE = "EMPLOYMENT_DESTINATION_DOCUMENT"
DOC_RELATION_TYPE = "GENERATED_REGISTRATION_FORM"
_SYSTEM_ACTOR = {"userType": "SYSTEM", "realName": "就业去向登记系统"}
_CJK_FONT = "STSong-Light"


@register_file_resolver(DOC_BIZ_TYPE)
def _employment_destination_document_resolver(db, file_obj, bindings, user, action) -> bool:
    """本人 + 具备就业模块权限的教职工可读；不做全局文件管理员放行。"""
    if db is None:
        return False
    from app.core.permissions import has_permission
    from app.services.mobile_student_service import resolve_student

    active = [b for b in bindings if not b.is_deleted and b.status == "ACTIVE" and b.is_current
             and str(b.biz_type or "").upper() == DOC_BIZ_TYPE]
    if not active:
        return False
    emp_id = active[0].biz_id
    if not str(emp_id or "").isdigit():
        return False
    emp = db.scalar(select(EmpStudent).where(
        EmpStudent.id == int(emp_id), EmpStudent.tenant_id == int(file_obj.tenant_id),
        EmpStudent.is_deleted.is_(False)))
    if not emp:
        return False
    if has_permission(user, "employment.student.view") or has_permission(user, "*"):
        return True
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        return False
    # 学生只能读自己的登记表——用与 departure_projection_service 同一条 canonical 身份
    # 解析（token.studentId 优先，姓名兜底仅唯一命中），不额外维护第二条更弱的识别路径。
    student = resolve_student(db, user)
    return bool(student and emp.student_id and int(student.id) == int(emp.student_id))


def _styles():
    try:
        pdfmetrics.getFont(_CJK_FONT)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(_CJK_FONT))
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("EmpDestTitle", parent=base["Title"], fontName=_CJK_FONT,
                                fontSize=17, leading=22, spaceAfter=10),
        "body": ParagraphStyle("EmpDestBody", parent=base["BodyText"], fontName=_CJK_FONT,
                               fontSize=10.5, leading=17),
        "muted": ParagraphStyle("EmpDestMuted", parent=base["BodyText"], fontName=_CJK_FONT,
                                fontSize=8, leading=12),
    }


def _safe(value) -> str:
    if value in (None, ""):
        return "—"
    return escape(str(value))


def render_destination_document_pdf(emp: EmpStudent) -> bytes:
    styles = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"就业去向登记表 V{int(emp.version or 0)}", author="Employment Destination Authority",
    )
    dest_label = L_DEST.get(str(emp.destination_type or "").upper(), emp.destination_type or "—")
    verify_label = L_VERIFY.get(str(emp.verify_status or "").upper(), emp.verify_status or "—")
    story = [
        Paragraph("就业去向登记表", styles["title"]),
        Paragraph(
            f"本文件由系统按第 {_safe(emp.version)} 版就业去向事实自动生成，"
            "内容以生成时刻的登记与核验状态为准，学生后续修改不会改变本文件对应的历史记录。",
            styles["muted"],
        ),
        Spacer(1, 6),
    ]
    rows = [
        [Paragraph("姓名", styles["body"]), Paragraph(_safe(emp.name), styles["body"]),
         Paragraph("学号", styles["body"]), Paragraph(_safe(emp.student_no), styles["body"])],
        [Paragraph("学院", styles["body"]), Paragraph(_safe(emp.college_name), styles["body"]),
         Paragraph("专业", styles["body"]), Paragraph(_safe(emp.major_name), styles["body"])],
        [Paragraph("去向类型", styles["body"]), Paragraph(_safe(dest_label), styles["body"]),
         Paragraph("核验状态", styles["body"]), Paragraph(_safe(verify_label), styles["body"])],
        [Paragraph("单位/去向", styles["body"]), Paragraph(_safe(emp.company_name), styles["body"]),
         Paragraph("岗位", styles["body"]), Paragraph(_safe(emp.job_title), styles["body"])],
        [Paragraph("签约日期", styles["body"]), Paragraph(_safe(emp.sign_date), styles["body"]),
         Paragraph("", styles["body"]), Paragraph("", styles["body"])],
    ]
    table = Table(rows, colWidths=[26 * mm, 58 * mm, 26 * mm, 58 * mm], hAlign="LEFT")
    table.setStyle([
        ("FONTNAME", (0, 0), (-1, -1), _CJK_FONT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, "#cccccc"),
    ])
    story.append(table)
    story.append(Spacer(1, 10))
    if verify_label != "已核验":
        story.append(Paragraph(
            f"注意：本记录当前核验状态为「{_safe(verify_label)}」，不代表已经通过学校正式核验，"
            "不得作为已核验的就业证明使用。", styles["muted"]))
    story.append(Paragraph(f"生成事实版本：{_safe(emp.version)}", styles["muted"]))
    doc.build(story)
    data = buf.getvalue()
    if not data.startswith(b"%PDF"):
        raise AppException("DATA_CONFLICT", "就业去向登记表生成失败", http_status=409)
    return data


def _existing_bound_doc_in_tx(db, emp: EmpStudent) -> FileObject | None:
    if emp.destination_document_file_id is None:
        return None
    # 注意：不能用 `emp.destination_document_source_version or -1` 判等——version 0 是
    # 每个新建对象的合法起始版本，`0 or -1` 会被 Python 短路成 -1，把"确实生成于 v0"
    # 误判成"指针缺失"，导致刚生成完的文件立刻被判定为过期。显式判 None。
    if emp.destination_document_source_version is None \
            or int(emp.destination_document_source_version) != int(emp.version or 0):
        # 事实已经前进，旧指针对应的不是当前版本，必须重新生成，不得复用过期文件。
        return None
    row = db.scalar(select(FileObject).where(
        FileObject.id == int(emp.destination_document_file_id),
        FileObject.tenant_id == emp.tenant_id,
        FileObject.biz_type == DOC_BIZ_TYPE,
        FileObject.biz_id == str(emp.id),
        FileObject.is_deleted.is_(False),
    ))
    binding = db.scalar(select(FileBinding).where(
        FileBinding.tenant_id == emp.tenant_id,
        FileBinding.file_id == int(emp.destination_document_file_id),
        FileBinding.biz_type == DOC_BIZ_TYPE,
        FileBinding.biz_id == str(emp.id),
        FileBinding.relation_type == DOC_RELATION_TYPE,
        FileBinding.status == "ACTIVE",
        FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    ))
    if not row or not binding:
        return None
    scan_status = str(row.scan_status or SCAN_NOT_REQUIRED).upper()
    if not is_downloadable_status(row.status) or scan_status not in READY_SCAN_STATES:
        return None
    return row


def ensure_destination_document_in_tx(db, emp: EmpStudent) -> FileObject:
    """幂等生成/复用：同一事实版本只产生一份文件；事实变化后重新生成。"""
    existing = _existing_bound_doc_in_tx(db, emp)
    if existing:
        return existing
    data = render_destination_document_pdf(emp)
    meta = file_service.store_bytes(
        data, f"employment-destination-{emp.id}-v{int(emp.version or 0)}.pdf",
        DOC_BIZ_TYPE, "application/pdf",
        biz_id=None, user=_SYSTEM_ACTOR, visibility="PRIVATE", security_level="NORMAL", db=db,
    )
    raw_file_id = str(meta.get("fileId") or "")
    if not raw_file_id.isdigit():
        raise AppException("DATA_CONFLICT", "文件中心未返回有效的就业去向登记表 fileId", http_status=409)
    file_id = int(raw_file_id)
    upsert_file_binding(
        raw_file_id, biz_type=DOC_BIZ_TYPE, biz_id=str(emp.id),
        relation_type=DOC_RELATION_TYPE, subject_type="BUSINESS_OBJECT", subject_id=str(emp.id),
        version_no=int(emp.version or 0),
        scope_json={"module": "employment", "empStudentId": str(emp.id),
                   "studentId": str(emp.student_id or ""), "sourceVersion": int(emp.version or 0)},
        user=_SYSTEM_ACTOR, db=db,
    )
    emp.destination_document_file_id = file_id
    emp.destination_document_source_version = int(emp.version or 0)
    db.flush()
    row = _existing_bound_doc_in_tx(db, emp)
    if not row:
        raise AppException("DATA_CONFLICT", "就业去向登记表生成后未建立正式绑定", http_status=409)
    return row
