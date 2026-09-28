"""Yiyang C08/G17 formal printable PDF authority.

Generated PDFs are derived artifacts. Authoritative facts remain in the internship record,
approved enterprise evaluation, published final score and approved immutable summary version.
A changed source snapshot creates a new document version; old PDFs are never overwritten.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (
    College,
    InternshipCheckin,
    InternshipEnterpriseEval,
    InternshipFinalScore,
    InternshipMakeup,
    InternshipFormalDocument,
    InternshipProcessReport,
    InternshipReportReview,
    InternshipReportVersion,
    Major,
    SchoolClass,
    StudentProfile,
    Tenant,
)
from app.models.file import FileObject
from app.modules.internship.services.internship_audit_service import add_audit
from app.modules.internship.services.internship_scope import assert_internship_record_scope
from app.services import file_service
from app.services.db_service import _tid, session

PDF_BIZ_TYPE = "INTERNSHIP_FORMAL_DOCUMENT"
_CJK_FONT = "STSong-Light"

SUPPORTED_DOCUMENTS = {
    "ENTERPRISE_EVALUATION": "企业实习鉴定表",
    "INTERNSHIP_CERTIFICATE": "学生实习证明",
    "FINAL_ASSESSMENT": "实习考核成绩表",
    "SUMMARY_REPORT": "实习总结报告",
}


def normalize_document_type(value: str) -> str:
    code = str(value or "").strip().upper()
    if code not in SUPPORTED_DOCUMENTS:
        raise AppException(
            "VALIDATION_ERROR",
            "documentType 必须是 ENTERPRISE_EVALUATION/INTERNSHIP_CERTIFICATE/"
            "FINAL_ASSESSMENT/SUMMARY_REPORT",
        )
    return code


def source_hash(snapshot: dict) -> str:
    raw = json.dumps(
        snapshot or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def _iso(value) -> str:
    return value.isoformat() if value else ""


def _safe(value) -> str:
    if value in (None, ""):
        return "—"
    return escape(str(value)).replace("\n", "<br/>")


def _org_name(db, model, ident, attr) -> str:
    if not ident:
        return ""
    row = db.get(model, int(ident))
    if not row or getattr(row, "tenant_id", _tid()) != _tid() or row.is_deleted:
        return ""
    return str(getattr(row, attr, "") or "")


def _base_snapshot(db, record, student, document_type: str) -> dict:
    tenant = db.get(Tenant, _tid())
    return {
        "schemaVersion": 1,
        "documentType": document_type,
        "school": {
            "tenantId": str(_tid()),
            "schoolName": str(getattr(tenant, "school_name", "") or ""),
        },
        "internship": {
            "id": str(record.id),
            "batchId": str(record.batch_id or ""),
            "status": record.status,
            "enterpriseName": record.enterprise_name or "",
            "positionName": record.position_name or "",
            "advisorName": record.advisor_name or "",
            "enterpriseMentorName": record.enterprise_mentor_name or "",
            "startDate": _iso(record.intern_start_date),
            "endDate": _iso(record.intern_end_date),
        },
        "student": {
            "id": str(student.id),
            "studentNo": student.student_no,
            "realName": student.real_name,
            "grade": student.grade or "",
            "collegeName": _org_name(db, College, student.college_id, "college_name"),
            "majorName": _org_name(db, Major, student.major_id, "major_name"),
            "className": _org_name(db, SchoolClass, student.class_id, "class_name"),
        },
    }


def _enterprise_evaluation(db, record) -> dict:
    query = select(InternshipEnterpriseEval).where(
        InternshipEnterpriseEval.tenant_id == _tid(),
        InternshipEnterpriseEval.internship_id == record.id,
        InternshipEnterpriseEval.student_id == record.student_id,
        InternshipEnterpriseEval.school_review_status == "APPROVED",
        InternshipEnterpriseEval.is_deleted.is_(False),
    )
    if record.enterprise_id:
        query = query.where(InternshipEnterpriseEval.enterprise_id == record.enterprise_id)
    if record.position_id:
        query = query.where(InternshipEnterpriseEval.position_id == record.position_id)
    row = db.scalars(query.order_by(
        InternshipEnterpriseEval.reviewed_at.desc(),
        InternshipEnterpriseEval.id.desc(),
    )).first()
    if not row:
        raise AppException(
            "DATA_CONFLICT", "缺少当前岗位已通过学校审核的企业评价，不能生成正式企业鉴定表",
            http_status=409,
        )
    scores = {
        "attendance": int(row.attendance_score or 0),
        "skill": int(row.skill_score or 0),
        "attitude": int(row.attitude_score or 0),
        "collaboration": int(row.collaboration_score or 0),
        "safety": int(row.safety_score or 0),
    }
    return {
        "evaluationId": str(row.id),
        "mentorName": row.mentor_name or "",
        "scores": scores,
        "averageScore": round(sum(scores.values()) / 5, 1),
        "overallComment": row.overall_comment or "",
        "recommendHire": bool(row.recommend_hire),
        "sourceType": row.source_type or row.source or "LEGACY_UNKNOWN",
        "sourceFileId": row.source_file_id or row.file_id or "",
        "reviewedByName": row.reviewed_by_name or "",
        "reviewedAt": _iso(row.reviewed_at),
    }


def _certificate_fact(db, record) -> dict:
    if record.status not in {"ASSESSING", "ARCHIVED"}:
        raise AppException(
            "DATA_CONFLICT", "学生尚未进入考核或归档阶段，不能生成正式实习证明",
            http_status=409,
        )
    if not record.enterprise_name or not record.position_name:
        raise AppException(
            "DATA_CONFLICT", "实习单位或岗位事实缺失，不能生成正式实习证明",
            http_status=409,
        )
    if not record.intern_start_date or not record.intern_end_date:
        raise AppException(
            "DATA_CONFLICT", "实习起止日期缺失，不能生成正式实习证明",
            http_status=409,
        )
    if record.intern_end_date > datetime.utcnow():
        raise AppException(
            "DATA_CONFLICT", "实习尚未结束，不能提前生成正式实习证明",
            http_status=409,
        )
    checkin_days = set(db.scalars(select(InternshipCheckin.checkin_date).where(
        InternshipCheckin.tenant_id == _tid(),
        InternshipCheckin.internship_id == record.id,
        InternshipCheckin.is_deleted.is_(False),
    )).all())
    makeup_days = set(db.scalars(select(InternshipMakeup.checkin_date).where(
        InternshipMakeup.tenant_id == _tid(),
        InternshipMakeup.internship_id == record.id,
        InternshipMakeup.status == "APPROVED",
        InternshipMakeup.is_deleted.is_(False),
    )).all())
    attendance_days = len({str(day) for day in checkin_days.union(makeup_days) if day})
    return {
        "status": record.status,
        "enterpriseName": record.enterprise_name,
        "positionName": record.position_name,
        "startDate": _iso(record.intern_start_date),
        "endDate": _iso(record.intern_end_date),
        "attendanceDays": attendance_days,
    }


def _final_assessment(db, record) -> dict:
    row = db.scalar(select(InternshipFinalScore).where(
        InternshipFinalScore.tenant_id == _tid(),
        InternshipFinalScore.internship_id == record.id,
        InternshipFinalScore.student_id == record.student_id,
        InternshipFinalScore.status.in_(("PUBLISHED", "ARCHIVED")),
        InternshipFinalScore.incomplete.is_(False),
        InternshipFinalScore.is_deleted.is_(False),
    ).order_by(InternshipFinalScore.id.desc()))
    if not row:
        raise AppException(
            "DATA_CONFLICT", "缺少已发布且完整的最终成绩，不能生成正式考核成绩表",
            http_status=409,
        )
    return {
        "scoreId": str(row.id),
        "status": row.status,
        "checkinScore": row.checkin_score,
        "weeklyScore": row.weekly_score,
        "monthlyScore": row.monthly_score,
        "enterpriseScore": row.enterprise_score,
        "schoolScore": row.school_score,
        "totalScore": float(row.total_score) if row.total_score is not None else None,
        "passLine": float(row.pass_line or 0),
        "passed": bool(row.is_pass),
        "publishedByName": row.published_by_name or "",
        "publishedAt": _iso(row.published_at),
    }


def _summary_report(db, record) -> dict:
    report = db.scalars(select(InternshipProcessReport).where(
        InternshipProcessReport.tenant_id == _tid(),
        InternshipProcessReport.internship_id == record.id,
        InternshipProcessReport.report_type == "SUMMARY",
        InternshipProcessReport.status == "APPROVED",
        InternshipProcessReport.is_deleted.is_(False),
    ).order_by(InternshipProcessReport.id.desc())).first()
    if not report:
        raise AppException(
            "DATA_CONFLICT", "缺少已通过批阅的实习总结，不能生成正式总结报告",
            http_status=409,
        )
    snap = db.scalars(select(InternshipReportVersion).where(
        InternshipReportVersion.tenant_id == _tid(),
        InternshipReportVersion.report_kind == "PROCESS",
        InternshipReportVersion.report_id == report.id,
        InternshipReportVersion.report_type == "SUMMARY",
    ).order_by(
        InternshipReportVersion.version_no.desc(),
        InternshipReportVersion.id.desc(),
    )).first()
    if not snap:
        raise AppException(
            "DATA_CONFLICT", "实习总结缺少不可变提交版本，不能生成正式总结报告",
            http_status=409,
        )
    review = db.scalar(select(InternshipReportReview).where(
        InternshipReportReview.tenant_id == _tid(),
        InternshipReportReview.report_version_id == snap.id,
        InternshipReportReview.action == "APPROVE",
    ))
    if not review:
        raise AppException(
            "DATA_CONFLICT", "实习总结当前版本缺少正式通过批阅事实",
            http_status=409,
        )
    return {
        "reportId": str(report.id),
        "reportVersionId": str(snap.id),
        "versionNo": int(snap.version_no),
        "wordCount": int(snap.word_count or 0),
        "content": str((snap.content_json or {}).get("content") or ""),
        "attachments": list(snap.attachment_meta_json or []),
        "ratingLevel": int(review.rating_level) if review.rating_level is not None else None,
        "summaryScore": float(review.summary_score) if review.summary_score is not None else None,
        "reviewComment": review.comment or "",
        "reviewerName": review.reviewer_name or "",
        "reviewedAt": _iso(review.reviewed_at),
        "submittedAt": _iso(snap.submitted_at),
    }


def build_source_snapshot(db, record, document_type: str) -> dict:
    document_type = normalize_document_type(document_type)
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == record.student_id,
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ))
    if not student:
        raise not_found("实习关联学生档案不存在")
    data = _base_snapshot(db, record, student, document_type)
    if document_type == "ENTERPRISE_EVALUATION":
        data["enterpriseEvaluation"] = _enterprise_evaluation(db, record)
    elif document_type == "INTERNSHIP_CERTIFICATE":
        data["completion"] = _certificate_fact(db, record)
    elif document_type == "FINAL_ASSESSMENT":
        data["finalAssessment"] = _final_assessment(db, record)
    else:
        data["summaryReport"] = _summary_report(db, record)
    return data


def _styles():
    try:
        pdfmetrics.getFont(_CJK_FONT)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(_CJK_FONT))
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "FormalTitle", parent=base["Title"], fontName=_CJK_FONT,
            fontSize=18, leading=25, spaceAfter=10,
        ),
        "body": ParagraphStyle(
            "FormalBody", parent=base["BodyText"], fontName=_CJK_FONT,
            fontSize=10, leading=17,
        ),
        "small": ParagraphStyle(
            "FormalSmall", parent=base["BodyText"], fontName=_CJK_FONT,
            fontSize=8, leading=12,
        ),
    }


def _identity_table(snapshot: dict, styles: dict):
    student = snapshot["student"]
    internship = snapshot["internship"]
    rows = [
        ["姓名", student["realName"], "学号", student["studentNo"]],
        ["学院", student["collegeName"], "专业", student["majorName"]],
        ["班级", student["className"], "年级", student["grade"]],
        ["实习单位", internship["enterpriseName"], "岗位", internship["positionName"]],
        ["开始日期", internship["startDate"], "结束日期", internship["endDate"]],
    ]
    return Table(
        [[Paragraph(_safe(cell), styles["body"]) for cell in row] for row in rows],
        colWidths=[24 * mm, 55 * mm, 24 * mm, 55 * mm],
        hAlign="LEFT",
    )


def render_formal_pdf(document_type: str, snapshot: dict, *, document_version: int = 1) -> bytes:
    document_type = normalize_document_type(document_type)
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=SUPPORTED_DOCUMENTS[document_type],
        author=snapshot.get("school", {}).get("schoolName") or "岗位实习管理平台",
    )
    title = SUPPORTED_DOCUMENTS[document_type]
    story = [
        Paragraph(_safe(snapshot.get("school", {}).get("schoolName") or "学校"), styles["body"]),
        Paragraph(title, styles["title"]),
        _identity_table(snapshot, styles),
        Spacer(1, 10),
    ]
    if document_type == "ENTERPRISE_EVALUATION":
        fact = snapshot["enterpriseEvaluation"]
        story.extend([
            Paragraph(f"企业导师：{_safe(fact['mentorName'])}", styles["body"]),
            Paragraph(
                "五项评分：出勤 {attendance} / 技能 {skill} / 态度 {attitude} / "
                "协作 {collaboration} / 安全纪律 {safety}，平均 {avg}".format(
                    **fact["scores"], avg=fact["averageScore"],
                ),
                styles["body"],
            ),
            Paragraph(f"综合评语：{_safe(fact['overallComment'])}", styles["body"]),
            Paragraph(f"建议录用：{'是' if fact['recommendHire'] else '否'}", styles["body"]),
            Paragraph(
                f"学校审核：{_safe(fact['reviewedByName'])} {_safe(fact['reviewedAt'])}",
                styles["small"],
            ),
            Spacer(1, 18),
            Paragraph("实习单位鉴定意见/签章：____________________________", styles["body"]),
            Spacer(1, 14),
            Paragraph("企业导师签字：________________　日期：____年__月__日", styles["body"]),
        ])
    elif document_type == "INTERNSHIP_CERTIFICATE":
        fact = snapshot["completion"]
        story.extend([
            Paragraph(
                f"兹证明 {_safe(snapshot['student']['realName'])}（学号 {_safe(snapshot['student']['studentNo'])}）"
                f"于 {_safe(fact['startDate'])} 至 {_safe(fact['endDate'])} 在 "
                f"{_safe(fact['enterpriseName'])} 完成岗位实习，实习岗位为 {_safe(fact['positionName'])}。",
                styles["body"],
            ),
            Paragraph(
                f"系统按正式签到与已批准补签事实自动计算：实习考勤签到天数为 "
                f"{_safe(fact.get('attendanceDays', 0))} 天。",
                styles["body"],
            ),
            Spacer(1, 18),
            Paragraph("实习单位签章：____________________　日期：____年__月__日", styles["body"]),
            Spacer(1, 14),
            Paragraph("学校审核/盖章：____________________　日期：____年__月__日", styles["body"]),
        ])
    elif document_type == "FINAL_ASSESSMENT":
        fact = snapshot["finalAssessment"]
        story.extend([
            Paragraph(
                f"最终成绩：{_safe(fact['totalScore'])} 分；及格线：{_safe(fact['passLine'])}；"
                f"结论：{'通过' if fact['passed'] else '未通过'}。",
                styles["body"],
            ),
            Paragraph(
                f"分项：打卡 {fact['checkinScore']} / 周报 {fact['weeklyScore']} / "
                f"月报总结 {fact['monthlyScore']} / 企业评价 {fact['enterpriseScore']} / "
                f"学校评价 {fact['schoolScore']}",
                styles["body"],
            ),
            Paragraph(
                f"发布人：{_safe(fact['publishedByName'])}；发布时间：{_safe(fact['publishedAt'])}",
                styles["small"],
            ),
        ])
    else:
        fact = snapshot["summaryReport"]
        story.extend([
            Paragraph(
                f"总结评分：{_safe(fact['summaryScore'])}；五级评价：{_safe(fact['ratingLevel'])}",
                styles["body"],
            ),
            Paragraph(f"批阅意见：{_safe(fact['reviewComment'])}", styles["body"]),
            Spacer(1, 6),
            Paragraph(_safe(fact["content"]), styles["body"]),
        ])
    story.extend([
        Spacer(1, 12),
        Paragraph(
            f"文书版本 V{int(document_version)}　来源事实 SHA-256：{_safe(source_hash(snapshot))}",
            styles["small"],
        ),
        Paragraph("本 PDF 为系统根据已审核/已发布正式业务事实生成的派生文书；历史版本不覆盖。", styles["small"]),
    ])
    doc.build(story)
    data = buffer.getvalue()
    if not data.startswith(b"%PDF"):
        raise AppException("DATA_CONFLICT", "正式 PDF 生成失败", http_status=409)
    return data


def _view(row: InternshipFormalDocument) -> dict:
    return {
        "id": str(row.id),
        "internshipId": str(row.internship_id),
        "studentId": str(row.student_id),
        "batchId": str(row.batch_id),
        "documentType": row.document_type,
        "documentTypeLabel": SUPPORTED_DOCUMENTS.get(row.document_type, row.document_type),
        "documentVersion": int(row.document_version or 0),
        "sourceHash": row.source_hash,
        "fileId": row.file_id or "",
        "fileSha256": row.file_sha256 or "",
        "status": row.status,
        "generatedByName": row.generated_by_name or "",
        "generatedAt": _iso(row.generated_at),
    }


def list_documents(user: dict, internship_id) -> list[dict]:
    with session() as db:
        record = assert_internship_record_scope(db, internship_id, user, "查看正式文书")
        rows = db.scalars(select(InternshipFormalDocument).where(
            InternshipFormalDocument.tenant_id == _tid(),
            InternshipFormalDocument.internship_id == record.id,
            InternshipFormalDocument.is_deleted.is_(False),
        ).order_by(
            InternshipFormalDocument.document_type,
            InternshipFormalDocument.document_version.desc(),
        )).all()
        return [_view(row) for row in rows]


def generate(user: dict, body: dict) -> dict:
    payload = body or {}
    document_type = normalize_document_type(payload.get("documentType"))
    internship_id = payload.get("internshipId")
    if internship_id in (None, ""):
        raise AppException("VALIDATION_ERROR", "internshipId 必填")
    with session() as db:
        record = assert_internship_record_scope(
            db, internship_id, user, "生成正式文书", lock=True,
        )
        if not record.batch_id:
            raise AppException("DATA_CONFLICT", "实习记录缺少批次，不能生成正式文书", http_status=409)
        snapshot = build_source_snapshot(db, record, document_type)
        digest = source_hash(snapshot)
        latest = db.scalars(select(InternshipFormalDocument).where(
            InternshipFormalDocument.tenant_id == _tid(),
            InternshipFormalDocument.internship_id == record.id,
            InternshipFormalDocument.document_type == document_type,
            InternshipFormalDocument.is_deleted.is_(False),
        ).order_by(
            InternshipFormalDocument.document_version.desc(),
            InternshipFormalDocument.id.desc(),
        ).with_for_update()).first()
        if latest and latest.source_hash == digest and latest.file_id and latest.status == "GENERATED":
            return {**_view(latest), "reused": True}

        next_version = int(latest.document_version or 0) + 1 if latest else 1
        row = InternshipFormalDocument(
            tenant_id=_tid(),
            internship_id=record.id,
            student_id=record.student_id,
            batch_id=record.batch_id,
            document_type=document_type,
            document_version=next_version,
            source_hash=digest,
            source_snapshot_json=snapshot,
            generated_by_user_id=str((user or {}).get("userId") or "") or None,
            generated_by_name=(user or {}).get("realName") or "系统",
            generated_at=datetime.utcnow(),
            status="GENERATED",
        )
        db.add(row)
        db.flush()
        pdf = render_formal_pdf(document_type, snapshot, document_version=next_version)
        meta = file_service.store_bytes(
            pdf,
            f"internship-{record.id}-{document_type.lower()}-v{next_version}.pdf",
            PDF_BIZ_TYPE,
            "application/pdf",
            biz_id=str(row.id),
            user=user,
            visibility="BIZ_SCOPED",
            security_level="SENSITIVE",
            db=db,
        )
        row.file_id = str(meta.get("fileId") or "")
        row.file_sha256 = str(meta.get("sha256") or sha256(pdf).hexdigest())
        if latest and latest.status == "GENERATED":
            latest.status = "SUPERSEDED"
        add_audit(
            db,
            target_type="FORMAL_DOCUMENT",
            target_id=row.id,
            action="FORMAL_DOCUMENT_GENERATE",
            user=user,
            batch_id=record.batch_id,
            internship_id=record.id,
            new_version=next_version,
            file_ids=[row.file_id] if row.file_id else [],
            detail={
                "documentType": document_type,
                "sourceHash": digest,
                "documentVersion": next_version,
            },
        )
        db.commit()
        return {**_view(row), "reused": False}


def resolve_download(user: dict, document_id):
    with session() as db:
        try:
            did = int(document_id)
        except (TypeError, ValueError):
            raise not_found("正式文书不存在") from None
        row = db.scalar(select(InternshipFormalDocument).where(
            InternshipFormalDocument.id == did,
            InternshipFormalDocument.tenant_id == _tid(),
            InternshipFormalDocument.is_deleted.is_(False),
        ))
        if not row:
            raise not_found("正式文书不存在")
        assert_internship_record_scope(db, row.internship_id, user, "下载正式文书")
        if not row.file_id:
            raise not_found("正式文书文件不存在")
        file_row = db.scalar(select(FileObject).where(
            FileObject.id == int(row.file_id),
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        ))
        if not file_row or str(file_row.mime_type or "").lower() != "application/pdf":
            raise not_found("正式文书文件不存在")
        resolved = file_service.resolve_download(row.file_id, user=user)
        if not resolved:
            raise not_found("正式文书文件不存在")
        path, _stored_name = resolved
        return path, f"internship-{row.internship_id}-{row.document_type.lower()}-v{row.document_version}.pdf"
