from datetime import datetime, timedelta

from app.services import organization_version_service as svc


def test_assignment_page_resolves_names_in_tenant_and_preserves_effective_scope(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.models.organization_version import StaffAssignment
    now=datetime.utcnow().replace(microsecond=0)
    tenant=1000000000000000001
    with get_sessionmaker()() as db:
        person=User(tenant_id=tenant,login_name='D604-staff',real_name='虚构任职教师',password_hash='fixture',user_type='TEACHER')
        foreign=User(tenant_id=tenant+1,login_name='foreign-account',real_name='不得泄露的他校姓名',password_hash='fixture',user_type='TEACHER')
        db.add_all([person,foreign]);db.flush()
        for i in range(21):
            db.add(StaffAssignment(tenant_id=tenant,user_id=person.id,org_type='CLASS',org_node_id=100+i,
                assignment_type='COUNSELOR',effective_at=now-timedelta(days=1),status='ACTIVE'))
        db.add(StaffAssignment(tenant_id=tenant,user_id=foreign.id,org_type='CLASS',org_node_id=900,
            assignment_type='COUNSELOR',effective_at=now-timedelta(days=1),status='ACTIVE'))
        db.add(StaffAssignment(tenant_id=tenant,user_id=person.id,org_type='CLASS',org_node_id=901,
            assignment_type='COUNSELOR',effective_at=now-timedelta(days=2),expires_at=now-timedelta(days=1),status='ACTIVE'))
        db.commit();person_id=person.id
    first=svc.list_assignments(tenant_id=tenant,page=1,page_size=20)
    second=svc.list_assignments(tenant_id=tenant,page=2,page_size=20)
    assert first['total']==22 and len(first['items'])==20 and len(second['items'])==2
    assert first['items'][0]['staffName'] is None and first['items'][0]['accountName'] is None
    assert all(row['staffName']=='虚构任职教师' for row in first['items'][1:]+second['items'])
    assert len(svc.effective_assignments(person_id,tenant_id=tenant))==21
    assert svc.list_assignments(tenant_id=tenant,page=1,include_expired=True)['total']==23
