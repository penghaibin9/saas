"""School phone projections and candidate commands over the original User authority."""
from sqlalchemy import select, func, false, or_, and_
from sqlalchemy.orm import aliased

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.permissions import get_effective_permission_patterns, _match, enforce_permission
from app.db.session import get_sessionmaker
from app.models import User, Role, StudentAccountLink, StudentProfile, PhoneLoginBinding, PhoneLoginCandidate
from app.services import auth_service_db, audit_log
from app.services.phone_binding_service import _locked_subject, _masked
from app.services.phone_login_service import phone_lookup, create_pending_candidate_in_session

PREFIX = 'systemAdmin.phoneBinding.'


def _candidate_conflict():
    other = aliased(PhoneLoginCandidate)
    binding = aliased(PhoneLoginBinding)
    occupied = select(binding.id).where(binding.tenant_id == User.tenant_id,
        binding.user_id != User.id, binding.is_deleted.is_(False), binding.state == 'VERIFIED',
        binding.active_phone_lookup == PhoneLoginCandidate.candidate_lookup).correlate(User, PhoneLoginCandidate).exists()
    duplicate = select(other.id).where(other.tenant_id == User.tenant_id, other.user_id != User.id,
        other.is_deleted.is_(False), other.state.in_(['PENDING', 'CONFLICT']),
        other.candidate_lookup == PhoneLoginCandidate.candidate_lookup).correlate(User, PhoneLoginCandidate).exists()
    return and_(PhoneLoginCandidate.state.in_(['PENDING', 'CONFLICT']),
        or_(PhoneLoginCandidate.state == 'CONFLICT', occupied, duplicate))


def authorize(db, ctx, action):
    actor, _ = _locked_subject(db, ctx)
    if current_tenant_id() and int(current_tenant_id()) != actor.tenant_id:
        raise AppException('NO_PERMISSION', '学校上下文不匹配', http_status=403)
    if not str(ctx.get('activeContextId') or '').startswith('role:'):
        raise AppException('NO_PERMISSION', '号码治理需要有效的学校岗位', http_status=403)
    patterns = get_effective_permission_patterns(ctx, strict=True)
    if not _match(PREFIX + action, patterns):
        enforce_permission(ctx, PREFIX + action)  # Preserve canonical denial audit.
        raise AppException('NO_PERMISSION', '缺少号码治理权限', http_status=403)
    role = db.get(Role, int(ctx['activeContextId'][5:]))
    from app.services.role_assignment_scope_service import _raw_role_scope
    scope = _raw_role_scope(db, role)
    return actor, scope, patterns


def scoped_users(db, actor, ctx, scope):
    stmt = select(User).where(User.tenant_id == actor.tenant_id, User.is_deleted.is_(False),
        User.user_type.in_({'STUDENT', 'TEACHER', 'STAFF', 'ADMIN', 'SCHOOL_ADMIN'}))
    if scope in {'SCHOOL', 'TENANT', 'TENANT_ALL'}:
        return stmt
    # Reuse original scope claim resolver and stable StudentAccountLink. Never
    # use parent display IDs to widen a CLASS/STUDENT assignment to a college.
    fresh = {key: ctx[key] for key in ('userId', 'tenantId', 'loginName', 'userType', 'currentRoleCode', 'activeContextId') if key in ctx}
    auth_service_db._inject_org_scope_claims(db, actor, fresh)
    columns = {'COLLEGE': ('collegeIds', StudentProfile.college_id), 'MAJOR': ('majorIds', StudentProfile.major_id),
        'CLASS': ('classIds', StudentProfile.class_id), 'STUDENT': ('studentIds', StudentProfile.id)}
    if scope in columns:
        field, column = columns[scope]
        condition = column.in_([int(value) for value in fresh.get(field, [])])
    elif scope == 'COUNSELOR_CLASSES':
        from app.core.affairs_security import build_affairs_context
        security = build_affairs_context(fresh, db)
        condition = StudentProfile.class_id.in_(security.allowed_class_ids(db) or [])
    else:
        condition = false()  # No generic staff department ownership exists on User.
    linked = select(StudentAccountLink.user_id).join(StudentProfile,
        StudentProfile.id == StudentAccountLink.student_id).where(
        StudentAccountLink.tenant_id == actor.tenant_id, StudentAccountLink.link_status == 'ACTIVE',
        StudentAccountLink.is_deleted.is_(False), StudentProfile.tenant_id == actor.tenant_id,
        StudentProfile.is_deleted.is_(False), condition)
    return stmt.where(User.id.in_(linked))


