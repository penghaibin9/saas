from app.core.context import set_tenant


def test_leave_todo_batch_comes_from_same_school_source_record(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch,InternshipRecord,InternshipLeave,UnifiedTodo
    from app.services.workbench_todo_service import list_todos
    tid=1000000000000000001;uid=611311
    with get_sessionmaker()() as db:
        batch=InternshipBatch(tenant_id=tid,batch_no='D611_ROUTE_BATCH',batch_name='独立跳转批次',status='DRAFT')
        db.add(batch);db.flush()
        record=InternshipRecord(tenant_id=tid,student_id=611,batch_id=batch.id,advisor_user_id=uid)
        db.add(record);db.flush()
        leave=InternshipLeave(tenant_id=tid,internship_id=record.id,student_id=611,start_date='2026-10-27',end_date='2026-10-27',reason='独立路由验证',status='PENDING')
        db.add(leave);db.flush()
        todo=UnifiedTodo(tenant_id=tid,source_module='internship',source_biz_type='INTERN_LEAVE',source_biz_id=leave.id,todo_type='INTERN_LEAVE_APPROVAL',assignee_id=uid,title='独立跨批次跳转',status='PENDING')
        db.add(todo);db.commit();batch_id,leave_id,record_id=batch.id,leave.id,record.id
    set_tenant({'tenantId':str(tid)})
    try:
        actor={'userId':f'db-{uid}','currentRoleCode':'SCHOOL_ADMIN','userType':'TEACHER','tenantId':str(tid)}
        rows,total=list_todos(actor,status='PENDING',todo_type='INTERN_LEAVE_APPROVAL')
        assert total==1 and rows[0]['query']['id']==str(leave_id)
        assert rows[0]['query']['batchId']==str(batch_id)
        from app.services.workbench_snapshot_service import snapshot
        first_screen = snapshot(actor)['todos']['items']
        assert len(first_screen)==1 and first_screen[0]['query']['batchId']==str(batch_id)
        with get_sessionmaker()() as db:
            record=db.get(InternshipRecord,record_id);record.tenant_id=tid+99;db.commit()
        rows,total=list_todos(actor,status='PENDING',todo_type='INTERN_LEAVE_APPROVAL')
        assert 'batchId' not in rows[0]['query']
    finally:
        set_tenant(None)
