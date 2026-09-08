import pytest
from types import SimpleNamespace

from app.api.v1 import mobile
from app.services import _mobile_teacher_service_impl as teacher
from app.services import affairs_risk_service as risk

@pytest.mark.parametrize('action,field,handler',[('process','content','teacher_affairs_risk_process'),('close','conclusion','teacher_affairs_risk_close')])
@pytest.mark.parametrize('version',[None,0,7])
def test_mobile_risk_routes_forward_exact_version_to_authority(monkeypatch,action,field,handler,version):
    seen=[]
    user={'userType':'TEACHER','realName':'联调教师'}
    monkeypatch.setattr(teacher,'_require_teacher',lambda value:value)
    monkeypatch.setattr(teacher,'db_enabled',lambda:True)
    monkeypatch.setattr(teacher,'_audit_write',lambda *args:None)
    def authority(rid,actor,**kwargs):
        seen.append((rid,actor,kwargs))
        return {'riskId':rid,'version':8}
    monkeypatch.setattr(risk,action,authority)
    monkeypatch.setattr(mobile.tea,'affairs_risk_'+action,getattr(teacher,'affairs_risk_'+action))
    getattr(mobile,handler)('9007199254740993',body={field:'处置说明已核验','version':version},user=user)
    assert seen==[('9007199254740993',user,{field:'处置说明已核验','expected_version':version})]


def test_risk_todo_points_to_teacher_original_workspace():
    from app.services.todo_route_registry import resolve_todo_route
    route = resolve_todo_route('RISK_HANDLE', '9007199254740993', client='teacherMini')
    assert route['query'] == {'recordId':'9007199254740993'}
    assert route['path'] == '/pages/teacher/risk-students/index'
    assert route['exact'] is True


def test_dorm_manager_actions_are_limited_to_owned_dorm_risk(monkeypatch):
    from app.core import affairs_security

    monkeypatch.setattr(
        affairs_security,
        'build_affairs_context',
        lambda _user, _db: SimpleNamespace(scope_type='DORM_BUILDING'),
    )
    monkeypatch.setattr(
        risk,
        'has_permission',
        lambda _user, code: code == 'studentAffairs.dorm.inspection.manage',
    )
    evaluate = risk._risk_action_evaluator({
        'userId': 'db-44',
        'currentRoleCode': 'DORM_MANAGER',
    })

    owned = SimpleNamespace(owner_id=44, source='DORM', status='PROCESSING')
    other_owner = SimpleNamespace(owner_id=45, source='DORM', status='PROCESSING')
    other_domain = SimpleNamespace(owner_id=44, source='MENTAL', status='PROCESSING')

    assert evaluate(owned) == ['PROCESS', 'CLOSE']
    assert evaluate(other_owner) == []
    assert evaluate(other_domain) == []


def test_exact_risk_owner_bypasses_class_scope_only_for_that_record(monkeypatch):
    from app.services import affairs_dashboard_service

    monkeypatch.setattr(
        affairs_dashboard_service,
        '_allowed_class_ids',
        lambda _db, _user: (set(), 'DORM_BUILDING'),
    )
    record = SimpleNamespace(owner_id=44)

    risk._scope_or_403(object(), 9001, {'userId': '44'}, record)
