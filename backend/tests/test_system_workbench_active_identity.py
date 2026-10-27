"""同一真实数据库账号的不同角色上下文，待办计数和列表必须同口径。"""
from datetime import datetime,timedelta
from sqlalchemy import select
from app.core.context import set_tenant


def test_current_role_gates_four_domain_todos_before_count_and_pagination(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Role,Permission,RolePermission,User,UserRole,UnifiedTodo
    from app.services import workbench_todo_service as svc
    from app.services import teacher_mobile_todo_keyset_service as mobile
    tid=1000000000000000001
    groups=[('internship','INTERN_LEAVE_APPROVAL'),('academic-affairs','AA_GRADE_ENTRY'),('graduation','GD_PROPOSAL_REVIEW'),('student-affairs','LEAVE_APPROVAL')]
    with get_sessionmaker()() as db:
        actor=User(tenant_id=tid,login_name='d611_context_actor',real_name='独立身份验证账号',user_type='TEACHER',status='ACTIVE',password_hash='not-used-by-this-service-test')
        db.add(actor);db.flush();uid=actor.id
        roles=[]
        for code,permissions in [('D611_CONFIG',[]),('D611_BUSINESS',sorted({p for _,kind in groups for p in svc._TODO_ACTION_PERMISSIONS[kind]}))]:
            role=Role(tenant_id=tid,role_code=code,role_name='独立验证职责',role_type='CUSTOM',status='ACTIVE');db.add(role);db.flush();roles.append((role.id,code))
            db.add(UserRole(tenant_id=tid,user_id=uid,role_id=role.id,status='ACTIVE'))
            for permission in permissions:
                p=db.scalar(select(Permission).where(Permission.permission_code==permission));assert p,permission
                db.add(RolePermission(tenant_id=tid,role_id=role.id,permission_id=p.id,status='ACTIVE'))
        for n,(module,kind) in enumerate(groups,1):
            db.add(UnifiedTodo(tenant_id=tid,source_module=module,source_biz_type='D611_TEST',source_biz_id=610+n,todo_type=kind,assignee_id=uid,title='独立身份待办',status='PENDING',created_at=datetime.utcnow()-timedelta(minutes=1)))
        db.commit()
    set_tenant({'tenantId':str(tid)})
    try:
        contexts=[{'userId':f'db-{uid}','loginName':'d611_context_actor','userType':'TEACHER','currentRoleCode':code,'activeContextId':f'role:{rid}','tenantId':str(tid)} for rid,code in roles]
        for actor,expected in [(contexts[0],0),(contexts[1],3),(contexts[0],0)]:
            rows,total=svc.list_todos(actor,status='PENDING',page_size=20)
            assert total==len(rows)==expected
            assert svc.count_todos(actor)['total']==expected
            assert svc.summary(actor)['pending']==expected
            small=mobile.list_continuous(actor,status='PENDING',page_size=20)
            assert small['total']==len(small['items'])==expected
        # 本页具有查看权限也不等于具备办理权限。
        rid=roles[1][0]
        with get_sessionmaker()() as db:
            permission=db.scalar(select(Permission).where(Permission.permission_code=='internship.leave.review'))
            grant=db.scalar(select(RolePermission).where(RolePermission.tenant_id==tid,RolePermission.role_id==rid,RolePermission.permission_id==permission.id))
            grant.status='INACTIVE';db.commit()
        rows,total=svc.list_todos(dict(contexts[1]),status='PENDING')
        assert total==2 and all(r['todoType']!='INTERN_LEAVE_APPROVAL' for r in rows)
    finally:
        set_tenant(None)


def test_internship_leave_link_uses_existing_detail_query():
    from app.services.todo_route_registry import resolve_todo_route
    route=resolve_todo_route('INTERN_LEAVE_APPROVAL','9007199254740993',client='pc')
    assert route['path']=='/admin/internship/leaves'
    assert route['query']['id']=='9007199254740993'

def test_known_pc_todo_routes_have_current_identity_capability_checks():
    from app.services.todo_route_registry import route_contract_snapshot
    from app.services.workbench_todo_service import _TODO_ACTION_PERMISSIONS,_TODO_ANY_ACTION_PERMISSIONS
    from app.core.permission_catalog import load_permission_catalog
    routes=route_contract_snapshot()
    kinds=set(routes['pcExact'])|set(routes['pcList'])|set(routes['teacherMini'])
    assert kinds <= set(_TODO_ACTION_PERMISSIONS)|{'MATERIAL_REVIEW'}
    codes={code for requirements in [*_TODO_ACTION_PERMISSIONS.values(),*_TODO_ANY_ACTION_PERMISSIONS.values()] for code in requirements}
    catalog={entry['permissionCode'] for entry in load_permission_catalog()['entries']}
    assert codes <= catalog
