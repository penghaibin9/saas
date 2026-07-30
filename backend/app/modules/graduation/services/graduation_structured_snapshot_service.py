"""阶段 6结构化毕业设计证据 PDF。

读取业务数据、生成 FileObject、登记 FileVersion 分三段事务执行，避免 MySQL 默认
REPEATABLE READ 下当前事务看不到 file_service.store_bytes 独立事务的新文件。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
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
from app.models.file import FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.services import graduation_material_catalog_service as catalog
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services import file_service
from app.services.db_service import _iso, _tid, session


@dataclass(frozen=True)
class SnapshotSpec:
    code: str
    title: str
    fields: tuple[tuple[str, Any], ...]
    source_type: str
    source_id: str
    approved: bool = True


def _collect(gd_student_id: int, user: dict) -> tuple[dict, list[SnapshotSpec]]:
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        )).first()
        if not student:
            raise not_found("毕业设计学生不存在")
        assert_student_access(db, student, "structured.snapshot")
        catalog._ensure_student_rows(db, student, user)
        db.commit()

        specs: list[SnapshotSpec] = []
        taskbook = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(),
            GraduationTaskBook.gd_student_id == int(student.id),
            GraduationTaskBook.status == "CONFIRMED",
            GraduationTaskBook.is_deleted.is_(False),
        )).first()
        if taskbook:
            specs.append(SnapshotSpec(
                "TASKBOOK", "毕业设计任务书",
                (("学生", student.name), ("学号", student.student_no), ("题目", student.topic_title),
                 ("任务目标", taskbook.objective), ("任务内容", taskbook.content),
                 ("进度计划", taskbook.progress_plan), ("成果要求", taskbook.outcome_requirement),
                 ("任务书业务版本", taskbook.taskbook_version), ("确认时间", _iso(taskbook.confirmed_at))),
                "TASKBOOK", str(taskbook.id), True,
            ))

        proposal = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(),
            GraduationProposal.gd_student_id == int(student.id),
            GraduationProposal.status == "APPROVED",
            GraduationProposal.is_deleted.is_(False),
        ).order_by(GraduationProposal.id.desc())).first()
        if proposal and proposal.defense_result:
            specs.append(SnapshotSpec(
                "PROPOSAL_DEFENSE", "开题答辩记录",
                (("学生", student.name), ("题目", student.topic_title),
                 ("答辩结果", proposal.defense_result), ("答辩评语", proposal.defense_comment),
                 ("答辩时间", _iso(proposal.defense_at))),
                "PROPOSAL_DEFENSE", str(proposal.id), proposal.defense_result == "PASS",
            ))

        guidance = db.scalars(select(GraduationGuidance).where(
            GraduationGuidance.tenant_id == _tid(),
            GraduationGuidance.gd_student_id == int(student.id),
            GraduationGuidance.is_deleted.is_(False),
            GraduationGuidance.void_reason.is_(None),
        ).order_by(GraduationGuidance.guidance_date, GraduationGuidance.id)).all()
        if guidance:
            fields: list[tuple[str, Any]] = [("学生", student.name), ("题目", student.topic_title)]
            for index, row in enumerate(guidance, start=1):
                fields.extend(((f"第{index}次指导时间", _iso(row.guidance_date)),
                               (f"第{index}次指导方式", row.method),
                               (f"第{index}次指导内容", row.content),
                               (f"第{index}次发现问题", row.issues)))
            specs.append(SnapshotSpec("GUIDANCE_RECORD", "毕业设计指导记录汇总", tuple(fields),
                                      "GUIDANCE", str(guidance[-1].id), True))

        midterm = db.scalars(select(GraduationMidterm).where(
            GraduationMidterm.tenant_id == _tid(),
            GraduationMidterm.gd_student_id == int(student.id),
            GraduationMidterm.is_deleted.is_(False),
        )).first()
        if midterm and midterm.status in {"CHECKED_PASS", "RECTIFIED_PASS"}:
            specs.append(SnapshotSpec(
                "MIDTERM_REPORT", "毕业设计中期检查记录",
                (("学生", student.name), ("检查结论", midterm.conclusion),
                 ("检查意见", midterm.check_comment), ("检查人", midterm.check_by),
                 ("检查时间", _iso(midterm.checked_at)), ("整改内容", midterm.rectify_content),
                 ("复核意见", midterm.review_comment), ("复核时间", _iso(midterm.reviewed_at))),
                "MIDTERM", str(midterm.id), True,
            ))

        plagiarism = db.scalars(select(GraduationPlagiarismCheck).where(
            GraduationPlagiarismCheck.tenant_id == _tid(),
            GraduationPlagiarismCheck.gd_student_id == int(student.id),
            GraduationPlagiarismCheck.status == "DONE",
            GraduationPlagiarismCheck.is_deleted.is_(False),
        ).order_by(GraduationPlagiarismCheck.id.desc())).first()
        if plagiarism:
            approved = not plagiarism.over_threshold or plagiarism.dispute_status == "APPROVED"
            specs.append(SnapshotSpec(
                "PLAGIARISM_REPORT", "毕业设计查重结果",
                (("学生", student.name), ("重复率", plagiarism.rate),
                 ("阈值", plagiarism.threshold), ("是否超标", "是" if plagiarism.over_threshold else "否"),
                 ("特例状态", plagiarism.dispute_status), ("提交时间", _iso(plagiarism.submit_at))),
                "PLAGIARISM", str(plagiarism.id), approved,
            ))

        reviews = db.scalars(select(GraduationReview).where(
            GraduationReview.tenant_id == _tid(),
            GraduationReview.gd_student_id == int(student.id),
            GraduationReview.status == "COMPLETED",
            GraduationReview.is_deleted.is_(False),
        ).order_by(GraduationReview.id)).all()
        if reviews:
            fields = [("学生", student.name)]
            for index, row in enumerate(reviews, start=1):
                fields.extend(((f"评阅人{index}", row.reviewer_name), (f"评阅分{index}", row.score),
                               (f"评阅意见{index}", row.opinion), (f"评阅时间{index}", _iso(row.reviewed_at))))
            specs.append(SnapshotSpec("REVIEW_ATTACHMENT", "毕业设计评阅意见汇总", tuple(fields),
                                      "REVIEW", str(reviews[-1].id), True))

        scores = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(),
            GraduationDefenseScore.gd_student_id == int(student.id),
            GraduationDefenseScore.status == "CONFIRMED",
            GraduationDefenseScore.is_deleted.is_(False),
        ).order_by(GraduationDefenseScore.round_no, GraduationDefenseScore.id)).all()
        if scores:
            fields = [("学生", student.name), ("答辩组", student.defense_group)]
            for index, row in enumerate(scores, start=1):
                fields.extend(((f"评委{index}", row.judge_name), (f"分数{index}", row.score),
                               (f"评语{index}", row.comment), (f"轮次{index}", row.round_no)))
            specs.append(SnapshotSpec("DEFENSE_RECORD", "毕业设计答辩记录", tuple(fields),
                                      "DEFENSE_SCORE", str(scores[-1].id), True))

        grade = db.scalars(select(GraduationGrade).where(
            GraduationGrade.tenant_id == _tid(),
            GraduationGrade.gd_student_id == int(student.id),
            GraduationGrade.status.in_(("REVIEWED", "PUBLISHED")),
            GraduationGrade.is_deleted.is_(False),
        )).first()
        if grade:
            specs.append(SnapshotSpec(
                "GRADE_MATERIAL", "毕业设计成绩评定表",
                (("学生", student.name), ("导师成绩", grade.advisor_score),
                 ("评阅成绩", grade.reviewer_score), ("答辩成绩", grade.defense_score),
                 ("综合成绩", grade.total_score), ("等级", grade.grade_level),
                 ("状态", grade.status), ("复核人", grade.reviewed_by),
                 ("复核时间", _iso(grade.reviewed_at)), ("数据快照SHA-256", grade.source_snapshot_hash)),
                "GRADE", str(grade.id), True,
            ))

        return {
            "id": int(student.id), "studentNo": student.student_no or str(student.id),
        }, specs


def _current_hash(material_code: str, gd_student_id: int) -> str | None:
    with session() as db:
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(gd_student_id),
            GraduationStudentMaterial.material_code == material_code,
            GraduationStudentMaterial.is_deleted.is_(False),
        )).first()
        if not material or not material.current_version_id:
            return None
        version = db.get(FileVersion, int(material.current_version_id))
        file_obj = db.get(FileObject, int(version.file_object_id)) if version else None
        return file_obj.sha256 if file_obj and not file_obj.is_deleted else None


def _persist_snapshot(student: dict, spec: SnapshotSpec, data: bytes, user: dict) -> str:
    digest = hashlib.sha256(data).hexdigest()
    if _current_hash(spec.code, int(student["id"])) == digest:
        return "UNCHANGED"

    meta = file_service.store_bytes(
        data,
        f"{student['studentNo']}_{spec.code}.pdf",
        biz_type="GRADUATION_MATERIAL",
        biz_id=str(student["id"]),
        mime_type="application/pdf",
        user=user,
        visibility="BIZ_SCOPED",
        security_level=catalog.SPEC_BY_CODE[spec.code]["sensitivityLevel"],
    )
    with session() as db:
        gd_student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.id == int(student["id"]),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not gd_student:
            raise not_found("毕业设计学生不存在")
        catalog._ensure_student_rows(db, gd_student, user)
        material = catalog._row_for_code(db, gd_student, spec.code, user=user)
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id == int(meta["fileId"]),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not file_obj:
            raise AppException("DATA_CONFLICT", "结构化材料PDF快照登记失败")
        catalog._append_version(
            db, gd_student, material, file_obj, user,
            source_channel="SYSTEM_GENERATED",
            status="APPROVED" if spec.approved else "SUBMITTED",
            source_type=spec.source_type,
            source_id=spec.source_id,
            comment=f"{spec.source_type}结构化数据PDF快照",
        )
        db.commit()
    return "CREATED"


def prepare_all(gd_student_id: int, user: dict) -> dict:
    student, specs = _collect(int(gd_student_id), user)
    result = {"created": [], "unchanged": [], "pendingReview": []}
    for spec in specs:
        data = catalog._pdf_snapshot(spec.title, list(spec.fields))
        status = _persist_snapshot(student, spec, data, user)
        result["unchanged" if status == "UNCHANGED" else "created"].append(spec.code)
        if not spec.approved:
            result["pendingReview"].append(spec.code)
    return result