def _filtered(db, actor, ctx, scope, body):
    from app.modules.system_admin.routers.system_bundle import _account_type_condition
    stmt = scoped_users(db, actor, ctx, scope).outerjoin(PhoneLoginBinding,
        (PhoneLoginBinding.user_id == User.id) & (PhoneLoginBinding.tenant_id == User.tenant_id) & PhoneLoginBinding.is_deleted.is_(False))
    stmt = stmt.outerjoin(PhoneLoginCandidate, (PhoneLoginCandidate.user_id == User.id) &
        (PhoneLoginCandidate.tenant_id == User.tenant_id) & PhoneLoginCandidate.is_deleted.is_(False))
    if body.accountType:
        stmt = stmt.where(_account_type_condition(User, body.accountType, actor.tenant_id))
    if body.userId:
        stmt = stmt.where(User.id == int(body.userId))
    if body.keyword:
        term = '%' + body.keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        stmt = stmt.where(or_(User.login_name.like(term), User.real_name.like(term)))
    if body.phone:
        lookup = phone_lookup(actor.tenant_id, body.phone)
        stmt = stmt.where(or_(PhoneLoginBinding.active_phone_lookup == lookup, PhoneLoginCandidate.candidate_lookup == lookup))
    if body.state == 'UNBOUND':
        stmt = stmt.where(or_(PhoneLoginBinding.id.is_(None), PhoneLoginBinding.state == 'UNBOUND'))
    elif body.state in {'VERIFIED', 'REVOKED'}:
        stmt = stmt.where(PhoneLoginBinding.state == body.state)
    elif body.state in {'PENDING', 'CONFLICT'}:
        stmt = stmt.where(_candidate_conflict() if body.state == 'CONFLICT' else
            and_(PhoneLoginCandidate.state == 'PENDING', ~_candidate_conflict()))
    return stmt


def query(ctx, body):
    with get_sessionmaker()() as db:
        actor, scope, patterns = authorize(db, ctx, 'view')
        if body.phone:
            authorize(db, ctx, 'lookup')
            if len(body.reason.strip()) < 5:
                raise AppException('VALIDATION_ERROR', '精确核对号码需要填写用途')
        stmt = _filtered(db, actor, ctx, scope, body)
        total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        rows = db.execute(stmt.add_columns(PhoneLoginBinding, PhoneLoginCandidate, _candidate_conflict()).order_by(User.id)
            .offset((body.page - 1) * body.pageSize).limit(body.pageSize)).all()
        result = []
        for user, binding, candidate, conflict in rows:
            verified = bool(binding and binding.state == 'VERIFIED')
            result.append({'userId': str(user.id), 'loginName': user.login_name, 'name': user.real_name,
                'userType': user.user_type, 'accountStatus': user.status,
                'state': binding.state if binding else 'UNBOUND', 'phoneMasked': _masked(binding.phone_ciphertext) if verified else '',
                'bindingVersion': int(binding.version) if binding else 0,
                'candidateState': 'CONFLICT' if conflict else candidate.state if candidate else 'NONE', 'candidateVersion': int(candidate.version) if candidate else 0,
                'candidatePhoneMasked': _masked(candidate.candidate_phone_ciphertext) if candidate else '',
                'sourceKind': candidate.source_kind if candidate else '', 'sourceJobId': str(candidate.source_job_id or '') if candidate else '',
                'recoveryFrozen': bool(binding and binding.recovery_frozen),
                'allowedActions': {'candidate': not verified and user.id != actor.id and user.status == 'ACTIVE'
                    and _match(PREFIX + 'candidate.manage', patterns),
                    'revoke': verified and user.id != actor.id and user.status == 'ACTIVE' and _match(PREFIX + 'revoke', patterns)}})
        if body.phone:
            audit_log.record_critical_in_session(db, 'PHONE_BINDING_LOOKUP', 'phone-ledger',
                detail={'reason': body.reason, 'matchedCount': total}, tenant_id=actor.tenant_id)
            db.commit()
        return {'list': result, 'total': total, 'page': body.page, 'pageSize': body.pageSize}


