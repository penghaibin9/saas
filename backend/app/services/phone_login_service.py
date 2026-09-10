"""Single authority for phone identifier normalization and verified-binding lookup."""
from __future__ import annotations

import re

from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.field_crypto import hash_sensitive

_CN_PHONE = re.compile(r"^(?:\+86)?(1[3-9][0-9]{9})$")
_LOOKUP_FIELD = "phone_login_v1"


def normalize_login_phone(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("手机号必须为文本")
    raw = value.strip()
    match = _CN_PHONE.fullmatch(raw)
    if not match:
        raise ValueError("仅支持中国大陆 11 位手机号；请勿输入掩码、空格或多个号码")
    return "+86" + match.group(1)


def phone_lookup(tenant_id: int, normalized_phone: str) -> str:
    from app.core.config import settings
    if not (settings.SENSITIVE_SEARCH_HMAC_KEY or "").strip():
        raise AppException("AUTH_STORE_UNAVAILABLE", "手机号安全配置尚未就绪，请使用原账号登录", http_status=503)
    normalized_phone = normalize_login_phone(normalized_phone)
    return str(hash_sensitive(f"{int(tenant_id)}\n{normalized_phone}", _LOOKUP_FIELD) or "")


def phone_login_enabled(db, tenant_id: int) -> bool:
    """Read the existing tenant configuration authority explicitly; disabled by default."""
    from app.models import SysConfig
    row = db.scalar(select(SysConfig).where(SysConfig.tenant_id == int(tenant_id),
        SysConfig.config_key == "SEC_PHONE_LOGIN_ENABLED", SysConfig.is_deleted.is_(False)))
    return bool(row and str(row.value_text or "").strip() == "1")


def resolve_verified_phone_user(db, *, tenant_id: int, phone: str):
    from app.models import PhoneLoginBinding, User

    if not phone_login_enabled(db, tenant_id):
        return None
    lookup = phone_lookup(tenant_id, normalize_login_phone(phone))
    return db.scalars(select(User).join(
        PhoneLoginBinding,
        (PhoneLoginBinding.user_id == User.id)
        & (PhoneLoginBinding.tenant_id == User.tenant_id),
    ).where(
        User.tenant_id == int(tenant_id), User.is_deleted.is_(False), User.status == "ACTIVE",
        User.user_type.in_(("STUDENT", "TEACHER", "STAFF", "ADMIN", "SCHOOL_ADMIN")),
        PhoneLoginBinding.state == "VERIFIED", PhoneLoginBinding.active_phone_lookup == lookup,
        PhoneLoginBinding.is_deleted.is_(False),
    )).first()


def require_phone_identifier(tenant_code: str | None, identifier: str | None) -> str:
    if not str(tenant_code or "").strip():
        raise AppException("SCHOOL_CONTEXT_REQUIRED", "手机号登录前请选择或填写学校编码", http_status=422)
    try:
        return normalize_login_phone(str(identifier or ""))
    except ValueError as exc:
        raise AppException("PHONE_FORMAT_INVALID", str(exc), http_status=422) from exc


def create_pending_candidate_in_session(db, *, tenant_id: int, user_id: int, phone: str,
                                        source_kind: str, source_row_no: int | None = None,
                                        expected_version: int | None = None, source_job_id: int | None = None) -> str:
    """Record a SELF candidate without activating it or overwriting a different one."""
    from app.core.field_crypto import encrypt_sensitive
    from app.models import PhoneLoginBinding, PhoneLoginCandidate, User
    from app.services import audit_log

    normalized = normalize_login_phone(phone)
    lookup = phone_lookup(tenant_id, normalized)
    user = db.scalar(select(User).where(User.id == int(user_id), User.tenant_id == int(tenant_id),
        User.is_deleted.is_(False), User.status == "ACTIVE",
        User.user_type.in_(("STUDENT", "TEACHER", "STAFF", "ADMIN", "SCHOOL_ADMIN")),
    ).with_for_update())
    if user is None:
        raise AppException("NO_PERMISSION", "该账号不能登记本人登录号码", http_status=403)
    current = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.tenant_id == int(tenant_id),
        PhoneLoginBinding.user_id == int(user_id)).with_for_update())
    if source_kind == "IDENTITY_IMPORT" and current and current.state == "VERIFIED":
        if current.active_phone_lookup == lookup:
            return "VERIFIED_UNCHANGED"
        raise AppException("DATA_CONFLICT", "已有不同的登录号码，请由本人办理换号", http_status=409)
    occupied = db.scalar(select(PhoneLoginBinding.id).where(PhoneLoginBinding.tenant_id == int(tenant_id),
        PhoneLoginBinding.active_phone_lookup == lookup, PhoneLoginBinding.user_id != int(user_id),
        PhoneLoginBinding.state == "VERIFIED"))
    if occupied:
        raise AppException("PHONE_NOT_AVAILABLE", "该号码不能登记，请核对后再试", http_status=409)
    row = db.scalars(select(PhoneLoginCandidate).where(
        PhoneLoginCandidate.tenant_id == int(tenant_id), PhoneLoginCandidate.user_id == int(user_id),
    ).with_for_update()).first()
    actual_version = int(row.version or 0) if row else 0
    if expected_version is not None and (type(expected_version) is not int or expected_version != actual_version):
        raise AppException("DATA_CONFLICT", "待核验号码已变化，请刷新后重新确认", http_status=409)
    if row is not None:
        if row.is_deleted:
            raise AppException("DATA_CONFLICT", "候选记录状态异常，请联系管理员核对", http_status=409)
        if row.candidate_lookup == lookup and row.state in {"PENDING", "CONFLICT"}:
            return "UNCHANGED"
        if expected_version is None and row.state != 'CLEARED':
            raise AppException("DATA_CONFLICT", "该账号已有不同的待核验手机号，请先在账号安全中明确处理", http_status=409)
    else:
        row = PhoneLoginCandidate(tenant_id=int(tenant_id), user_id=int(user_id), version=0)
        db.add(row)
    row.candidate_phone_ciphertext = encrypt_sensitive(normalized, "phone_login_candidate")
    row.candidate_lookup = lookup
    row.owner_type, row.state, row.source_kind = "SELF", "PENDING", source_kind
    row.source_row_no = source_row_no
    row.source_job_id = source_job_id
    row.version = actual_version + 1
    audit_log.record_critical_in_session(db, "PHONE_CANDIDATE_CHANGE", f"user:{user_id}",
        detail={"source": source_kind, "version": row.version, "sourceRowNo": source_row_no},
        tenant_id=tenant_id, resource_id=str(user_id))
    return "CREATED" if actual_version == 0 else "UPDATED"


