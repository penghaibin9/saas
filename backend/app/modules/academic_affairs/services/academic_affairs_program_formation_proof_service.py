"""历史方案课程形成方式补证：只追加证据，不覆盖原来源或教学执行。"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.core.timeutil import utc_now_naive
from app.services.db_service import _tid, session
from .academic_affairs_task_formation_policy import FORMATION_LABELS, class_type_for_formation, normalize_formation_mode

_HEX = re.compile(r'^[0-9a-fA-F]{64}$')
_MAX_TASKS = 1000


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


def source_fingerprint(source, program):
    """权威原字段指纹；保留空值与原形成方式，不从教学班推断。"""
    return _hash({'sourceId': str(source.id), 'programId': str(source.program_id),
        'courseId': str(source.course_id) if source.course_id is not None else None,
        'openTermNo': source.open_term_no,
        'credit': format(Decimal(str(source.credit_snapshot)), '.1f') if source.credit_snapshot is not None else None,
        'originalFormationMode': source.formation_mode, 'programVersion': program.version})


def _conflict(message):
    return AppException('DATA_CONFLICT', message, http_status=409)


def _block(code, message):
    return {'code': code, 'message': message}


def _raise_blockers(blockers):
    raise AppException('DATA_CONFLICT', '；'.join(item['message'] for item in blockers),
        http_status=409, details={'confirmationBlockers': blockers})


def _actor(db, user):
    from .academic_affairs_grade_correction_command import _current_user_id
    current = dict(user)
    if current.get('userId') in (None, '') and current.get('id') not in (None, ''):
        current['userId'] = current['id']
    # 复用现行稳定账号解析；所有数值或登录键均回链同租户有效User，不能以角色名代替。
    return _current_user_id(db, current)


def _file_user(db, user, *, actor_id=None):
    """统一文件裁决消费已验证数值账号；保留原权限、范围及角色上下文。"""
    actor = _actor(db, user) if actor_id is None else actor_id
    return {**user, 'id': str(actor), 'userId': str(actor)}


def _responsible(db, user):
    from .academic_affairs_program_governance_service import _scope
    from .academic_affairs_responsibility_service import resolve_school
    enforce_permission(user, 'academicAffairs.program.review')
    scope = _scope(user, db)
    if scope.scope_type != 'TENANT_ALL':
        raise AppException('PERMISSION_DENIED', '只有校级教务责任人员可以确认历史形成方式依据', http_status=403)
    actor = _actor(db, user)
    responsibility = resolve_school(db, permission_code='academicAffairs.program.review')
    if str(actor) not in responsibility['assigneeUserIds']:
        raise AppException('PERMISSION_DENIED', '当前账号不是有效的校级教务审核责任人员', http_status=403)
    return actor


def _source(db, source_id, user, *, lock=False):
    from app.models import AaProgram, AaProgramCourse
    from .academic_affairs_program_governance_service import _ensure_program_scope
    source = db.scalar(select(AaProgramCourse).where(AaProgramCourse.tenant_id == _tid(),
        AaProgramCourse.id == int(source_id), AaProgramCourse.is_deleted.is_(False)))
    if not source:
        raise not_found('方案课程来源不存在')
    _ensure_program_scope(db, user, source.program_id)
    program_query = select(AaProgram).where(AaProgram.tenant_id == _tid(),
        AaProgram.id == source.program_id, AaProgram.is_deleted.is_(False))
    if lock:
        program_query = program_query.with_for_update().execution_options(populate_existing=True)
    program = db.scalar(program_query)
    if not program:
        raise not_found('来源方案不存在')
    if lock:
        source = db.scalar(select(AaProgramCourse).where(AaProgramCourse.tenant_id == _tid(),
            AaProgramCourse.id == int(source_id), AaProgramCourse.is_deleted.is_(False))
            .with_for_update().execution_options(populate_existing=True))
        if not source or source.program_id != program.id:
            raise _conflict('方案课程来源已变化，请重新核对')
        _ensure_program_scope(db, user, program.id)
    return source, program


def _base_blockers(db, source, program):
    from app.models import AaCourse
    blockers = []
    if program.status not in ('PUBLISHED', 'ENABLED'):
        blockers.append(_block('PROGRAM_STATE', '只有已发布或已启用方案的历史课程来源可以补证'))
    if source.formation_mode is not None:
        blockers.append(_block('ORIGINAL_MODE_PRESENT', '原来源已有形成方式，不能通过历史补证覆盖'))
    course = db.scalar(select(AaCourse.id).where(AaCourse.tenant_id == _tid(),
        AaCourse.id == source.course_id, AaCourse.is_deleted.is_(False)))
    if course is None or source.open_term_no is None or source.open_term_no <= 0 or source.credit_snapshot is None or source.credit_snapshot < 0:
        blockers.append(_block('SOURCE_INCOMPLETE', '课程、开课序号或学分来源不完整'))
    return blockers


def _impact(db, source, mode=None, *, lock=False, locked_term_ids=None):
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm, AaTeachingClass
    # 锁序：学期→方案→来源→批次→任务；初读只用于有界定位批次。
    statement = select(AaTeachingTask).where(AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.source_program_course_id == source.id).order_by(AaTeachingTask.id).limit(_MAX_TASKS + 1)
    tasks = db.scalars(statement).all()
    if len(tasks) > _MAX_TASKS:
        raise _conflict('该来源关联任务超过单次核对上限，请由实施人员分批核查')
    if not tasks:
        return []
    batch_ids = sorted({task.batch_id for task in tasks})
    batch_query = select(AaTeachingTaskBatch).where(AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.id.in_(batch_ids)).order_by(AaTeachingTaskBatch.id)
    if lock:
        batch_query = batch_query.with_for_update().execution_options(populate_existing=True)
    batches = db.scalars(batch_query).all()
    if len(batches) != len(batch_ids):
        raise _conflict('关联任务无法回链同学校教学任务批次')
    term_ids = sorted({batch.term_id for batch in batches})
    if lock and not set(term_ids).issubset(set(locked_term_ids or ())):
        raise _conflict('关联学期集合已变化，请重新读取后确认')
    if lock:
        tasks = db.scalars(statement.with_for_update().execution_options(populate_existing=True)).all()
        if len(tasks) > _MAX_TASKS or {task.batch_id for task in tasks} != set(batch_ids):
            raise _conflict('关联任务批次集合已变化，请重新读取后确认')
    term_query = select(AaTerm).where(AaTerm.tenant_id == _tid(), AaTerm.id.in_(term_ids)).order_by(AaTerm.id)
    if lock:
        term_query = term_query.with_for_update().execution_options(populate_existing=True)
    terms = db.scalars(term_query).all()
    if len(terms) != len(term_ids):
        raise _conflict('关联任务学期来源不完整')
    blockers = []
    if any(term.status == 'ARCHIVED' for term in terms):
        blockers.append(_block('TERM_ARCHIVED', '关联教学任务已有归档学期，不能补写执行语义依据'))
    if mode:
        if any(task.formation_mode is not None and task.formation_mode != mode for task in tasks):
            blockers.append(_block('TASK_MODE_CONFLICT', '关联任务已有形成方式快照与本次证据矛盾'))
        class_query = select(AaTeachingClass).where(AaTeachingClass.tenant_id == _tid(),
            AaTeachingClass.teaching_task_id.in_([task.id for task in tasks])).order_by(AaTeachingClass.id).limit(_MAX_TASKS + 1)
        if lock:
            class_query = class_query.with_for_update().execution_options(populate_existing=True)
        classes = db.scalars(class_query).all()
        if len(classes) > _MAX_TASKS:
            raise _conflict('关联教学班超过核对上限')
        if any(clazz.class_type != class_type_for_formation(mode) for clazz in classes):
            blockers.append(_block('CLASS_TYPE_CONFLICT', '已有正式教学班形成类型与本次证据矛盾，不能自动转换教学班'))
    return blockers


def _file(db, file_id, user, *, lock=False, with_view=False):
    from app.models.file import FileObject, FileBinding
    from app.services.file_access_service import authorize_file_object, file_view
    query = select(FileObject).where(FileObject.tenant_id == _tid(),
        FileObject.id == int(file_id), FileObject.is_deleted.is_(False))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    file = db.scalar(query)
    if not file:
        raise not_found('证据文件不存在或无权访问')
    bindings = db.scalars(select(FileBinding).where(FileBinding.tenant_id == _tid(),
        FileBinding.file_id == file.id, FileBinding.is_deleted.is_(False)).limit(1001)).all()
    if len(bindings) > 1000:
        raise _conflict('证据文件关联超过单次授权核对上限')
    file_user = _file_user(db, user)
    if not authorize_file_object(file, bindings, file_user, 'bind', db=db):
        raise not_found('证据文件不存在或无权访问')
    view = file_view(file, user=file_user, bindings=bindings, db=db)
    if not view['readyForBusiness']:
        raise _conflict('证据文件尚未通过文件中心就绪检查')
    if not _HEX.fullmatch(file.sha256 or ''):
        raise _conflict('证据文件缺少有效的内容校验值')
    return (file, view) if with_view else file


def _proof(db, source_id, *, lock=False):
    from app.models import AaProgramCourseFormationProof
    statement = select(AaProgramCourseFormationProof).where(
        AaProgramCourseFormationProof.tenant_id == _tid(), AaProgramCourseFormationProof.program_course_id == source_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return db.scalar(statement)


def _proof_view(db, proof, user):
    if proof is None:
        return None
    evidence = None
    try:
        file, view = _file(db, proof.evidence_file_id, user, with_view=True)
        if file.sha256.lower() == proof.evidence_sha256.lower():
            # attachment_view另开会话且只认全局原身份；在本事务投影同样字段，
            # 能力全部来自现有file_view，不自行授予预览或下载。
            actions = list(view.get('allowedActions') or [])
            evidence = {key: view.get(key) for key in ('fileId', 'fileName', 'ext', 'mimeType', 'sizeBytes')}
            evidence.update(allowedActions=actions, canPreview='preview' in actions, canDownload='download' in actions)
    except AppException:
        pass
    return {'proofId': str(proof.id), 'formationModeLabel': FORMATION_LABELS[proof.formation_mode],
        'evidence': evidence, 'evidenceLocator': proof.evidence_locator, 'reason': proof.reason,
        'confirmedAt': proof.confirmed_at.isoformat(timespec='seconds') + 'Z'}


def _response(db, source, program, proof, user):
    from app.models.file import FileObject
    from .academic_affairs_task_formation_provenance_service import resolve_program_course_formation_snapshot
    blockers = _base_blockers(db, source, program) + _impact(db, source)
    try:
        _responsible(db, user)
    except AppException:
        blockers.append(_block('RESPONSIBILITY_REQUIRED', '当前账号不是有确认权限的校级教务责任人员'))
    if proof is not None:
        blockers.append(_block('ALREADY_CONFIRMED', '该来源已有不可覆盖的确认记录'))
    file = db.scalar(select(FileObject).where(FileObject.tenant_id == _tid(),
        FileObject.id == proof.evidence_file_id, FileObject.is_deleted.is_(False))) if proof else None
    snapshot = resolve_program_course_formation_snapshot(db, source, tenant_id=_tid(),
        proof_bundle=(proof, program, file) if proof else None)
    proof_valid = bool(proof is not None and snapshot['status'] == 'PROVEN'
        and snapshot.get('proofId') == str(proof.id))
    if proof is not None and not proof_valid:
        messages = {
            'FORMATION_PROOF_SOURCE_CHANGED': '原方案课程字段或版本已变化，既有确认已失效，须核对来源依据',
            'FORMATION_PROOF_PAYLOAD_CHANGED': '既有确认记录的内容校验不一致，须核对历史确认记录',
            'FORMATION_PROOF_EVIDENCE_UNAVAILABLE': '原证据文件内容、扫描或可用状态已变化，既有确认已失效',
        }
        for code in snapshot.get('blockers') or ['FORMATION_PROOF_INVALID']:
            blockers.append(_block(code, messages.get(code, '既有确认已失效，须核对原始来源及证据')))
    mode_label = FORMATION_LABELS.get(snapshot['formationMode'], '来源未证明')
    if proof is not None and not proof_valid:
        mode_label = '既有确认已失效，需核对来源依据'
    return {'programCourseId': str(source.id), 'programId': str(program.id),
        'programName': program.program_name, 'programVersion': program.version,
        'courseName': source.course_name, 'originalFormationModeLabel': FORMATION_LABELS.get(source.formation_mode, '来源未证明'),
        'formationModeLabel': mode_label, 'proofValid': proof_valid,
        'proofValidityLabel': ('有效正式依据' if proof_valid else '既有确认已失效') if proof else '尚无正式确认',
        'sourceFingerprint': source_fingerprint(source, program), 'proof': _proof_view(db, proof, user),
        'canConfirm': not blockers, 'confirmationBlockers': blockers}


def get_formation_proof(program_course_id, user):
    enforce_permission(user, 'academicAffairs.program.view')
    with session() as db:
        source, program = _source(db, program_course_id, user)
        return _response(db, source, program, _proof(db, source.id), user)


def _write_audit(db, proof, user):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type='AA_PROGRAM_FORMATION_PROOF',
        biz_id=proof.id, action='CONFIRM_FORMATION_PROOF', operator=str(proof.confirmed_by),
        role_name=str(user.get('currentRoleCode') or ''),
        detail=f'来源={proof.program_course_id};证据校验={proof.evidence_sha256};定位={proof.evidence_locator}',
        occurred_at=proof.confirmed_at))
    db.flush()


def _lock_terms(db, source):
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm
    tasks = db.execute(select(AaTeachingTask.id, AaTeachingTaskBatch.term_id).join(AaTeachingTaskBatch,
        (AaTeachingTaskBatch.id == AaTeachingTask.batch_id) & (AaTeachingTaskBatch.tenant_id == AaTeachingTask.tenant_id))
        .where(AaTeachingTask.tenant_id == _tid(), AaTeachingTask.source_program_course_id == source.id)
        .order_by(AaTeachingTask.id).limit(_MAX_TASKS + 1)).all()
    if len(tasks) > _MAX_TASKS:
        raise _conflict('该来源关联任务超过单次核对上限')
    term_ids = sorted({row.term_id for row in tasks})
    if term_ids:
        terms = db.scalars(select(AaTerm).where(AaTerm.tenant_id == _tid(), AaTerm.id.in_(term_ids))
            .order_by(AaTerm.id).with_for_update().execution_options(populate_existing=True)).all()
        if len(terms) != len(term_ids):
            raise _conflict('关联任务学期来源不完整')
    return term_ids


def confirm_formation_proof(program_course_id, body, user):
    from app.models import AaProgramCourseFormationProof
    from app.services.file_access_service import upsert_file_binding
    try:
        with session() as db:
            # 仅本次命令使用已提交读，避免等待生成锁后仍用旧空快照定位关联。
            # 必须在责任/来源任何SQL之前设置；连接归还时SQLAlchemy恢复池隔离配置。
            db.connection(execution_options={'isolation_level': 'READ COMMITTED'})
            actor = _responsible(db, user)
            if not 2 <= len(body.evidenceLocator.strip()) <= 300 or not 5 <= len(body.reason.strip()) <= 500:
                raise AppException('VALIDATION_ERROR', '证据定位至少2字、确认原因至少5字，不能仅填写空白')
            preliminary_source, _ = _source(db, program_course_id, user)
            locked_term_ids = _lock_terms(db, preliminary_source)
            source, program = _source(db, program_course_id, user, lock=True)
            mode = normalize_formation_mode(body.formationMode, required=True)
            fingerprint = source_fingerprint(source, program)
            if fingerprint != body.expectedSourceFingerprint.lower():
                raise _conflict('原方案课程字段已变化，请重新读取核对后提交')
            blockers = _base_blockers(db, source, program)
            if blockers:
                _raise_blockers(blockers)
            payload = {'source': str(source.id), 'mode': mode, 'file': str(int(body.evidenceFileId)),
                'locator': body.evidenceLocator.strip(), 'reason': body.reason.strip(), 'fingerprint': fingerprint}
            payload_hash = _hash(payload)
            existing = _proof(db, source.id, lock=True)
            keyed = db.scalar(select(AaProgramCourseFormationProof).where(
                AaProgramCourseFormationProof.tenant_id == _tid(),
                AaProgramCourseFormationProof.idempotency_key == body.idempotencyKey)
                .with_for_update().execution_options(populate_existing=True))
            if keyed and (keyed.program_course_id != source.id or keyed.payload_hash != payload_hash):
                raise _conflict('本次防重标识已用于另一份确认，不可覆盖')
            if existing:
                if existing.payload_hash != payload_hash:
                    raise _conflict('该来源已确认另一份证据，不可覆盖历史确认')
                return _response(db, source, program, existing, user)
            blockers = _impact(db, source, mode, lock=True, locked_term_ids=locked_term_ids)
            if blockers:
                _raise_blockers(blockers)
            file = _file(db, body.evidenceFileId, user, lock=True)
            proof = AaProgramCourseFormationProof(tenant_id=_tid(), program_course_id=source.id,
                program_id=program.id, course_id=source.course_id, open_term_no=source.open_term_no,
                credit_snapshot=source.credit_snapshot, original_formation_mode=source.formation_mode,
                formation_mode=mode, source_fingerprint=fingerprint, evidence_file_id=file.id,
                evidence_sha256=file.sha256.lower(), evidence_locator=payload['locator'], reason=payload['reason'],
                confirmed_by=actor, confirmed_at=utc_now_naive(), idempotency_key=body.idempotencyKey,
                payload_hash=payload_hash)
            db.add(proof); db.flush()
            upsert_file_binding(str(file.id), biz_type='AA_PROGRAM_FORMATION_PROOF', biz_id=str(proof.id),
                subject_type='USER', subject_id=str(actor), user=_file_user(db, user, actor_id=actor), db=db)
            _write_audit(db, proof, user)
            result = _response(db, source, program, proof, user)
            db.commit()
            return result
    except IntegrityError as exc:
        raise _conflict('来源确认发生并发冲突，请重新读取既有确认结果') from exc
    except OperationalError as exc:
        code = getattr(exc.orig, 'args', (None,))[0]
        if code in (1205, 1213):
            raise _conflict('来源确认遇到并发锁冲突，请重新读取后重试') from exc
        raise
