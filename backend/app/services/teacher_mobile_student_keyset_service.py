"""Teacher Miniapp V3 T3 MyStudents keyset/search read service.

This is additive to the legacy ``mobile_teacher_service.my_students`` surface. It removes the
legacy 200-row ceiling for the V3 path while keeping object scope server-authoritative:
- classId/search only narrow an already-authorized SQL set;
- advisor roles keep the canonical exclusive business-relation boundary;
- the list is true keyset pagination, never ``LIMIT 200`` + client-side slicing.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import mobile_teacher_service as teacher_guard
from app.services.db_service import _tid, session
from app.services.teacher_student_visibility_service import (
    compile_teacher_mobile_student_visibility,
    teacher_user_id,
)

_CURSOR_VERSION = 1
_CURSOR_KIND = "teacherStudents"
_MAX_CURSOR_LENGTH = 2048
_PAGE_SIZE_DEFAULT = 20
_PAGE_SIZE_MAX = 100
_SORT_CONTRACT = "studentNo:asc,id:asc"


def _validation_error(message: str) -> AppException:
    return AppException("VALIDATION_ERROR", message, details={"reason": "INVALID_STUDENT_CURSOR"})


def _normalize_class_id(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise _validation_error("classId 不合法") from exc
    if parsed <= 0:
        raise _validation_error("classId 不合法")
    return parsed


def _normalize_keyword(value: str | None) -> str:
    keyword = str(value or "").strip()
    if len(keyword) > 100:
        raise _validation_error("搜索关键字过长")
    return keyword


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="microseconds") if value else None


def _parse_dt(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except (TypeError, ValueError) as exc:
        raise _validation_error("cursor asOf 不合法") from exc
    if parsed.tzinfo is not None:
        raise _validation_error("cursor asOf 时区格式不合法")
    return parsed


def _filter_hash(user: dict, *, class_id: int | None, keyword: str) -> str:
    payload = {
        "client": "teacherMini",
        "kind": _CURSOR_KIND,
        "tenantId": int(_tid() or 0),
        "userId": teacher_user_id(user),
        "classId": class_id or 0,
        "keyword": keyword,
        "sort": _SORT_CONTRACT,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(token: str) -> bytes:
    return base64.urlsafe_b64decode((token + "=" * (-len(token) % 4)).encode("ascii"))


def _signature(raw: bytes) -> bytes:
    secret = str(settings.jwt_secret or "").encode("utf-8")
    if not secret:
        raise AppException("SERVER_ERROR", "游标签名密钥未配置", details={"reason": "CURSOR_SIGNING_KEY_MISSING"})
    return hmac.new(secret, raw, hashlib.sha256).digest()


def _encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{_b64encode(raw)}.{_b64encode(_signature(raw))}"


def _decode_cursor(cursor: str, *, expected_filter_hash: str) -> dict[str, Any]:
    token = str(cursor or "").strip()
    if not token or len(token) > _MAX_CURSOR_LENGTH or token.count(".") != 1:
        raise _validation_error("cursor 为空、过长或格式不合法")
    try:
        body_token, sig_token = token.split(".", 1)
        raw = _b64decode(body_token)
        supplied_sig = _b64decode(sig_token)
        if not hmac.compare_digest(supplied_sig, _signature(raw)):
            raise _validation_error("cursor 签名校验失败")
        payload = json.loads(raw.decode("utf-8"))
    except AppException:
        raise
    except (ValueError, TypeError, binascii.Error, UnicodeError, json.JSONDecodeError) as exc:
        raise _validation_error("cursor 无法解析") from exc
    if not isinstance(payload, dict):
        raise _validation_error("cursor 内容不合法")
    if int(payload.get("v") or 0) != _CURSOR_VERSION or payload.get("kind") != _CURSOR_KIND:
        raise _validation_error("cursor 版本或类型不兼容")
    if str(payload.get("filterHash") or "") != expected_filter_hash:
        raise _validation_error("cursor 与当前筛选条件不一致")
    student_no = str(payload.get("studentNo") or "").strip()
    try:
        row_id = int(payload.get("id") or 0)
        total = int(payload.get("total") or 0)
    except (TypeError, ValueError) as exc:
        raise _validation_error("cursor 排序键不合法") from exc
    if not student_no or row_id <= 0 or total < 0:
        raise _validation_error("cursor 排序键不合法")
    _parse_dt(payload.get("asOf"))
    payload["studentNo"] = student_no
    payload["id"] = row_id
    payload["total"] = total
    return payload


def list_continuous(
    user: dict,
    *,
    class_id=None,
    keyword: str | None = None,
    cursor: str | None = None,
    page_size: int = _PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    """Return one stable MyStudents page with object-scope intersection and server search."""
    from app.models import SchoolClass, StudentProfile

    teacher_guard._require_teacher(user)
    normalized_class_id = _normalize_class_id(class_id)
    normalized_keyword = _normalize_keyword(keyword)
    size = max(1, min(_PAGE_SIZE_MAX, int(page_size or _PAGE_SIZE_DEFAULT)))
    filter_hash = _filter_hash(user, class_id=normalized_class_id, keyword=normalized_keyword)
    first_page = not bool(str(cursor or "").strip())

    if first_page:
        as_of = datetime.utcnow()
        cursor_payload = None
        total = 0
    else:
        cursor_payload = _decode_cursor(str(cursor), expected_filter_hash=filter_hash)
        as_of = _parse_dt(cursor_payload.get("asOf"))
        total = int(cursor_payload.get("total") or 0)

    student = aliased(StudentProfile, name="visible_student")
    class_row = aliased(SchoolClass, name="student_class")
    scope = teacher_guard.resolve_teacher_scope(user)
    object_visibility = compile_teacher_mobile_student_visibility(
        user, student.id, scope=scope,
    )

    conds = [
        student.tenant_id == _tid(),
        student.is_deleted.is_(False),
        student.created_at <= as_of,
        object_visibility,
    ]
    if normalized_class_id is not None:
        # Critical: classId narrows *after* visibility; it can never bypass object scope.
        conds.append(student.class_id == normalized_class_id)
    if normalized_keyword:
        pattern = f"%{_escape_like(normalized_keyword)}%"
        conds.append(or_(
            student.student_no.like(pattern, escape="\\"),
            student.real_name.like(pattern, escape="\\"),
        ))
    if cursor_payload is not None:
        last_no = str(cursor_payload["studentNo"])
        last_id = int(cursor_payload["id"])
        conds.append(or_(
            student.student_no > last_no,
            and_(student.student_no == last_no, student.id > last_id),
        ))

    with session() as db:
        if first_page:
            total = int(db.scalar(select(func.count()).select_from(student).where(*conds)) or 0)

        rows = db.execute(
            select(student, class_row.class_name)
            .outerjoin(
                class_row,
                and_(
                    class_row.id == student.class_id,
                    class_row.tenant_id == _tid(),
                    class_row.is_deleted.is_(False),
                ),
            )
            .where(*conds)
            .order_by(student.student_no.asc(), student.id.asc())
            .limit(size + 1)
        ).all()

    has_more = len(rows) > size
    page_rows = rows[:size]
    items = [
        {
            "studentId": str(row.id),
            "studentNo": row.student_no,
            "name": row.real_name,
            "classId": str(row.class_id) if row.class_id else None,
            "className": class_name or "",
            "gender": row.gender or "",
            "stage": row.current_stage,
            "status": row.student_status,
        }
        for row, class_name in page_rows
    ]

    next_cursor = None
    if has_more and page_rows:
        last_row = page_rows[-1][0]
        next_cursor = _encode_cursor({
            "v": _CURSOR_VERSION,
            "kind": _CURSOR_KIND,
            "filterHash": filter_hash,
            "asOf": _iso(as_of),
            "studentNo": last_row.student_no,
            "id": int(last_row.id),
            "total": int(total),
        })

    return {
        "items": items,
        "total": int(total),
        "pageSize": size,
        "nextCursor": next_cursor,
        "hasMore": has_more,
        "filterHash": filter_hash,
        "asOf": _iso(as_of),
    }
