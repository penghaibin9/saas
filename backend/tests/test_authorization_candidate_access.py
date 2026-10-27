"""正常受限身份的授权选人权限、租户隔离和最小字段回归。"""
from uuid import uuid4
import secrets
from sqlalchemy import select


def test_assignment_operators_can_select_without_account_view(client, db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User, Role, UserRole, Permission, RolePermission
    tid=1000000000000000001
    password=secrets.token_urlsafe(24)
    stamp=uuid4().hex[:10]
    actors=[]
    with get_sessionmaker()() as db:
        for i,code in enumerate(['systemAdmin.user.assign','systemAdmin.role.config','systemAdmin.delegation.manage','systemAdmin.role.view']):
            role=Role(tenant_id=tid,role_code=f'CANDIDATE_{stamp}_{i}',role_name='授权选人测试岗位',role_type='CUSTOM',status='ACTIVE')
            actor=User(tenant_id=tid,login_name=f'candidate_actor_{stamp}_{i}',real_name='授权经办人',user_type='TEACHER',status='ACTIVE',password_hash=hash_password(password))
            db.add_all([role,actor]);db.flush()
            permission=db.scalar(select(Permission).where(Permission.permission_code==code));assert permission
            db.add(RolePermission(tenant_id=tid,role_id=role.id,permission_id=permission.id,status='ACTIVE'))
            db.add(UserRole(tenant_id=tid,user_id=actor.id,role_id=role.id,status='ACTIVE'))
            actors.append(actor.login_name)
        keyword=f'candidate_target_{stamp}'
        target=User(tenant_id=tid,login_name=keyword,real_name='可选择的老师',user_type='TEACHER',status='ACTIVE',password_hash='unused-fixture')
        db.add(target);db.flush();target_id=str(target.id)
        for suffix,tenant,status,kind in [('other',tid+1,'ACTIVE','TEACHER'),('disabled',tid,'DISABLED','TEACHER'),('platform',tid,'ACTIVE','PLATFORM_ADMIN')]:
            db.add(User(tenant_id=tenant,login_name=keyword+'_'+suffix,real_name='不应显示',user_type=kind,status=status,password_hash='unused-fixture'))
        db.commit()
    for i,login in enumerate(actors):
        response=client.post('/api/v1/auth/login',json={'tenantCode':'demo','loginName':login,'password':password})
        assert response.status_code==200,response.text
        headers={'Authorization':'Bearer '+response.json()['data']['accessToken']}
        response=client.get('/api/v1/system/authorization-candidates',params={'keyword':keyword,'page_size':1000},headers=headers)
        if i==3:
            assert response.status_code==403
            continue
        assert response.status_code==200,response.text
        data=response.json()['data']
        assert data['pageSize']==20 and data['total']==1
        assert data['list']==[{'id':target_id,'name':'可选择的老师','userNo':keyword,'loginName':keyword}]
        assert client.get('/api/v1/system/users',headers=headers).status_code==403


def test_reconciliation_filter_targets_one_user_before_paging(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User, Role, UserRole
    from app.services.role_assignment_service import list_assignments
    tid=1000000000000000001
    with get_sessionmaker()() as db:
        role=Role(tenant_id=tid,role_code='RECOVERY_TARGET_ONLY',role_name='核对专用角色',role_type='CUSTOM',status='ACTIVE')
        db.add(role);db.flush()
        ids=[]
        for n in range(3):
            user=User(tenant_id=tid,login_name=f'recovery_candidate_{n}',real_name='核对人员',user_type='TEACHER',status='ACTIVE',password_hash='unused-fixture')
            db.add(user);db.flush();ids.append(user.id)
            db.add(UserRole(tenant_id=tid,user_id=user.id,role_id=role.id,status='ACTIVE'))
        db.commit()
    result=list_assignments(tenant_id=tid,role_code='RECOVERY_TARGET_ONLY',user_id=ids[-1],page_size=1)
    assert result['total']==1 and len(result['list'])==1
    assert result['list'][0]['userId']==str(ids[-1])