def preview_import_phones(db, tenant_id: int, body: dict, report: dict) -> None:
    """Bounded phone preflight alongside the original identity preview, never phone-to-user matching."""
    from itertools import chain, islice
    from sqlalchemy import or_
    from app.models import User, PhoneLoginBinding, PhoneLoginCandidate
    rows = chain(((r, 'student', 'studentNo') for r in body.get('students') or []),
                 ((r, 'teacher', 'loginName') for r in body.get('teachers') or []))
    counts = report.setdefault('phoneSummary', {'phoneEmpty': 0, 'phonePending': 0, 'phoneVerifiedUnchanged': 0,
        'phoneCandidateUnchanged': 0, 'phoneConflict': 0, 'contactPhoneOnly': 0})
    while chunk := list(islice(rows, 500)):
        selected = []
        for row, entity, key in chunk:
            report.setdefault('warnings', []).extend(row.get('_phoneWarnings') or [])
            if not row.get('selfPhone'):
                counts['contactPhoneOnly' if row.get('contactPhone') else 'phoneEmpty'] += 1
                continue
            if row.get('phoneOwnerType', '').upper() != 'SELF':
                continue
            try:
                selected.append((row, entity, str(row.get(key) or ''), phone_lookup(tenant_id, row['selfPhone'])))
            except ValueError:
                continue  # Original row validator reports the malformed field.
        if not selected:
            continue
        users = {u.login_name: u for u in db.scalars(select(User).where(User.tenant_id == tenant_id,
            User.login_name.in_([r[2] for r in selected])))}
        ids = [u.id for u in users.values()]
        bindings = list(db.scalars(select(PhoneLoginBinding).where(PhoneLoginBinding.tenant_id == tenant_id,
            or_(PhoneLoginBinding.user_id.in_(ids), PhoneLoginBinding.active_phone_lookup.in_([r[3] for r in selected])))))
        by_user = {b.user_id: b for b in bindings}
        occupied = {b.active_phone_lookup: b for b in bindings if b.state == 'VERIFIED'}
        candidates = {c.user_id: c for c in db.scalars(select(PhoneLoginCandidate).where(
            PhoneLoginCandidate.tenant_id == tenant_id, PhoneLoginCandidate.user_id.in_(ids)))}
        for row, entity, account_no, lookup in selected:
            user = users.get(account_no)
            current = by_user.get(user.id) if user else None
            candidate = candidates.get(user.id) if user else None
            hit = occupied.get(lookup)
            reason = None
            if hit and (not user or hit.user_id != user.id):
                reason = ('PHONE_OCCUPIED', '号码已被其他账号验证占用，请核对；不会合并账号')
            elif current and current.state == 'VERIFIED':
                if current.active_phone_lookup != lookup:
                    reason = ('PHONE_VERIFIED_CONFLICT', '账号已有不同的已验证号码，导入不能覆盖，请本人办理换号')
                else:
                    counts['phoneVerifiedUnchanged'] += 1
            elif candidate and candidate.state != 'CLEARED':
                if candidate.candidate_lookup == lookup and candidate.state in {'PENDING', 'CONFLICT'}:
                    counts['phoneCandidateUnchanged'] += 1
                else:
                    reason = ('PHONE_CANDIDATE_CONFLICT', '账号已有不同的待核验号码，请先明确处理原候选')
            else:
                counts['phonePending'] += 1
            if reason:
                counts['phoneConflict'] += 1
                report['errors'].append({'row': int(row.get('_rowNo') or 0), 'entity': entity,
                    'field': 'selfPhone', 'reasonCode': reason[0], 'error': reason[1]})


