from app.core.context import set_tenant


def test_material_todo_uses_source_business_permission_and_same_tenant(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo
    from app.models.affairs_operations import AffairsMaterialRequirement
    from app.services.workbench_todo_service import list_todos,count_todos
    tid=1000000000000000001;uid=611312
    with get_sessionmaker()() as db:
        known=AffairsMaterialRequirement(tenant_id=tid,student_id=1,biz_type='LEAVE',biz_id=1,item_code='D611_KNOWN',item_name='独立权限核验材料',status='PENDING_REVIEW',review_owner_id=uid)
        unknown=AffairsMaterialRequirement(tenant_id=tid,student_id=1,biz_type='UNREGISTERED',biz_id=2,item_code='D611_UNKNOWN',item_name='独立未知来源材料',status='PENDING_REVIEW',review_owner_id=uid)
        db.add_all([known,unknown]);db.flush()
        for req in [known,unknown]:
            db.add(UnifiedTodo(tenant_id=tid,source_module='student-affairs',source_biz_type='MATERIAL_REQUIREMENT',source_biz_id=req.id,todo_type='MATERIAL_REVIEW',assignee_id=uid,title='独立材料权限验证',status='PENDING'))
        db.commit();known_id=known.id
    set_tenant({'tenantId':str(tid)})
    try:
        config={'userId':f'db-{uid}','userType':'TEACHER','currentRoleCode':'SYS_ADMIN','tenantId':str(tid)}
        business={**config,'currentRoleCode':'SCHOOL_ADMIN'}
        assert list_todos(config,status='PENDING')[1]==0
        rows,total=list_todos(business,status='PENDING')
        assert total==1 and rows[0]['sourceBizId']==str(known_id)
        assert count_todos(business)['total']==1
        with get_sessionmaker()() as db:
            db.get(AffairsMaterialRequirement,known_id).tenant_id=tid+99;db.commit()
        assert list_todos(business,status='PENDING')[1]==0
    finally:
        set_tenant(None)
