"""Single structured-snapshot implementation for graduation evidence."""
from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from typing import Any

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.core.exceptions import not_found
from app.models import (
    GraduationDefenseScore,
    GraduationGrade,
    GraduationGuidance,
    GraduationMidterm,
    GraduationPlagiarismCheck,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationTaskBook,
)
from app.models.file import FileBinding
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services import file_service
from app.services.db_service import _iso, _tid, session

from .command_service import register_generated_snapshot
from .definitions import MODULE_CODE, SNAPSHOT_GENERATOR_VERSION, SNAPSHOT_SCHEMA_VERSION
from .rule_service import rule_item


SYSTEM_SNAPSHOT_CODES = {
    "TASKBOOK", "PROPOSAL_REPORT", "PROPOSAL_DEFENSE", "GUIDANCE_RECORD",
    "MIDTERM_REPORT", "PLAGIARISM_REPORT", "REVIEW_ATTACHMENT",
    "DEFENSE_RECORD", "GRADE_MATERIAL",
}


@dataclass(frozen=True)
class SnapshotSpec:
    material_code: str
    title: str
    source_record_type: str
    source_record_id: str
    fields: tuple[tuple[str, Any], ...]
    approved: bool = True

    def source_payload(self, gd_student_id: int) -> dict:
        return {
            "snapshotSchemaVersion": SNAPSHOT_SCHEMA_VERSION,
            "generatorVersion": SNAPSHOT_GENERATOR_VERSION,
            "gdStudentId": str(gd_student_id),
            "materialCode": self.material_code,
            "sourceRecordType": self.source_record_type,
            "sourceRecordId": self.source_record_id,
            "approved": self.approved,
            "fields": [[label, value] for label, value in self.fields],
        }

    def source_hash(self, gd_student_id: int) -> str:
        encoded = json.dumps(
            self.source_payload(gd_student_id), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _collect(gd_student_id: int, user: dict) -> tuple[dict, list[SnapshotSpec]]:
    """Phase 1: collect a stable read snapshot without material-domain writes."""
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student:
            raise not_found("毕业设计学生不存在")
        assert_student_access(db, student, "structured.snapshot")
        specs: list[SnapshotSpec] = []
        common = (("学生", student.name), ("学号", student.student_no or ""), ("题目", student.topic_title or ""))

        taskbook = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == int(student.id),
            GraduationTaskBook.status == "CONFIRMED", GraduationTaskBook.is_deleted.is_(False),
        ).order_by(GraduationTaskBook.id.desc())).first()
        if taskbook:
            specs.append(SnapshotSpec(
                "TASKBOOK", "毕业设计任务书", "TASKBOOK", str(taskbook.id),
                common + (("任务目标", taskbook.objective), ("任务内容", taskbook.content),
                          ("进度计划", taskbook.progress_plan), ("成果要求", taskbook.outcome_requirement),
                          ("业务版本", taskbook.taskbook_version), ("确认时间", _iso(taskbook.confirmed_at))),
            ))

        proposal = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == int(student.id),
            GraduationProposal.status == "APPROVED", GraduationProposal.is_deleted.is_(False),
        ).order_by(GraduationProposal.id.desc())).first()
        if proposal:
            specs.append(SnapshotSpec(
                "PROPOSAL_REPORT", "毕业设计开题报告", "PROPOSAL", str(proposal.id),
                common + (("选题背景", proposal.background), ("研究方案与进度", proposal.plan),
                          ("预期成果", proposal.outcome), ("业务版本", proposal.version),
                          ("提交时间", _iso(proposal.submit_at)), ("审核时间", _iso(proposal.review_time))),
            ))
            if proposal.defense_result:
                specs.append(SnapshotSpec(
                    "PROPOSAL_DEFENSE", "开题答辩记录", "PROPOSAL_DEFENSE", str(proposal.id),
                    common + (("答辩结果", proposal.defense_result), ("答辩评语", proposal.defense_comment),
                              ("答辩时间", _iso(proposal.defense_at))),
                    approved=proposal.defense_result == "PASS",
                ))

        guidance = list(db.scalars(select(GraduationGuidance).where(
            GraduationGuidance.tenant_id == _tid(), GraduationGuidance.gd_student_id == int(student.id),
            GraduationGuidance.void_reason.is_(None), GraduationGuidance.is_deleted.is_(False),
        ).order_by(GraduationGuidance.guidance_date, GraduationGuidance.id)).all())
        if guidance:
            fields = list(common)
            for index, row in enumerate(guidance, start=1):
                fields.extend(((f"第{index}次指导时间", _iso(row.guidance_date)),
                               (f"第{index}次指导方式", row.method),
                               (f"第{index}次指导内容", row.content),
                               (f"第{index}次发现问题", row.issues)))
            specs.append(SnapshotSpec(
                "GUIDANCE_RECORD", "毕业设计指导记录汇总", "GUIDANCE", str(guidance[-1].id), tuple(fields),
            ))

        midterm = db.scalars(select(GraduationMidterm).where(
            GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == int(student.id),
            GraduationMidterm.status.in_(("CHECKED_PASS", "RECTIFIED_PASS")),
            GraduationMidterm.is_deleted.is_(False),
        ).order_by(GraduationMidterm.id.desc())).first()
        if midterm:
            specs.append(SnapshotSpec(
                "MIDTERM_REPORT", "毕业设计中期检查记录", "MIDTERM", str(midterm.id),
                common + (("检查结论", midterm.conclusion), ("检查意见", midterm.check_comment),
                          ("检查人", midterm.check_by), ("检查时间", _iso(midterm.checked_at)),
                          ("整改内容", midterm.rectify_content), ("复核意见", midterm.review_comment),
                          ("复核时间", _iso(midterm.reviewed_at))),
            ))

        plagiarism = db.scalars(select(GraduationPlagiarismCheck).where(
            GraduationPlagiarismCheck.tenant_id == _tid(),
            GraduationPlagiarismCheck.gd_student_id == int(student.id),
            GraduationPlagiarismCheck.status == "DONE", GraduationPlagiarismCheck.is_deleted.is_(False),
        ).order_by(GraduationPlagiarismCheck.id.desc())).first()
        if plagiarism:
            approved = not plagiarism.over_threshold or plagiarism.dispute_status == "APPROVED"
            specs.append(SnapshotSpec(
                "PLAGIARISM_REPORT", "毕业设计查重结果", "PLAGIARISM", str(plagiarism.id),
                common + (("重复率", plagiarism.rate), ("阈值", plagiarism.threshold),
                          ("是否超标", "是" if plagiarism.over_threshold else "否"),
                          ("特例状态", plagiarism.dispute_status), ("提交时间", _iso(plagiarism.submit_at))),
                approved=approved,
            ))

        reviews = list(db.scalars(select(GraduationReview).where(
            GraduationReview.tenant_id == _tid(), GraduationReview.gd_student_id == int(student.id),
            GraduationReview.status == "COMPLETED", GraduationReview.is_deleted.is_(False),
        ).order_by(GraduationReview.id)).all())
        if reviews:
            fields = list(common)
            for index, row in enumerate(reviews, start=1):
                fields.extend(((f"评阅人{index}", row.reviewer_name), (f"评阅分{index}", row.score),
                               (f"评阅意见{index}", row.opinion), (f"评阅时间{index}", _iso(row.reviewed_at))))
            specs.append(SnapshotSpec(
                "REVIEW_ATTACHMENT", "毕业设计评阅意见汇总", "REVIEW", str(reviews[-1].id), tuple(fields),
            ))

        scores = list(db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == int(student.id),
            GraduationDefenseScore.status == "CONFIRMED", GraduationDefenseScore.is_deleted.is_(False),
        ).order_by(GraduationDefenseScore.round_no, GraduationDefenseScore.id)).all())
        if scores:
            fields = list(common) + [("答辩组", student.defense_group)]
            for index, row in enumerate(scores, start=1):
                fields.extend(((f"评委{index}", row.judge_name), (f"分数{index}", row.score),
                               (f"评语{index}", row.comment), (f"轮次{index}", row.round_no)))
            specs.append(SnapshotSpec(
                "DEFENSE_RECORD", "毕业设计答辩记录", "DEFENSE_SCORE", str(scores[-1].id), tuple(fields),
            ))

        grade = db.scalars(select(GraduationGrade).where(
            GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == int(student.id),
            GraduationGrade.status.in_(("REVIEWED", "PUBLISHED")), GraduationGrade.is_deleted.is_(False),
        ).order_by(GraduationGrade.id.desc())).first()
        if grade:
            specs.append(SnapshotSpec(
                "GRADE_MATERIAL", "毕业设计成绩评定表", "GRADE", str(grade.id),
                common + (("导师成绩", grade.advisor_score), ("评阅成绩", grade.reviewer_score),
                          ("答辩成绩", grade.defense_score), ("综合成绩", grade.total_score),
                          ("等级", grade.grade_level), ("状态", grade.status),
                          ("复核人", grade.reviewed_by), ("复核时间", _iso(grade.reviewed_at)),
                          ("权威输入哈希", grade.source_snapshot_hash)),
            ))
        # Invalid codes are rejected now, before file bytes are generated.
        for spec in specs:
            rule_item(db, int(student.batch_id), spec.material_code)
        return {
            "id": int(student.id), "studentNo": student.student_no or str(student.id),
        }, specs


