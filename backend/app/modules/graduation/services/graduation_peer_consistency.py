"""成果互查任务的定稿绑定、数据范围与学生可读证据链。"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (
    FileObject,
    GraduationFinal,
    GraduationPeerReview,
    GraduationStudent,
)
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _iso, _tid, session
from app.services.file_content_security import is_downloadable_status

_INSTALLED = False


def _version_number(value) -> int:
    match = re.search(r"(\d+)", str(value or ""))
    return max(1, int(match.group(1))) if match else 1


def _final_attachments(db, final: GraduationFinal | None) -> list[dict]:
    if not final:
        return []
    ids: list[int] = []
    for raw in final.attachments_json or []:
        value = (raw.get("fileId") or raw.get("id")) if isinstance(raw, dict) else raw
        if str(value or "").isdigit() and int(value) not in ids:
            ids.append(int(value))
    if not ids:
        return []
    rows = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(),
        FileObject.id.in_(ids),
        FileObject.is_deleted.is_(False),
        FileObject.biz_type == "GRADUATION_MATERIAL",
    )).all()
    by_id = {int(row.id): row for row in rows if is_downloadable_status(row.status)}
    return [{
        "fileId": str(file_id),
        "fileName": by_id[file_id].file_name or f"材料-{file_id}",
        "ext": by_id[file_id].ext or "",
        "size": int(by_id[file_id].size_bytes or 0),
        "downloadUrl": f"/api/v1/mobile/graduation/materials/{file_id}/download",
    } for file_id in ids if file_id in by_id]


def _bound_final(db, peer: GraduationPeerReview, *, lock=False) -> GraduationFinal:
    if not peer.gd_final_id:
        raise AppException("DATA_CONFLICT", "该历史互查任务未绑定正式定稿，请联系管理员重新分配")
    query = select(GraduationFinal).where(
        GraduationFinal.id == int(peer.gd_final_id),
        GraduationFinal.tenant_id == _tid(),
        GraduationFinal.gd_student_id == peer.gd_student_id,
        GraduationFinal.final_type == "定稿",
        GraduationFinal.status == "APPROVED",
        GraduationFinal.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    final = db.scalars(query).first()
    if not final:
        raise AppException("DATA_CONFLICT", "互查绑定的正式定稿已失效，请联系管理员重新分配")
    return final


def peer_row(db, peer: GraduationPeerReview) -> dict:
    target = db.get(GraduationStudent, peer.gd_student_id)
    reviewer = db.get(GraduationStudent, peer.reviewer_gd_student_id)
    final = db.get(GraduationFinal, peer.gd_final_id) if peer.gd_final_id else None
    final_valid = bool(
        final and not final.is_deleted and final.tenant_id == _tid()
        and final.gd_student_id == peer.gd_student_id
        and final.final_type == "定稿" and final.status == "APPROVED"
    )
    return {
        "id": str(peer.id),
        "gdStudentId": str(peer.gd_student_id),
        "studentName": target.name if target else "",
        "studentNo": target.student_no if target else "",
        "reviewerGdStudentId": str(peer.reviewer_gd_student_id),
        "reviewerName": reviewer.name if reviewer else "",
        "gdFinalId": str(peer.gd_final_id) if peer.gd_final_id else None,
        "finalVersion": final.version if final_valid else "",
        "finalType": final.final_type if final_valid else "",
        "attachmentsList": _final_attachments(db, final if final_valid else None),
        "taskVersion": int(peer.task_version or 1),
        "taskValid": final_valid,
        "taskError": "" if final_valid else "任务未绑定有效正式定稿，请联系管理员重新分配",
        "opinion": peer.opinion or "",
        "rectifyNote": peer.rectify_note or "",
        "status": peer.status,
        "statusLabel": {"ASSIGNED": "待互查", "REVIEWED": "已互查", "RECTIFIED": "已整改"}.get(
            peer.status, peer.status,
        ),
        "reviewedAt": _iso(peer.reviewed_at),
        "updatedAt": _iso(peer.updated_at),
    }


def assign_peer(gd_student_id, reviewer_gd_student_id) -> dict:
    """将同批次、同数据范围的两名学生绑定到目标学生最新已通过定稿。"""
    if str(gd_student_id) == str(reviewer_gd_student_id):
        raise AppException("VALIDATION_ERROR", "互查学生不能是本人")

    from app.modules.graduation.services import graduation_more_service as service

    with session() as db:
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.id.in_((int(gd_student_id), int(reviewer_gd_student_id))),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).order_by(GraduationStudent.id).with_for_update()).all()
        by_id = {int(row.id): row for row in students}
        target = by_id.get(int(gd_student_id))
        reviewer = by_id.get(int(reviewer_gd_student_id))
        if not target or not reviewer:
            raise not_found("互查学生不存在")
        assert_student_access(db, target, "peer.assign.target")
        assert_student_access(db, reviewer, "peer.assign.reviewer")
        if int(target.batch_id or 0) != int(reviewer.batch_id or 0):
            raise AppException("DATA_CONFLICT", "互查双方必须属于同一毕业设计批次")

        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.gd_student_id == target.id,
            GraduationFinal.final_type == "定稿",
            GraduationFinal.status == "APPROVED",
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc()).with_for_update()).first()
        if not final:
            raise AppException("DATA_CONFLICT", "被评学生尚无已通过的正式定稿，不能分配互查")
        task_version = _version_number(final.version)

        existing = db.scalars(select(GraduationPeerReview).where(
            GraduationPeerReview.tenant_id == _tid(),
            GraduationPeerReview.gd_student_id == target.id,
            GraduationPeerReview.reviewer_gd_student_id == reviewer.id,
            GraduationPeerReview.gd_final_id == final.id,
            GraduationPeerReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing:
            if existing.status == "ASSIGNED":
                return peer_row(db, existing)
            raise AppException("DATA_CONFLICT", "该定稿版本的互查任务已完成，不能重复分配")

        peer = GraduationPeerReview(
            tenant_id=_tid(),
            gd_student_id=target.id,
            reviewer_gd_student_id=reviewer.id,
            gd_final_id=final.id,
            task_version=task_version,
            status="ASSIGNED",
        )
        db.add(peer)
        db.flush()
        service._audit(
            db, "PEER_REVIEW", peer.id, "分配成果互查",
            f"reviewer={reviewer.id};target={target.id};final={final.id};version={final.version}",
        )
        db.commit()
        return peer_row(db, peer)


def submit_peer(peer_id, opinion) -> dict:
    note = str(opinion or "").strip()
    if len(note) < 5:
        raise AppException("VALIDATION_ERROR", "互查意见不少于 5 字")
    from app.modules.graduation.services import graduation_more_service as service
    with session() as db:
        peer = db.scalars(select(GraduationPeerReview).where(
            GraduationPeerReview.id == int(peer_id),
            GraduationPeerReview.tenant_id == _tid(),
            GraduationPeerReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if not peer:
            raise not_found("互查任务不存在")
        reviewer = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == peer.reviewer_gd_student_id,
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, reviewer, "peer.submit")
        _bound_final(db, peer, lock=True)
        if peer.status != "ASSIGNED":
            raise AppException("DATA_CONFLICT", "仅待互查任务可提交意见")
        peer.opinion = note
        peer.status = "REVIEWED"
        peer.reviewed_at = datetime.now(timezone.utc)
        service._audit(db, "PEER_REVIEW", peer.id, "提交互查意见", note)
        db.commit()
        return peer_row(db, peer)


def rectify_peer(peer_id, note) -> dict:
    content = str(note or "").strip()
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "整改说明不少于 5 字")
    from app.modules.graduation.services import graduation_more_service as service
    with session() as db:
        peer = db.scalars(select(GraduationPeerReview).where(
            GraduationPeerReview.id == int(peer_id),
            GraduationPeerReview.tenant_id == _tid(),
            GraduationPeerReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if not peer:
            raise not_found("互查任务不存在")
        target = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == peer.gd_student_id,
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, target, "peer.rectify")
        _bound_final(db, peer, lock=True)
        if peer.status != "REVIEWED":
            raise AppException("DATA_CONFLICT", "仅已互查任务可提交整改")
        peer.rectify_note = content
        peer.status = "RECTIFIED"
        service._audit(db, "PEER_REVIEW", peer.id, "提交互查整改", content)
        db.commit()
        return peer_row(db, peer)


def install_peer_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.modules.graduation.services import graduation_more_service as service
    service._peer_row = peer_row
    service.assign_peer = assign_peer
    service.submit_peer = submit_peer
    service.rectify_peer = rectify_peer
    _INSTALLED = True