def set_candidate(ctx, user_id: int, body):
    with get_sessionmaker()() as db:
        actor, scope, _ = authorize(db, ctx, 'candidate.manage')
        if user_id == actor.id:
            raise AppException('NO_PERMISSION', '本人号码请在账号安全中办理，不能走管理员入口', http_status=403)
        target = db.scalar(scoped_users(db, actor, ctx, scope).where(User.id == user_id).with_for_update())
        if target is None or target.status != 'ACTIVE':
            raise AppException('NO_PERMISSION', '账号不存在或不在可办理范围内', http_status=403)
        binding = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.tenant_id == actor.tenant_id,
            PhoneLoginBinding.user_id == target.id).with_for_update())
        if binding and binding.state == 'VERIFIED':
            raise AppException('DATA_CONFLICT', '已验证号码不能由管理员覆盖，请本人办理换号', http_status=409)
        if body.phone:
            create_pending_candidate_in_session(db, tenant_id=actor.tenant_id, user_id=target.id,
                phone=body.phone, source_kind='ADMIN', expected_version=body.expectedCandidateVersion)
        else:
            candidate = db.scalar(select(PhoneLoginCandidate).where(PhoneLoginCandidate.tenant_id == actor.tenant_id,
                PhoneLoginCandidate.user_id == target.id).with_for_update())
            if body.expectedCandidateVersion != (int(candidate.version) if candidate else 0):
                raise AppException('DATA_CONFLICT', '候选号码已变化，请重新读取', http_status=409)
            if candidate:
                candidate.state = 'CLEARED'
                candidate.candidate_phone_ciphertext = candidate.candidate_lookup = None
                candidate.version += 1
        audit_log.record_critical_in_session(db, 'PHONE_CANDIDATE_CHANGE', f'user:{target.id}',
            detail={'reason': body.reason, 'source': 'ADMIN', 'cleared': not bool(body.phone)}, tenant_id=actor.tenant_id, resource_id=str(target.id))
        db.commit()
        return {'accepted': True, 'state': 'PENDING' if body.phone else 'CLEARED', 'credentialChanged': False}


