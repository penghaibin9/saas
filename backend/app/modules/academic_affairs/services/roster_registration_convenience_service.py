"""D2-U 学籍名册/注册便利性服务。

只提供候选 enrich、批量预览和批量编排；不新增事实表，不直接写学生主档。
最终注册逐项复用 academic_affairs_service.register_student() canonical 写入口。
批量确认必须携带服务端签发的短时 previewToken，禁止跳过预览直接写入。
候选列表与 preview 在 SQL 侧完成 dataScope/状态/分页或定点收窄，禁止先 materialize 全校候选。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from contextlib import contextmanager

from sqlalchemy import and_, func, or_, select, text

from app.core.affairs_security import build_affairs_context
from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.models import AaRegistration, AaRegistrationBatch, Major, SchoolClass, StudentProfile
from app.modules.academic_affairs.services import academic_affairs_service as svc
from app.services.db_service import _tid, session


_MAX_BULK = 100
_PREVIEW_TTL_SECONDS = 10 * 60
_TOKEN_CONTEXT = b"aa-registration-preview-v1"
_LOCK_TIMEOUT_SECONDS = 5


def _status_label(status: str | None) -> str:
    return svc._STATUS_LABEL.get(status, status or "—")


def _explanation(batch, registration, student) -> str:
    elig = registration.eligibility_status if registration else "PENDING"
    note = ((registration.eligibility_note if registration else "") or "").strip()
    if elig == "INELIGIBLE":
        return note or "资格核验不通过，请先在“注册异常”处理后再注册"
    if elig == "ELIGIBLE":
        return note or "资格核验已通过"
    kind = {"ENROLL": "入学", "ANNUAL": "学年", "SEMESTER": "学期"}.get(batch.register_type, "当前")
    return f"系统已按{kind}注册候选规则圈定；当前学籍状态为{_status_label(student.student_status)}，资格尚待核验"


@contextmanager
def registration_mutex(batch_id, student_id):
    """跨 worker 的注册临界区。

    MySQL 为项目权威数据库：使用 GET_LOCK 对 tenant+batch+student 做短时互斥，锁名只存哈希，
    不泄露业务主键。锁仅覆盖最终 recheck + canonical register，不包 preview/列表查询。
    非 MySQL 开发数据库保持兼容直通；生产并发合同由 MySQL 集成测试负责。
    """
    lock_db = session()
    acquired = False
    try:
        dialect = lock_db.get_bind().dialect.name
        if dialect == "mysql":
            raw = f"{_tid()}:{int(batch_id)}:{int(student_id)}".encode("utf-8")
            lock_name = "aa-reg:" + hashlib.sha256(raw).hexdigest()[:48]
            acquired = lock_db.execute(
                text("SELECT GET_LOCK(:lock_name, :timeout_seconds)"),
                {"lock_name": lock_name, "timeout_seconds": _LOCK_TIMEOUT_SECONDS},
            ).scalar() == 1
            if not acquired:
                raise AppException(
                    "DATA_CONFLICT",
                    "同一学生的注册正在处理中，请稍后重新预览后再确认",
                    http_status=409,
                )
        yield
    finally:
        if acquired:
            try:
                lock_db.execute(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": lock_name})
            except Exception:
                # 连接断开时 MySQL 会自动释放命名锁；不得用释放失败覆盖原业务异常。
                pass
        lock_db.close()


def _enrich_pairs(db, batch, pairs):
    students = [s for s, _r in pairs]
    class_ids = {int(s.class_id) for s in students if s.class_id}
    major_ids = {int(s.major_id) for s in students if s.major_id}
    classes = {}
    if class_ids:
        classes = {
            c.id: c for c in db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.id.in_(list(class_ids)),
                SchoolClass.is_deleted.is_(False),
            )).all()
        }
        major_ids.update(int(c.major_id) for c in classes.values() if c.major_id)
    majors = {}
    if major_ids:
        majors = {
            m.id: m for m in db.scalars(select(Major).where(
                Major.tenant_id == _tid(),
                Major.id.in_(list(major_ids)),
                Major.is_deleted.is_(False),
            )).all()
        }

    out = []
    for student, registration in pairs:
        cls = classes.get(student.class_id)
        major_id = student.major_id or (cls.major_id if cls else None)
        major = majors.get(major_id)
        elig = registration.eligibility_status if registration else "PENDING"
        out.append({
            "studentId": str(student.id),
            "studentNo": student.student_no or "",
            "realName": student.real_name or "",
            "className": cls.class_name if cls else "",
            "majorName": major.major_name if major else "",
            "currentStatus": student.student_status or "",
            "currentStatusLabel": _status_label(student.student_status),
            "registrationStatus": registration.status if registration else "PENDING_REGISTER",
            "eligibilityStatus": elig,
            "eligibilityNote": ((registration.eligibility_note if registration else "") or ""),
            "eligibilityExplanation": _explanation(batch, registration, student),
        })
    return out


def enrich_eligibility_class_names(items: list[dict]) -> list[dict]:
    """给既有资格核验响应增补 className；classId 继续保留兼容，但页面不再展示内部 ID。"""
    class_ids = {
        int(row["classId"])
        for row in items or []
        if str(row.get("classId") or "").isdigit()
    }
    if not class_ids:
        return [{**row, "className": ""} for row in items or []]
    with session() as db:
        classes = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(),
            SchoolClass.id.in_(list(class_ids)),
            SchoolClass.is_deleted.is_(False),
        )).all()
        names = {int(row.id): row.class_name or "" for row in classes}
    return [
        {
            **row,
            "className": names.get(int(row["classId"]), "")
            if str(row.get("classId") or "").isdigit() else "",
        }
        for row in items or []
    ]


def _candidate_join(batch):
    return and_(
        AaRegistration.tenant_id == _tid(),
        AaRegistration.batch_id == batch.id,
        AaRegistration.student_id == StudentProfile.id,
        AaRegistration.is_deleted.is_(False),
    )


def _candidate_conditions(batch, allowed, *, student_ids=None, status=None, keyword=None):
    """D2-U SQL 候选合同：与 canonical 状态池一致，但把范围/过滤真正下推数据库。"""
    if allowed is not None and not allowed:
        return None
    conds = [
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
        StudentProfile.student_status.in_(svc._batch_target_statuses(batch)),
        or_(AaRegistration.id.is_(None), AaRegistration.status != "REGISTERED"),
    ]
    if allowed is not None:
        conds.append(StudentProfile.class_id.in_(allowed))
    if student_ids is not None:
        conds.append(StudentProfile.id.in_(student_ids))
    if status:
        if status == "PENDING":
            conds.append(or_(AaRegistration.id.is_(None), AaRegistration.eligibility_status == "PENDING"))
        else:
            conds.append(AaRegistration.eligibility_status == status)
    if keyword:
        term = str(keyword).strip()
        if term:
            conds.append(or_(StudentProfile.real_name.contains(term), StudentProfile.student_no.contains(term)))
    return conds


def _query_candidate_pairs(db, batch, allowed, *, student_ids=None, status=None, keyword=None,
                           page=None, page_size=None):
    """SQL 侧候选查询。列表真分页；preview 仅查最多 100 个选中 ID，不扫全校。"""
    conds = _candidate_conditions(
        batch, allowed, student_ids=student_ids, status=status, keyword=keyword
    )
    if conds is None:
        return [], 0
    join = _candidate_join(batch)
    total = db.scalar(
        select(func.count(StudentProfile.id))
        .select_from(StudentProfile)
        .outerjoin(AaRegistration, join)
        .where(*conds)
    ) or 0
    stmt = (
        select(StudentProfile, AaRegistration)
        .outerjoin(AaRegistration, join)
        .where(*conds)
        .order_by(StudentProfile.id.desc())
    )
    if page is not None and page_size is not None:
        safe_page = max(1, int(page))
        safe_size = max(1, int(page_size))
        stmt = stmt.offset((safe_page - 1) * safe_size).limit(safe_size)
    return db.execute(stmt).all(), int(total)


def list_registration_candidates(batch_id, user, *, status=None, keyword=None, page=1, page_size=20):
    """权威候选 + 人类可读组织/状态；SQL 真分页，避免学校大名单全量 materialize。"""
    with session() as db:
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("注册批次不存在")
        ctx = build_affairs_context(user, db)
        allowed = ctx.allowed_class_ids(db)
        pairs, total = _query_candidate_pairs(
            db, batch, allowed, status=status, keyword=keyword, page=page, page_size=page_size
        )
        return _enrich_pairs(db, batch, pairs), total


def _validate_ids(student_ids) -> list[int]:
    ids = []
    seen = set()
    for raw in student_ids or []:
        try:
            sid = int(raw)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "学生 ID 非法")
        if sid <= 0:
            raise AppException("VALIDATION_ERROR", "学生 ID 非法")
        if sid in seen:
            continue
        seen.add(sid)
        ids.append(sid)
    if not ids:
        raise AppException("VALIDATION_ERROR", "请至少选择 1 名学生")
    if len(ids) > _MAX_BULK:
        raise AppException("VALIDATION_ERROR", f"单次最多处理 {_MAX_BULK} 名学生")
    return ids


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _signing_key() -> bytes:
    return hmac.new(settings.jwt_secret.encode("utf-8"), _TOKEN_CONTEXT, hashlib.sha256).digest()


def _preview_snapshot(preview: dict) -> str:
    """只签稳定业务事实，避免展示文案变化导致 token 无意义失效。"""
    stable = {
        "batchId": preview.get("batchId"),
        "batchStatus": preview.get("batchStatus"),
        "items": [
            {
                "studentId": item.get("studentId"),
                "status": item.get("status"),
                "code": item.get("code"),
                "currentStatus": item.get("currentStatus"),
                "registrationStatus": item.get("registrationStatus"),
                "eligibilityStatus": item.get("eligibilityStatus"),
            }
            for item in preview.get("items") or []
        ],
    }
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _issue_preview_token(batch_id: int, student_ids: list[int], snapshot: str) -> str:
    now = int(time.time())
    payload = {
        "v": 1,
        "tenantId": str(_tid()),
        "batchId": str(int(batch_id)),
        "studentIds": [str(x) for x in student_ids],
        "snapshot": snapshot,
        "iat": now,
        "exp": now + _PREVIEW_TTL_SECONDS,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_signing_key(), raw, hashlib.sha256).digest()
    return f"{_b64encode(raw)}.{_b64encode(sig)}"


def _decode_preview_token(preview_token: str, batch_id: int) -> dict:
    try:
        raw_part, sig_part = (preview_token or "").split(".", 1)
        raw = _b64decode(raw_part)
        supplied = _b64decode(sig_part)
        expected = hmac.new(_signing_key(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("bad signature")
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        raise AppException("VALIDATION_ERROR", "批量注册预览凭证无效，请重新预览")
    if payload.get("v") != 1 or payload.get("tenantId") != str(_tid()):
        raise AppException("VALIDATION_ERROR", "批量注册预览凭证无效，请重新预览")
    if payload.get("batchId") != str(int(batch_id)):
        raise AppException("VALIDATION_ERROR", "预览凭证与当前注册批次不匹配，请重新预览")
    if int(payload.get("exp") or 0) < int(time.time()):
        raise AppException("DATA_CONFLICT", "批量注册预览已过期，请重新预览", http_status=409)
    payload["studentIds"] = _validate_ids(payload.get("studentIds") or [])
    return payload


def bulk_register_preview(batch_id, user, student_ids):
    """零写入预览。未知/越权/非候选 studentId 只返回通用 BLOCKED，不泄露他人资料。"""
    ids = _validate_ids(student_ids)
    with session() as db:
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("注册批次不存在")
        ctx = build_affairs_context(user, db)
        allowed = ctx.allowed_class_ids(db)
        selected_pairs, _ = _query_candidate_pairs(db, batch, allowed, student_ids=ids)
        by_id = {s.id: (s, r) for s, r in selected_pairs}
        enriched = {int(row["studentId"]): row for row in _enrich_pairs(db, batch, selected_pairs)}

        items = []
        ready = 0
        for sid in ids:
            pair = by_id.get(sid)
            if pair is None:
                items.append({
                    "studentId": str(sid), "status": "BLOCKED", "code": "NOT_AVAILABLE",
                    "message": "该学生不在当前可注册候选范围内",
                })
                continue
            _student, registration = pair
            row = enriched[sid]
            if batch.status != "OPEN":
                status, code, message = "BLOCKED", "DATA_CONFLICT", "注册批次未开放或已关闭"
            elif registration and registration.eligibility_status == "INELIGIBLE":
                status, code, message = "BLOCKED", "INELIGIBLE", row["eligibilityExplanation"]
            else:
                status, code, message = "READY", "", "可提交注册；确认时系统会再次执行正式校验"
                ready += 1
            items.append({**row, "status": status, "code": code, "message": message})
        preview = {
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "batchStatus": batch.status,
            "selected": len(ids),
            "ready": ready,
            "blocked": len(ids) - ready,
            "items": items,
        }
    snapshot = _preview_snapshot(preview)
    preview["previewToken"] = _issue_preview_token(batch_id, ids, snapshot) if ready else None
    preview["previewExpiresIn"] = _PREVIEW_TTL_SECONDS if ready else 0
    return preview


def _final_ready_check(batch_id, user, student_id) -> tuple[bool, str, str]:
    """确认前逐项重检 dataScope + 候选身份 + 显式不合格；只读且按主键定点查询。"""
    with session() as db:
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            return False, "NOT_FOUND", "注册批次不存在"
        if batch.status != "OPEN":
            return False, "DATA_CONFLICT", "注册批次未开放或已关闭"
        ctx = build_affairs_context(user, db)
        try:
            student = ctx.require_student(db, int(student_id))
        except AppException:
            return False, "NOT_AVAILABLE", "该学生不在当前可注册候选范围内"
        if student.student_status not in svc._batch_target_statuses(batch):
            return False, "NOT_AVAILABLE", "该学生不在当前可注册候选范围内"
        registration = db.scalars(select(AaRegistration).where(
            AaRegistration.tenant_id == _tid(),
            AaRegistration.batch_id == batch.id,
            AaRegistration.student_id == int(student_id),
            AaRegistration.is_deleted.is_(False),
        )).first()
        if registration and registration.status == "REGISTERED":
            return False, "DATA_CONFLICT", "该生已在本批次完成注册"
        if registration and registration.eligibility_status == "INELIGIBLE":
            return False, "INELIGIBLE", ((registration.eligibility_note or "").strip()
                                           or "资格核验不通过，请先处理注册异常")
        return True, "", ""


def _apply_preview(batch_id, user, preview):
    items = []
    for item in preview["items"]:
        sid = int(item["studentId"])
        if item["status"] != "READY":
            items.append({
                "studentId": item["studentId"],
                "ok": False,
                "code": item["code"],
                "message": item["message"],
            })
            continue
        with registration_mutex(batch_id, sid):
            # 必须在拿到跨 worker 锁后重检；两个并发 confirm 即便同时通过 token snapshot，
            # 第二个也会在这里看到第一个已经落下的 REGISTERED 事实并 fail closed。
            ready, code, message = _final_ready_check(batch_id, user, sid)
            if not ready:
                items.append({
                    "studentId": str(sid), "ok": False,
                    "code": code, "message": message,
                })
                continue
            try:
                result = svc.register_student(batch_id, user, sid)
            except AppException as exc:
                items.append({
                    "studentId": str(sid), "ok": False,
                    "code": exc.code, "message": exc.message,
                })
            else:
                items.append({
                    "studentId": str(sid), "ok": True, "code": "",
                    "message": "注册成功",
                    "registrationId": result["registrationId"],
                    "studentStatus": result["studentStatus"],
                    "changeType": result["changeType"],
                })
    success_count = sum(1 for x in items if x["ok"])
    return {
        "batchId": str(batch_id),
        "selected": len(items),
        "succeeded": success_count,
        "failed": len(items) - success_count,
        "items": items,
    }


def bulk_register_confirm(batch_id, user, preview_token):
    """必须先 preview。token 绑定租户/批次/名单/快照，确认前还会重新计算并比对。"""
    token = _decode_preview_token(preview_token, batch_id)
    current = bulk_register_preview(batch_id, user, token["studentIds"])
    if _preview_snapshot(current) != token.get("snapshot"):
        raise AppException("DATA_CONFLICT", "注册名单或资格状态已变化，请重新预览后再确认", http_status=409)
    return _apply_preview(batch_id, user, current)