def apply_import_phone_fields(db, *, user, row: dict, source_job_id: int | None, report: dict):
    """Part of the existing writer's transaction; contact fill never activates credentials."""
    from app.core.field_crypto import encrypt_field
    db.refresh(user, with_for_update=True)
    if row.get('contactPhone'):
        if not user.phone_encrypted:
            contact = normalize_login_phone(row['contactPhone']).removeprefix('+86')
            user.phone_encrypted = encrypt_field(contact)
            user.phone_hash = hash_sensitive(contact, 'phone')
            report.setdefault('phoneWriteSummary', {}).setdefault('contactFilled', 0)
            report['phoneWriteSummary']['contactFilled'] += 1
        else:
            report.setdefault('phoneWriteSummary', {}).setdefault('contactPreserved', 0)
            report['phoneWriteSummary']['contactPreserved'] += 1
    if str(row.get('phoneOwnerType') or '').upper() == 'SELF' and row.get('selfPhone'):
        result = create_pending_candidate_in_session(db, tenant_id=user.tenant_id, user_id=user.id,
            phone=row['selfPhone'], source_kind='IDENTITY_IMPORT',
            source_row_no=int(row.get('_rowNo') or 0) or None, source_job_id=source_job_id)
        counts = report.setdefault('phoneWriteSummary', {})
        counts[result] = counts.get(result, 0) + 1