def revoke_binding(ctx, user_id, body):
    import json
    from datetime import timedelta
    from app.core.security import verify_password
    from app.services.control_plane_auth_service import rate_limit
    from app.services import password_reset_service as proofs
    from app.services.phone_binding_service import revoke_binding_in_session
    from app.services.message_event_outbox_service import emit_message_event
    from app.models import IdempotencyRecord
    with get_sessionmaker()() as db:
        actor, scope, _ = authorize(db, ctx, 'revoke')
        if actor.id == user_id:
            raise AppException('NO_PERMISSION', '本人号码请在账号安全中办理', http_status=403)
        if not rate_limit(f'phone-admin-reauth:{actor.tenant_id}:{actor.id}', 5, 300):
            raise AppException('RATE_LIMITED', '验证过于频繁，请稍后再试', http_status=429)
        if not verify_password(body.currentPassword, actor.password_hash):
            raise AppException('REAUTH_REQUIRED', '请核对经办人当前密码', http_status=401)
        target = db.scalar(scoped_users(db, actor, ctx, scope).where(User.id == user_id).with_for_update())
        if target is None or target.status != 'ACTIVE':
            raise AppException('NO_PERMISSION', '账号不在可办理范围', http_status=403)
        fingerprint = proofs._digest('phone-admin-revoke', json.dumps([user_id, body.expectedBindingVersion, body.reason]))
        key = proofs._digest('phone-admin-revoke-key', body.operationKey)
        receipt = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.tenant_id == actor.tenant_id,
            IdempotencyRecord.user_id == str(actor.id), IdempotencyRecord.operation == 'PHONE_ADMIN_REVOKE',
            IdempotencyRecord.key_hash == key).with_for_update())
        if receipt:
            if receipt.fingerprint != fingerprint:
                raise AppException('DATA_CONFLICT', '操作键已用于其他内容，请核对原结果', http_status=409)
            return dict(receipt.result_json)
        binding = db.scalar(select(PhoneLoginBinding).where(PhoneLoginBinding.tenant_id == actor.tenant_id,
            PhoneLoginBinding.user_id == target.id).with_for_update())
        if not binding or binding.is_deleted or binding.state != 'VERIFIED' or binding.version != body.expectedBindingVersion:
            raise AppException('DATA_CONFLICT', '号码状态已变化，请重新读取', http_status=409)
        revoke_binding_in_session(binding)
        binding.version += 1; target.credential_version += 1
        result = {'accepted': True, 'state': 'REVOKED', 'bindingVersion': int(binding.version),
            'credentialVersion': int(target.credential_version), 'accountLoginPreserved': True,
            'notificationQueued': True, 'affectedSessionsRequireRelogin': True,
            'cacheRecoveryRequired': True, 'refreshCleanupRequired': True}
        audit_log.record_critical_in_session(db, 'PHONE_BINDING_CHANGE', f'user:{target.id}',
            detail={'source': 'ADMIN_REVOKE', 'reason': body.reason, 'bindingVersion': int(binding.version)},
            tenant_id=actor.tenant_id, resource_id=str(target.id))
        emit_message_event(db, event_code='AUTH.PHONE_CHANGED', source_module='systemAdmin', source_biz_type='USER',
            source_biz_id=target.id, tenant_id=actor.tenant_id, recipient_refs=[{'userId': target.id}],
            dedup_key='admin-revoke:' + key,
            content='学校已撤销您的手机号登录凭据，原账号及密码仍可使用。请重新登录并在账号安全中核对，如有疑问请联系学校。')
        receipt = IdempotencyRecord(tenant_id=actor.tenant_id, user_id=str(actor.id), operation='PHONE_ADMIN_REVOKE',
            key_hash=key, fingerprint=fingerprint, state='SUCCEEDED', result_json=result,
            expires_at=proofs._utc_now() + timedelta(days=1))
        db.add(receipt)
        db.commit()
        # Epoch validation is authoritative; cache cleanup must not replay the mutation.
        cleanup = auth_service_db.credential_change_receipt(target, {'userId': f'db-{target.id}', 'tenantId': str(target.tenant_id)})
        result = {**result, 'cacheInvalidated': cleanup['cacheInvalidated'],
            'cacheRecoveryRequired': cleanup['cacheRecoveryRequired'], 'refreshCleanupRequired': cleanup['refreshCleanupRequired']}
        try:
            receipt.result_json = result
            db.commit()
        except Exception:
            db.rollback()  # Security change already durable; old receipt conservatively says cleanup pending.
        return result


def policy(ctx):
    from app.services.effective_config_service import resolve, PHONE_POLICY_KEYS
    with get_sessionmaker()() as db:
        actor, _, _ = authorize(db, ctx, 'policy.view')
        return {'accountLoginAlwaysAvailable': True, 'items': [resolve(key, tenant_id=actor.tenant_id) for key in sorted(PHONE_POLICY_KEYS)]}


def set_policy(ctx, body):
    from app.services.effective_config_service import set_override
    with get_sessionmaker()() as db:
        actor, scope, _ = authorize(db, ctx, 'policy.manage')
        if scope not in {'SCHOOL', 'TENANT', 'TENANT_ALL'}:
            raise AppException('NO_PERMISSION', '学校登录策略需要全校管理范围', http_status=403)
        # Keep the original actor lock through the policy command to reject a
        # concurrent credential revocation before this administrative write.
        return set_override(body.configKey, value=body.value, reason=body.reason,
            expected_version=body.expectedVersion, tenant_id=actor.tenant_id)