def _current_source_hash(gd_student_id: int, material_code: str) -> str | None:
    with session() as db:
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(gd_student_id),
            GraduationStudentMaterial.material_code == material_code,
            GraduationStudentMaterial.is_deleted.is_(False),
        )).first()
        if not material or not material.current_version_id:
            return None
        binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == int(material.current_version_id),
            FileBinding.module_code == MODULE_CODE, FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        )).first()
        return str((binding.scope_json or {}).get("sourceDataHash") or "") or None if binding else None


def render_fields_pdf(title: str, fields: tuple[tuple[str, Any], ...]) -> bytes:
    output = io.BytesIO()
    try:
        pdfmetrics.getFont("STSong-Light")
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdf = canvas.Canvas(output, pagesize=(595.28, 841.89), pageCompression=1)
    pdf.setTitle(title)
    pdf.setAuthor("毕业设计材料中心")
    y = 805
    pdf.setFont("STSong-Light", 16)
    pdf.drawString(48, y, title[:60])
    y -= 34
    pdf.setFont("STSong-Light", 10)
    for label, raw in fields:
        text = f"{label}：{'' if raw is None else raw}"
        chunks = [text[index:index + 46] for index in range(0, max(1, len(text)), 46)] or [""]
        for chunk in chunks:
            if y < 50:
                pdf.showPage()
                pdf.setFont("STSong-Light", 10)
                y = 805
            pdf.drawString(48, y, chunk)
            y -= 17
        y -= 3
    pdf.save()
    return output.getvalue()


