"""W7.3 production Review Center query projection.

Queue count/sort/pagination executes in the database. Only the selected page is then
hydrated with append-only feedback/evidence, avoiding full-batch feedback loads and
per-row student/material/FileVersion queries.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import bindparam, select, text

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import GraduationBatch
from app.models.file import FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.services import graduation_review_feedback_service as feedback
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session

CASE_TYPES = {"PROPOSAL", "FINAL_DRAFT", "FINAL", "FORMAL_REVIEW"}
STATUS_GROUPS = {"WAITING", "IN_REVIEW", "RETURNED", "DONE", "BLOCKED"}
SORTS = {"PRIORITY", "LATEST", "EARLIEST", "STUDENT_NO", "STATUS"}
STATUS_LABELS = {"PENDING_REVIEW": "待审核", "APPROVED": "已通过", "REJECTED": "已退回",
                 "ASSIGNED": "待评阅", "REVIEWING": "评阅中", "COMPLETED": "已完成", "RETURNED": "已退回重评"}
_STAGE_HINTS = {
    "PROPOSAL": ("PROPOSAL", "OPENING", "开题"), "FINAL_DRAFT": ("DRAFT", "FIRST_DRAFT", "初稿"),
    "FINAL": ("FINAL", "THESIS_FINAL", "定稿"), "FORMAL_REVIEW": ("REVIEW", "FORMAL_REVIEW", "评阅"),
}

_CTE = r"""
WITH candidate AS (
SELECT 'PROPOSAL' case_type,p.id record_id,NULL gd_final_id,p.gd_student_id,p.status,p.submit_at submitted_at,
       p.review_time reviewed_at,NULL assigned_at,NULL started_at,p.created_at,p.reviewer reviewer_name,NULL reviewer_mentor_id,
       NULL score,s.student_no,s.name student_name,s.class_name,t.major_name,s.topic_title,s.advisor_name,
       m.id material_id,m.material_code,m.material_name,m.asset_id,m.current_version_id,
       m.current_version_id file_version_id,fv.version_no,fo.id file_id,fo.file_name,fo.mime_type,fo.sha256 source_sha256,
       fv.status version_status,fo.status file_status,fo.scan_status,
       CASE p.status WHEN 'PENDING_REVIEW' THEN 'WAITING' WHEN 'REJECTED' THEN 'RETURNED' WHEN 'APPROVED' THEN 'DONE' ELSE 'BLOCKED' END base_group,
       CASE WHEN m.id IS NULL THEN 1 ELSE 0 END material_missing,
       CASE WHEN m.current_version_id IS NULL OR fv.id IS NULL THEN 1 ELSE 0 END version_missing,
       CASE WHEN fv.id IS NOT NULL AND fv.status NOT IN ('SUBMITTED','APPROVED') THEN 1 ELSE 0 END version_bad,
       CASE WHEN fo.id IS NULL OR fo.status<>'AVAILABLE' OR fo.scan_status NOT IN ('NOT_REQUIRED','CLEAN') THEN 1 ELSE 0 END file_bad,
       0 sha_conflict,0 version_conflict,0 reviewer_missing,NULL plag_status,0 plag_over,NULL plag_dispute
FROM t_gd_proposal p JOIN t_gd_student s ON s.id=p.gd_student_id AND s.tenant_id=p.tenant_id AND s.is_deleted=0
LEFT JOIN t_gd_topic t ON t.id=s.topic_id AND t.tenant_id=s.tenant_id AND t.is_deleted=0
LEFT JOIN t_gd_student_material m ON m.tenant_id=p.tenant_id AND m.batch_id=s.batch_id AND m.gd_student_id=s.id AND m.material_code='PROPOSAL_REPORT' AND m.is_deleted=0
LEFT JOIN t_file_version fv ON fv.id=m.current_version_id AND fv.tenant_id=p.tenant_id AND fv.is_deleted=0
LEFT JOIN t_file_object fo ON fo.id=fv.file_object_id AND fo.tenant_id=p.tenant_id AND fo.is_deleted=0
WHERE p.tenant_id=:tenant_id AND p.is_deleted=0 AND s.batch_id=:batch_id AND s.record_status='ACTIVE' AND s.id IN :scope_ids
UNION ALL
SELECT CASE WHEN f.final_type='定稿' THEN 'FINAL' ELSE 'FINAL_DRAFT' END case_type,f.id record_id,f.id gd_final_id,f.gd_student_id,f.status,
       f.submit_at,f.review_time,NULL,NULL,f.created_at,f.reviewer,NULL,NULL,s.student_no,s.name,s.class_name,t.major_name,s.topic_title,s.advisor_name,
       m.id,m.material_code,m.material_name,m.asset_id,m.current_version_id,m.current_version_id,fv.version_no,fo.id,fo.file_name,fo.mime_type,fo.sha256,
       fv.status,fo.status,fo.scan_status,
       CASE f.status WHEN 'PENDING_REVIEW' THEN 'WAITING' WHEN 'REJECTED' THEN 'RETURNED' WHEN 'APPROVED' THEN 'DONE' ELSE 'BLOCKED' END,
       CASE WHEN m.id IS NULL THEN 1 ELSE 0 END,
       CASE WHEN m.current_version_id IS NULL OR fv.id IS NULL THEN 1 ELSE 0 END,
       CASE WHEN fv.id IS NOT NULL AND fv.status NOT IN ('SUBMITTED','APPROVED') THEN 1 ELSE 0 END,
       CASE WHEN fo.id IS NULL OR fo.status<>'AVAILABLE' OR fo.scan_status NOT IN ('NOT_REQUIRED','CLEAN') THEN 1 ELSE 0 END,
       0,0,0,
       (SELECT pp.status FROM t_gd_plagiarism pp WHERE pp.tenant_id=f.tenant_id AND pp.gd_final_id=f.id AND pp.is_deleted=0 ORDER BY pp.id DESC LIMIT 1),
       COALESCE((SELECT pp.over_threshold FROM t_gd_plagiarism pp WHERE pp.tenant_id=f.tenant_id AND pp.gd_final_id=f.id AND pp.is_deleted=0 ORDER BY pp.id DESC LIMIT 1),0),
       (SELECT pp.dispute_status FROM t_gd_plagiarism pp WHERE pp.tenant_id=f.tenant_id AND pp.gd_final_id=f.id AND pp.is_deleted=0 ORDER BY pp.id DESC LIMIT 1)
FROM t_gd_final f JOIN t_gd_student s ON s.id=f.gd_student_id AND s.tenant_id=f.tenant_id AND s.is_deleted=0
LEFT JOIN t_gd_topic t ON t.id=s.topic_id AND t.tenant_id=s.tenant_id AND t.is_deleted=0
LEFT JOIN t_gd_student_material m ON m.tenant_id=f.tenant_id AND m.batch_id=s.batch_id AND m.gd_student_id=s.id AND m.material_code=CASE WHEN f.final_type='定稿' THEN 'THESIS_FINAL' ELSE 'THESIS_DRAFT' END AND m.is_deleted=0
LEFT JOIN t_file_version fv ON fv.id=m.current_version_id AND fv.tenant_id=f.tenant_id AND fv.is_deleted=0
LEFT JOIN t_file_object fo ON fo.id=fv.file_object_id AND fo.tenant_id=f.tenant_id AND fo.is_deleted=0
WHERE f.tenant_id=:tenant_id AND f.is_deleted=0 AND s.batch_id=:batch_id AND s.record_status='ACTIVE' AND s.id IN :scope_ids
UNION ALL
SELECT 'FORMAL_REVIEW',r.id,r.gd_final_id,r.gd_student_id,r.status,NULL,r.reviewed_at,r.assigned_at,r.started_at,r.created_at,r.reviewer_name,r.reviewer_mentor_id,r.score,
       s.student_no,s.name,s.class_name,t.major_name,s.topic_title,s.advisor_name,m.id,m.material_code,m.material_name,m.asset_id,m.current_version_id,
       r.file_version_id,fv.version_no,fo.id,fo.file_name,fo.mime_type,r.source_sha256,fv.status,fo.status,fo.scan_status,
       CASE r.status WHEN 'ASSIGNED' THEN 'WAITING' WHEN 'REVIEWING' THEN 'IN_REVIEW' WHEN 'RETURNED' THEN 'RETURNED' WHEN 'COMPLETED' THEN 'DONE' ELSE 'BLOCKED' END,
       CASE WHEN r.material_id IS NULL OR m.id IS NULL THEN 1 ELSE 0 END,
       CASE WHEN r.file_version_id IS NULL OR fv.id IS NULL THEN 1 ELSE 0 END,
       CASE WHEN fv.id IS NOT NULL AND fv.status<>'APPROVED' THEN 1 ELSE 0 END,
       CASE WHEN fo.id IS NULL OR fo.status<>'AVAILABLE' OR fo.scan_status NOT IN ('NOT_REQUIRED','CLEAN') THEN 1 ELSE 0 END,
       CASE WHEN r.source_sha256 IS NULL OR fo.sha256 IS NULL OR LOWER(r.source_sha256)<>LOWER(fo.sha256) THEN 1 ELSE 0 END,
       CASE WHEN r.file_version_id IS NOT NULL AND m.current_version_id IS NOT NULL AND r.file_version_id<>m.current_version_id THEN 1 ELSE 0 END,
       CASE WHEN r.reviewer_mentor_id IS NULL THEN 1 ELSE 0 END,NULL,0,NULL
FROM t_gd_review r JOIN t_gd_student s ON s.id=r.gd_student_id AND s.tenant_id=r.tenant_id AND s.is_deleted=0
LEFT JOIN t_gd_topic t ON t.id=s.topic_id AND t.tenant_id=s.tenant_id AND t.is_deleted=0
LEFT JOIN t_gd_student_material m ON m.id=r.material_id AND m.tenant_id=r.tenant_id AND m.is_deleted=0
LEFT JOIN t_file_version fv ON fv.id=r.file_version_id AND fv.tenant_id=r.tenant_id AND fv.is_deleted=0
LEFT JOIN t_file_object fo ON fo.id=fv.file_object_id AND fo.tenant_id=r.tenant_id AND fo.is_deleted=0
WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND s.batch_id=:batch_id AND s.record_status='ACTIVE' AND s.id IN :scope_ids
), projected AS (
SELECT candidate.*,
       CASE WHEN base_group IN ('WAITING','IN_REVIEW') AND (
            material_missing=1 OR version_missing=1 OR version_bad=1 OR file_bad=1 OR sha_conflict=1 OR version_conflict=1 OR reviewer_missing=1 OR
            (case_type='FINAL' AND status='PENDING_REVIEW' AND (plag_status IS NULL OR plag_status<>'DONE' OR (plag_over=1 AND COALESCE(plag_dispute,'')<>'APPROVED')))
       ) THEN 'BLOCKED' ELSE base_group END status_group
FROM candidate
)
"""


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _batch_deadlines(db, batch_id: int) -> dict[str, datetime | None]:
    batch = db.scalars(select(GraduationBatch).where(GraduationBatch.tenant_id == _tid(), GraduationBatch.id == int(batch_id), GraduationBatch.is_deleted.is_(False))).first()
    if not batch:
        raise not_found("毕设批次不存在")
    result = {case: None for case in CASE_TYPES}
    for item in batch.stage_config if isinstance(batch.stage_config, list) else []:
        if not isinstance(item, dict):
            continue
        label = " ".join(str(item.get(k) or "") for k in ("code", "name", "stage", "stageCode")).upper()
        deadline = _parse_dt(item.get("endDate") or item.get("end_at") or item.get("deadline"))
        if not deadline:
            continue
        for case, hints in _STAGE_HINTS.items():
            if result[case] is None and any(str(h).upper() in label for h in hints):
                result[case] = deadline
    fallback = _parse_dt(batch.end_date)
    for case in result:
        result[case] = result[case] or fallback
    return result


def _deadline(row: dict, deadlines: dict[str, datetime | None]) -> datetime | None:
    return deadlines.get(str(row.get("case_type") or ""))


def _is_overdue(row: dict, deadlines: dict[str, datetime | None], now: datetime) -> bool:
    deadline = _deadline(row, deadlines)
    return bool(deadline and deadline < now and str(row.get("status_group") or "") in {"WAITING", "IN_REVIEW", "RETURNED", "BLOCKED"})


def _current_reviewer(db) -> tuple[int | None, str]:
    name = str((get_current_user_ctx() or {}).get("realName") or "").strip()
    try:
        from app.modules.graduation.services import graduation_identity as gid
        mentor = gid.current_user_mentor(db)
        return (int(mentor.id), name) if mentor else (None, name)
    except Exception:  # noqa: BLE001
        return None, name


def _filters(case_type, status_group, keyword, reviewer_only, reviewer_id, reviewer_name):
    clauses, params = [], {}
    if case_type:
        value = str(case_type).upper()
        if value not in CASE_TYPES:
            raise AppException("VALIDATION_ERROR", "caseType 不支持")
        clauses.append("case_type=:case_type"); params["case_type"] = value
    if status_group:
        value = str(status_group).upper()
        if value not in STATUS_GROUPS:
            raise AppException("VALIDATION_ERROR", "statusGroup 不支持")
        clauses.append("status_group=:status_group"); params["status_group"] = value
    if keyword:
        params["keyword"] = "%" + str(keyword).strip().lower() + "%"
        clauses.append("(LOWER(COALESCE(student_name,'')) LIKE :keyword OR LOWER(COALESCE(student_no,'')) LIKE :keyword OR LOWER(COALESCE(class_name,'')) LIKE :keyword OR LOWER(COALESCE(major_name,'')) LIKE :keyword OR LOWER(COALESCE(topic_title,'')) LIKE :keyword)")
    if reviewer_only:
        if reviewer_id is not None:
            clauses.append("reviewer_mentor_id=:reviewer_id"); params["reviewer_id"] = int(reviewer_id)
        elif reviewer_name:
            clauses.append("reviewer_mentor_id IS NULL AND reviewer_name=:reviewer_name"); params["reviewer_name"] = reviewer_name
        else:
            clauses.append("1=0")
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _priority_key(row: dict, deadlines: dict[str, datetime | None], now: datetime):
    group, case = str(row.get("status_group") or ""), str(row.get("case_type") or "")
    if group == "RETURNED": rank = 0
    elif _is_overdue(row, deadlines, now): rank = 1
    elif group == "DONE": rank = 9
    elif case in {"FINAL", "FINAL_DRAFT"}: rank = 2
    elif case == "FORMAL_REVIEW": rank = 3
    elif case == "PROPOSAL": rank = 4
    else: rank = 5
    when = row.get("reviewed_at") or row.get("submitted_at") or row.get("assigned_at") or row.get("created_at") or datetime.min
    return rank, when, int(row.get("record_id") or 0)


def _blockers(row: dict) -> list[dict]:
    result = []
    def add(flag, code, message):
        if int(row.get(flag) or 0): result.append({"code": code, "message": message})
    add("material_missing", "MATERIAL_MISSING", "业务记录未绑定权威材料项")
    add("version_missing", "FILE_VERSION_MISSING", "业务记录缺少可评阅 FileVersion")
    add("version_bad", "FILE_VERSION_NOT_REVIEWABLE", "FileVersion 当前状态不可评阅")
    add("file_bad", "FILE_NOT_READY", "文件未通过公共文件中心可用性/安全门禁")
    add("sha_conflict", "SOURCE_SHA_CONFLICT", "冻结 SHA-256 与文件证据不一致")
    add("version_conflict", "CANONICAL_VERSION_CHANGED", "任务冻结版本与当前 canonical 版本不一致")
    add("reviewer_missing", "REVIEWER_ID_MISSING", "正式评阅缺少稳定 reviewerMentorId")
    if row.get("case_type") == "FINAL" and row.get("status") == "PENDING_REVIEW":
        if row.get("plag_status") != "DONE": result.append({"code": "PLAGIARISM_PENDING", "message": "定稿查重尚未完成"})
        elif int(row.get("plag_over") or 0) and str(row.get("plag_dispute") or "") != "APPROVED": result.append({"code": "PLAGIARISM_BLOCKED", "message": "查重超标且未通过特例审批"})
    return result


def _allowed(case: str, status: str, ready: bool) -> list[str]:
    if case in {"PROPOSAL", "FINAL_DRAFT", "FINAL"}: return ["REVIEW"] if status == "PENDING_REVIEW" and ready else []
    if status in {"ASSIGNED", "RETURNED"} and ready: return ["START", "SUBMIT"]
    if status == "REVIEWING" and ready: return ["SUBMIT"]
    if status == "COMPLETED": return ["RETURN"]
    return []


def _descriptor(row: dict) -> dict | None:
    if row.get("file_version_id") is None: return None
    return {"fileId": str(row.get("file_id")) if row.get("file_id") is not None else None,
            "fileVersionId": str(row.get("file_version_id")), "versionNo": row.get("version_no"),
            "fileName": row.get("file_name"), "mimeType": row.get("mime_type"),
            "versionStatus": row.get("version_status"), "fileStatus": row.get("file_status"),
            "scanStatus": row.get("scan_status"), "sourceSha256": row.get("source_sha256")}


def _public(row: dict, deadlines, now, latest_feedback=None) -> dict:
    blockers = _blockers(row); ready = not blockers
    deadline = _deadline(row, deadlines)
    return {
        "caseKey": f"{row['case_type']}:{row['record_id']}", "caseType": row["case_type"], "recordId": str(row["record_id"]),
        "batchId": str(row["batch_id"]), "gdStudentId": str(row["gd_student_id"]), "studentName": row.get("student_name") or "",
        "studentNo": row.get("student_no") or "", "className": row.get("class_name"), "majorName": row.get("major_name"),
        "topicTitle": row.get("topic_title") or "", "advisorName": row.get("advisor_name") or "", "reviewerName": row.get("reviewer_name") or "",
        "reviewerMentorId": str(row.get("reviewer_mentor_id")) if row.get("reviewer_mentor_id") is not None else None,
        "status": row.get("status"), "statusLabel": STATUS_LABELS.get(str(row.get("status") or ""), str(row.get("status") or "")),
        "statusGroup": row.get("status_group"), "submittedAt": row.get("submitted_at").isoformat() if hasattr(row.get("submitted_at"), "isoformat") else row.get("submitted_at"),
        "assignedAt": row.get("assigned_at").isoformat() if hasattr(row.get("assigned_at"), "isoformat") else row.get("assigned_at"),
        "startedAt": row.get("started_at").isoformat() if hasattr(row.get("started_at"), "isoformat") else row.get("started_at"),
        "reviewedAt": row.get("reviewed_at").isoformat() if hasattr(row.get("reviewed_at"), "isoformat") else row.get("reviewed_at"),
        "materialCode": row.get("material_code"), "materialName": row.get("material_name"),
        "materialId": str(row.get("material_id")) if row.get("material_id") is not None else None,
        "fileId": str(row.get("file_id")) if row.get("file_id") is not None else None,
        "fileVersionId": str(row.get("file_version_id")) if row.get("file_version_id") is not None else None,
        "versionNo": row.get("version_no"), "fileName": row.get("file_name"), "mimeType": row.get("mime_type"), "sourceSha256": row.get("source_sha256"),
        "reviewReady": ready, "versionConflict": bool(row.get("version_conflict")), "blockingReasons": blockers,
        "score": row.get("score"), "latestFeedback": latest_feedback, "allowedActions": _allowed(str(row["case_type"]), str(row.get("status") or ""), ready),
        "deadlineAt": deadline.isoformat() if deadline else None, "overdue": _is_overdue(row, deadlines, now), "canonicalFile": _descriptor(row),
    }


def _base_params(batch_id: int, scope_ids: list[int]) -> dict:
    return {"tenant_id": int(_tid()), "batch_id": int(batch_id), "scope_ids": scope_ids or [-1]}


def list_tasks(*, batch_id: int, page: int, page_size: int, case_type=None, status_group=None,
               keyword=None, reviewer_only: bool = False, sort: str | None = None) -> tuple[list[dict], int]:
    sort_key = str(sort or "PRIORITY").upper()
    if sort_key not in SORTS: raise AppException("VALIDATION_ERROR", "sort 不支持")
    with session() as db:
        scope_ids = accessible_student_ids(db, int(_tid()), batch_id=int(batch_id))
        reviewer_id, reviewer_name = _current_reviewer(db)
        where, extra = _filters(case_type, status_group, keyword, reviewer_only, reviewer_id, reviewer_name)
        params = {**_base_params(batch_id, scope_ids), **extra}
        stmt_count = text(_CTE + "SELECT COUNT(*) FROM projected" + where).bindparams(bindparam("scope_ids", expanding=True))
        total = int(db.execute(stmt_count, params).scalar() or 0)
        # Database performs count and a bounded candidate page; priority ordering is finalized on the bounded page
        # after conservative deadlines are loaded. LIMIT/OFFSET are never applied in Python to a full projection.
        if sort_key == "LATEST": order = " ORDER BY COALESCE(reviewed_at,submitted_at,assigned_at,created_at) DESC,record_id DESC"
        elif sort_key == "EARLIEST": order = " ORDER BY COALESCE(reviewed_at,submitted_at,assigned_at,created_at) ASC,record_id ASC"
        elif sort_key == "STUDENT_NO": order = " ORDER BY student_no ASC,student_name ASC,case_type ASC,record_id ASC"
        elif sort_key == "STATUS": order = " ORDER BY status_group ASC,case_type ASC,record_id ASC"
        else:
            # RETURNED first; overdue is re-ranked within the bounded priority window using batch deadlines.
            order = " ORDER BY CASE WHEN status_group='RETURNED' THEN 0 WHEN status_group='DONE' THEN 9 WHEN case_type IN ('FINAL','FINAL_DRAFT') THEN 2 WHEN case_type='FORMAL_REVIEW' THEN 3 WHEN case_type='PROPOSAL' THEN 4 ELSE 5 END, COALESCE(reviewed_at,submitted_at,assigned_at,created_at),record_id"
        page_size = max(1, min(200, int(page_size))); page = max(1, int(page))
        params.update({"limit": page_size, "offset": (page - 1) * page_size})
        stmt = text(_CTE + "SELECT * FROM projected" + where + order + " LIMIT :limit OFFSET :offset").bindparams(bindparam("scope_ids", expanding=True))
        rows = [dict(r) for r in db.execute(stmt, params).mappings().all()]
        deadlines = _batch_deadlines(db, int(batch_id)); now = datetime.now(timezone.utc)
        if sort_key == "PRIORITY": rows.sort(key=lambda r: _priority_key(r, deadlines, now))
        keys = [("PROPOSAL" if r["case_type"] == "PROPOSAL" else "FORMAL" if r["case_type"] == "FORMAL_REVIEW" else "FINAL", int(r["record_id"])) for r in rows]
        latest = feedback.feedback_for_sources(db, keys)
        return [_public(r, deadlines, now, latest.get((keys[i][0], str(keys[i][1])))) for i, r in enumerate(rows)], total


def summary(batch_id: int) -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, int(_tid()), batch_id=int(batch_id))
        stmt = text(_CTE + "SELECT case_type,status_group,submitted_at,assigned_at,started_at,reviewed_at FROM projected").bindparams(bindparam("scope_ids", expanding=True))
        rows = [dict(r) for r in db.execute(stmt, _base_params(batch_id, scope_ids)).mappings().all()]
        deadlines = _batch_deadlines(db, int(batch_id)); now = datetime.now(timezone.utc); today = now.date()
        groups = {g: 0 for g in STATUS_GROUPS}; by_type = {c: {"caseType": c, "total": 0, "pending": 0, "inReview": 0, "returned": 0, "done": 0, "blocked": 0} for c in CASE_TYPES}
        durations=[]; done_today=0; overdue=0
        for row in rows:
            g=str(row.get("status_group") or "BLOCKED"); c=str(row.get("case_type")); groups[g]=groups.get(g,0)+1; slot=by_type[c]; slot["total"]+=1
            slot[{"WAITING":"pending","IN_REVIEW":"inReview","RETURNED":"returned","DONE":"done","BLOCKED":"blocked"}.get(g,"blocked")]+=1
            reviewed=_parse_dt(row.get("reviewed_at")); start=_parse_dt(row.get("started_at") or row.get("assigned_at") or row.get("submitted_at"))
            if g=="DONE" and reviewed and reviewed.date()==today: done_today+=1
            if _is_overdue(row, deadlines, now): overdue+=1
            if reviewed and start and reviewed>=start: durations.append((reviewed-start).total_seconds()/3600.0)
        return {"batchId": str(batch_id), "pending": groups.get("WAITING",0)+groups.get("BLOCKED",0), "inReview": groups.get("IN_REVIEW",0),
                "returned": groups.get("RETURNED",0), "doneToday": done_today, "overdue": overdue,
                "avgHours": round(sum(durations)/len(durations),2) if durations else None, "byType": [by_type[k] for k in sorted(by_type)],
                "total": len(rows), "blocked": groups.get("BLOCKED",0), "groups": groups}


def detail(*, batch_id: int, case_type: str, record_id: int) -> dict:
    case_type = str(case_type).upper()
    if case_type not in CASE_TYPES: raise AppException("VALIDATION_ERROR", "caseType 不支持")
    with session() as db:
        scope_ids = accessible_student_ids(db, int(_tid()), batch_id=int(batch_id))
        params = _base_params(batch_id, scope_ids); params.update({"case_type": case_type, "record_id": int(record_id)})
        stmt = text(_CTE + "SELECT * FROM projected WHERE case_type=:case_type AND record_id=:record_id LIMIT 1").bindparams(bindparam("scope_ids", expanding=True))
        raw = db.execute(stmt, params).mappings().first()
        if not raw: raise not_found("评阅任务不存在或不在当前数据范围内")
        row=dict(raw); deadlines=_batch_deadlines(db,int(batch_id)); now=datetime.now(timezone.utc)
        stage = "PROPOSAL" if case_type=="PROPOSAL" else "FORMAL" if case_type=="FORMAL_REVIEW" else "FINAL"
        histories=feedback.feedback_for_sources(db,[(stage,int(record_id))],history=True); history=histories.get((stage,str(record_id)),[])
        latest=history[-1] if history else None; case=_public(row,deadlines,now,latest)
        versions=[]
        if row.get("asset_id"):
            vrows=db.execute(text(
                "SELECT fv.id file_version_id,fv.version_no,fv.status version_status,fo.id file_id,fo.file_name,fo.mime_type,fo.status file_status,fo.scan_status,fo.sha256 source_sha256 "
                "FROM t_file_version fv JOIN t_file_object fo ON fo.id=fv.file_object_id AND fo.tenant_id=fv.tenant_id AND fo.is_deleted=0 "
                "WHERE fv.tenant_id=:tenant_id AND fv.asset_id=:asset_id AND fv.is_deleted=0 ORDER BY fv.version_no ASC"
            ),{"tenant_id":int(_tid()),"asset_id":int(row["asset_id"])}).mappings().all()
            versions=[_descriptor(dict(v)) for v in vrows]
        plag=None
        if row.get("gd_final_id"):
            p=db.execute(text("SELECT id,status,rate,threshold,over_threshold,dispute_status,dispute_comment,submit_at FROM t_gd_plagiarism WHERE tenant_id=:tenant_id AND gd_final_id=:fid AND is_deleted=0 ORDER BY id DESC LIMIT 1"),{"tenant_id":int(_tid()),"fid":int(row["gd_final_id"])}).mappings().first()
            plag=dict(p) if p else None
        return {"case": case, "student": {"gdStudentId":case["gdStudentId"],"studentName":case["studentName"],"studentNo":case["studentNo"],"className":case["className"],"majorName":case["majorName"],"topicTitle":case["topicTitle"],"advisorName":case["advisorName"]},
                "canonicalMaterial": {"materialId":case["materialId"],"materialCode":case["materialCode"],"materialName":case["materialName"]},
                "canonicalFile": case.get("canonicalFile"), "frozenFile": _descriptor(row), "versionHistory": versions,
                "feedbackHistory": history, "plagiarism": plag, "blockers": case["blockingReasons"], "allowedActions": case["allowedActions"],
                "deadlineAt": case["deadlineAt"], "overdue": case["overdue"]}