def _batch_rows(db, actor, ctx, scope, body, *, lock=False):
    stmt = _filtered(db, actor, ctx, scope, body.filters)
    if body.action == 'REMIND':
        stmt = stmt.where(User.id != actor.id, User.status == 'ACTIVE',
            PhoneLoginCandidate.state == 'PENDING', ~_candidate_conflict(),
            or_(PhoneLoginBinding.id.is_(None), PhoneLoginBinding.state != 'VERIFIED'))
    limit = 200 if body.action == 'REMIND' else 20000
    stmt = stmt.add_columns(PhoneLoginBinding, PhoneLoginCandidate, _candidate_conflict()).order_by(User.id).limit(limit + 1)
    rows = db.execute(stmt.with_for_update() if lock else stmt).all()
    if not rows or len(rows) > limit:
        raise AppException('VALIDATION_ERROR', f'可办理范围须为 1—{limit} 个账号，请调整筛选后重新预览')
    return rows


def _batch_digest(rows):
    from app.services.password_reset_service import _digest
    import json
    # Versions and credential epoch change even when the visible mask does not.
    return _digest('phone-batch-targets', json.dumps([[u.id, int(u.credential_version), u.status,
        int(b.version) if b else 0, int(c.version) if c else 0, bool(conflict)] for u, b, c, conflict in rows]))


def _batch_authorize(db, ctx, body):
    actor, scope, _ = authorize(db, ctx, 'view')
    authorize(db, ctx, 'remind' if body.action == 'REMIND' else 'export')
    if body.filters.phone:
        authorize(db, ctx, 'lookup')
    if len(body.reason.strip()) < 5:
        raise AppException('VALIDATION_ERROR', '请填写办理用途')
    return actor, scope


def export_scope_key(db, ctx):
    import json
    from app.services.phone_binding_service import _session
    from app.services.password_reset_service import _digest
    actor, scope, patterns = authorize(db, ctx, 'export')
    fresh = {key: ctx[key] for key in ('userId', 'tenantId', 'loginName', 'userType', 'currentRoleCode', 'activeContextId') if key in ctx}
    auth_service_db._inject_org_scope_claims(db, actor, fresh)
    return _digest('phone-export-scope', json.dumps([_session(ctx), scope, int(actor.credential_version),
        sorted(patterns), fresh], sort_keys=True, default=str))


def assert_export_scope(db, ctx, row):
    from app.services.data_exchange_job_service import _row_is_owned
    if not _row_is_owned(row, ctx) or row.adapter_ref != export_scope_key(db, ctx):
        raise AppException('NO_PERMISSION', '导出台账不属于当前办理会话或权限范围已变化，请重新导出', http_status=403)


def preview_batch(ctx, body):
    import secrets
    from app.core.field_crypto import encrypt_field
    from app.services import password_reset_service as proofs
    from app.services.phone_binding_service import _session
    with get_sessionmaker()() as db:
        actor, scope = _batch_authorize(db, ctx, body)
        rows = _batch_rows(db, actor, ctx, scope, body)
        token = secrets.token_urlsafe(36)
        proofs._set('phone-admin-preview', token, {'userId': actor.id, 'tenantId': actor.tenant_id,
            'session': _session(ctx), 'bodyEncrypted': encrypt_field(body.model_dump_json()),
            'targetsHash': _batch_digest(rows)}, 300, require_shared=True)
        return {'previewId': token, 'count': len(rows), 'action': body.action, 'expiresIn': 300,
            'channel': 'IN_APP' if body.action == 'REMIND' else 'MASKED_XLSX',
            'notice': '仅提醒待验证本人，不发送短信' if body.action == 'REMIND' else '仅导出当前权限和筛选范围，手机号保持脱敏'}


