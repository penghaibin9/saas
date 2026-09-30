"""Run bounded leased jobs with fresh school, identity, permission and source checks."""
from app.core.context import set_current_user, set_tenant, get_current_user_ctx, get_tenant, get_trace_id, set_trace_id
from app.core.permissions import enforce_permission, require_module
from app.services.db_service import session, _tid
from app.services import auth_service_db as auth
from app.modules.academic_affairs.optimizer.persistence import run_one
from .schedule_optimizer_source_service import capture_source
from .schedule_optimizer_jobs_service import _repository, _enabled


def current_actor(reference):
    from app.core.exceptions import AppException
    if str(reference.get('tenantId')) != str(_tid()):
        raise AppException('NO_PERMISSION', '候选任务不属于当前学校', http_status=403)
    with session() as db:
        user = auth._load_token_user(db, reference)
        auth._ensure_tenant_login_allowed(db, user)
        role = auth._pick_context(auth._role_contexts(db, user),
                                 context_id=reference.get('activeContextId'),
                                 role_code=reference.get('roleCode'))
        if not role or role['roleCode'] != reference.get('roleCode'):
            raise AppException('NO_PERMISSION', '候选创建人的岗位已失效', http_status=403)
        actor = {'userId': f'db-{user.id}', 'tenantId': str(user.tenant_id),
                 'loginName': user.login_name, 'realName': user.real_name, 'userType': user.user_type,
                 'currentRoleCode': role['roleCode'], 'activeContextId': role['contextId'],
                 'dataScope': role['dataScope']}
    enforce_permission(actor, 'academicAffairs.schedule.rule.manage')
    require_module('academicAffairs')(actor)
    return actor


def run_pending(tenant_id):
    if not _enabled():
        return None
    previous_tenant, previous_user = get_tenant(), get_current_user_ctx()
    previous_trace=get_trace_id()
    set_trace_id('-')  # Background rechecks must not reuse the HTTP module-access snapshot.
    set_tenant(str(tenant_id))
    try:
        active = {}
        def allowed():
            from app.services.tenant_effective_state_service import background_execution_policy
            return background_execution_policy(int(tenant_id)).get('writable') is True
        def actor_allowed(claim):
            actor = current_actor(claim['actorContext'])
            from .schedule_optimizer_jobs_service import _authorize
            _authorize(actor, claim['batchId'])
            active['actor'] = actor
            set_current_user(actor)
            return True
        def source_current(snapshot):
            with session() as db:
                _, revision = capture_source(db, active['actor'], snapshot.batch)
                return revision == snapshot.revision
        # At most two pending jobs per batch. A persistent CLI can repeatedly drain leases.
        return run_one(_repository({'userId': 'schedule-worker', 'currentRoleCode': ''}),
                       str(tenant_id), execution_allowed=allowed,
                       actor_allowed=actor_allowed, source_validator=source_current)
    finally:
        set_current_user(previous_user)
        set_tenant(previous_tenant)
        set_trace_id(previous_trace)
