"""成绩审批读投影与实际入口使用同一当前身份门槛。"""
from sqlalchemy import select
import pytest
from app.core.context import set_tenant
from app.core.exceptions import AppException


def test_grade_approval_list_summary_detail_and_action_share_context_gate(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User,Role,UserRole,Permission,RolePermission,WorkflowInstance,WorkflowTask
    from app.services import approval_runtime_service as approval
    from app.services import approval_service as base
    tid=1000000000000000001
    with get_sessionmaker()() as db:
        actor=User(tenant_id=tid,login_name='d611_grade_context',real_name='独立成绩身份验证',user_type='TEACHER',status='ACTIVE',password_hash='unused-service-fixture')
        db.add(actor);db.flush();uid=actor.id
        contexts=[]
        for code,permissions in [('D611_CONFIG_ONLY',['approval.manage']),('D611_GRADE_REVIEW',['approval.manage','academicAffairs.grade.collegeReview'])]:
            role=Role(tenant_id=tid,role_code=code,role_name='独立验证职责',role_type='CUSTOM',status='ACTIVE')
            db.add(role);db.flush();db.add(UserRole(tenant_id=tid,user_id=uid,role_id=role.id,status='ACTIVE'))
            for permission in permissions:
                p=db.scalar(select(Permission).where(Permission.permission_code==permission));assert p,permission
                db.add(RolePermission(tenant_id=tid,role_id=role.id,permission_id=p.id,status='ACTIVE'))
            contexts.append({'userId':f'db-{uid}','loginName':actor.login_name,'userType':'TEACHER','currentRoleCode':code,'activeContextId':f'role:{role.id}','tenantId':str(tid)})
        ids=[]
        for n,(assignee,node) in enumerate([(uid,'COLLEGE_REVIEW'),(uid+99,'COLLEGE_REVIEW'),(uid,'ACADEMIC_REVIEW')]):
            instance=WorkflowInstance(tenant_id=tid,workflow_code='D611_GRADE_CONTEXT',source_module='academic-affairs',source_biz_type='AA_GRADE_TASK',source_biz_id=610+n,applicant_id=uid,status='RUNNING',current_node=node,title='独立成绩审批投影')
            db.add(instance);db.flush();task=WorkflowTask(tenant_id=tid,instance_id=instance.id,node_code=node,assignee_id=assignee,status='PENDING')
            db.add(task);db.flush();ids.append((task.id,task.instance_id,int(task.version or 0)))
        db.commit()
    set_tenant({'tenantId':str(tid)})
    try:
        for context,count in [(contexts[0],0),(contexts[1],1),(contexts[0],0)]:
            rows,total=base.list_tasks(1,20,user=context,biz_type='AA_GRADE_TASK')
            assert len(rows)==total==count
            summary=approval.summary(user=context)
            grade=next((r for r in summary['byBizType'] if r['bizType']=='AA_GRADE_TASK'),None)
            assert (grade['count'] if grade else 0)==count
        task_id,instance_id,version=ids[0]
        with pytest.raises(AppException) as denied:
            approval.get_task(str(task_id),user=contexts[0])
        assert denied.value.http_status==403
        with pytest.raises(AppException) as hidden:
            approval.get_task(str(ids[1][0]),user=contexts[1])
        assert hidden.value.http_status==404
        with pytest.raises(AppException) as denied:
            approval.approve(str(task_id),'当前身份不得跨业务审批',user=contexts[0],version=version)
        assert denied.value.http_status==403
        with get_sessionmaker()() as db:
            assert db.get(WorkflowTask,task_id).status=='PENDING'
            assert db.get(WorkflowTask,task_id).version==version
            assert db.get(WorkflowInstance,instance_id).status=='RUNNING'
    finally:
        set_tenant(None)