def confirm_batch(ctx, body):
    from datetime import timedelta
    from app.core.field_crypto import decrypt_field
    from app.services import password_reset_service as proofs
    from app.services.phone_binding_service import _session
    from app.models import IdempotencyRecord
    from app.modules.system_admin.routers.phone_governance_router import PhoneBatchPreview
    frozen = proofs._read('phone-admin-preview', body.previewId, require_shared=True)
    if not frozen or frozen['session'] != _session(ctx):
        raise AppException('CHALLENGE_INVALID', '预览已失效或学校岗位已切换，请重新预览')
    command = PhoneBatchPreview.model_validate_json(decrypt_field(frozen['bodyEncrypted'], allow_legacy_plaintext=False))
    with get_sessionmaker()() as db:
        actor, scope = _batch_authorize(db, ctx, command)
        if actor.id != frozen['userId'] or actor.tenant_id != frozen['tenantId']:
            raise AppException('NO_PERMISSION', '预览不属于当前办理人', http_status=403)
        key = proofs._digest('phone-admin-preview', body.previewId)
        receipt = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.tenant_id == actor.tenant_id,
            IdempotencyRecord.user_id == str(actor.id), IdempotencyRecord.operation == 'PHONE_ADMIN_BATCH',
            IdempotencyRecord.key_hash == key).with_for_update())
        if receipt:
            return dict(receipt.result_json)
        rows = _batch_rows(db, actor, ctx, scope, command, lock=True)
        if _batch_digest(rows) != frozen['targetsHash']:
            raise AppException('DATA_CONFLICT', '账号或候选范围已变化，请重新预览', http_status=409)
        if command.action == 'REMIND':
            from app.services.message_event_outbox_service import emit_message_event
            from app.services.control_plane_auth_service import rate_limit
            if not rate_limit(f'phone-remind:{actor.tenant_id}:{actor.id}', 3, 3600):
                raise AppException('RATE_LIMITED', '提醒过于频繁，请稍后再试', http_status=429)
            emit_message_event(db, event_code='AUTH.PHONE_VERIFY_REMINDER', source_module='systemAdmin',
                source_biz_type='USER', source_biz_id=actor.id, tenant_id=actor.tenant_id,
                recipient_refs=[{'userId': u.id} for u, _, _, _ in rows], dedup_key='phone-remind:' + key,
                content='学校已登记您的待核验号码。请使用原账号登录，在账号安全中核对并完成本人短信验证；如非本人号码请联系学校。不要向任何人提供密码或验证码。')
            result = {'accepted': True, 'count': len(rows), 'channel': 'IN_APP', 'notificationQueued': True}
            action = 'PHONE_VERIFY_REMINDER'
        else:
            from io import BytesIO
            from openpyxl import Workbook
            from app.services.xlsx_util import safe_excel_value
            from app.services.data_exchange_job_service import _write_generated_file, _create_export_job
            book = Workbook(write_only=True); sheet = book.create_sheet('手机号脱敏台账')
            sheet.append(['原账号', '姓名', '账号类型', '登录凭据状态', '登录手机号（脱敏）', '候选状态', '候选手机号（脱敏）', '凭据版本', '候选版本'])
            for user, binding, candidate, conflict in rows:
                sheet.append([safe_excel_value(v) for v in [user.login_name, user.real_name, user.user_type,
                    binding.state if binding else 'UNBOUND', _masked(binding.phone_ciphertext) if binding and binding.state == 'VERIFIED' else '',
                    'CONFLICT' if conflict else candidate.state if candidate else 'NONE',
                    _masked(candidate.candidate_phone_ciphertext) if candidate else '',
                    int(binding.version) if binding else 0, int(candidate.version) if candidate else 0]])
            stream = BytesIO(); book.save(stream); book.close()
            file_id = _write_generated_file(stream.getvalue(), '手机号脱敏台账.xlsx', biz_id=key, user=ctx, session=db)
            job = _create_export_job(export_type='PHONE_MASKED_LEDGER', purpose=command.reason,
                file_object_id=file_id, row_count=len(rows), user=ctx, session=db,
                adapter_type='PHONE_MASKED_LEDGER', adapter_ref=export_scope_key(db, ctx))
            result = {'accepted': True, 'count': len(rows), 'channel': 'MASKED_XLSX', 'job': job}
            action = 'PHONE_LEDGER_EXPORT'
        audit_log.record_critical_in_session(db, action, 'phone-ledger', detail={
            'reason': command.reason, 'count': len(rows), 'previewHash': key}, tenant_id=actor.tenant_id)
        db.add(IdempotencyRecord(tenant_id=actor.tenant_id, user_id=str(actor.id), operation='PHONE_ADMIN_BATCH',
            key_hash=key, fingerprint=frozen['targetsHash'], state='SUCCEEDED', result_json=result,
            expires_at=proofs._utc_now() + timedelta(days=1)))
        db.commit()
        return result