def _pdf_bytes(spec: SnapshotSpec) -> bytes:
    return render_fields_pdf(spec.title, spec.fields)


def prepare_all(gd_student_id: int, user: dict) -> dict:
    """Three phases: read source, persist bytes, register immutable version."""
    student, specs = _collect(int(gd_student_id), user)
    result = {"created": [], "unchanged": [], "pendingReview": []}
    for spec in specs:
        source_hash = spec.source_hash(int(student["id"]))
        if _current_source_hash(int(student["id"]), spec.material_code) == source_hash:
            result["unchanged"].append(spec.material_code)
            continue
        meta = file_service.store_bytes(
            _pdf_bytes(spec), f"{student['studentNo']}_{spec.material_code}.pdf",
            biz_type="GRADUATION_SNAPSHOT_STAGING", biz_id=str(student["id"]),
            mime_type="application/pdf", user=user, visibility="BIZ_SCOPED",
            security_level="HIGHLY_SENSITIVE",
        )
        registered = register_generated_snapshot(
            int(student["id"]), spec.material_code, int(meta["fileId"]),
            source_record_type=spec.source_record_type, source_record_id=spec.source_record_id,
            source_data_hash=source_hash, snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
            generator_version=SNAPSHOT_GENERATOR_VERSION, approved=spec.approved, user=user,
        )
        result["unchanged" if registered["status"] == "UNCHANGED" else "created"].append(spec.material_code)
        if not spec.approved:
            result["pendingReview"].append(spec.material_code)
    return result


__all__ = ["prepare_all", "render_fields_pdf"]
