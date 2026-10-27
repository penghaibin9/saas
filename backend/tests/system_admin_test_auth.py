"""Normal login for selected system-management integration tests; no mock-login switch."""
import secrets
from uuid import uuid4


def school_admin_headers(client):
    from sqlalchemy import select
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User, Role, UserRole
    tenant_id=1000000000000000001
    login='system_audit_'+uuid4().hex[:12]
    password=secrets.token_urlsafe(24)
    with get_sessionmaker()() as db:
        role=db.scalar(select(Role).where(Role.tenant_id==tenant_id,Role.role_code=='SCHOOL_ADMIN'))
        if role is None:
            role=Role(tenant_id=tenant_id,role_code='SCHOOL_ADMIN',role_name='学校管理员',role_type='SYSTEM',status='ACTIVE');db.add(role)
        actor=User(tenant_id=tenant_id,login_name=login,real_name='系统集成验收管理员',password_hash=hash_password(password),user_type='ADMIN',status='ACTIVE')
        db.add(actor);db.flush();db.add(UserRole(tenant_id=tenant_id,user_id=actor.id,role_id=role.id,status='ACTIVE'));db.commit()
    response=client.post('/api/v1/auth/login',json={'tenantCode':'demo','loginName':login,'password':password})
    assert response.status_code==200
    return {'Authorization':'Bearer '+response.json()['data']['accessToken']}
