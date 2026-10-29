"""通用审批不得只结束调课任务而绕过正式课表事务。"""
import pytest
from app.core.context import set_tenant
from app.core.exceptions import AppException


def test_schedule_decisions_require_business_entry_and_preserve_all_rows(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User, WorkflowInstance, WorkflowTask
    from app.services import db_service, approval_service, approval_runtime_service as runtime

    tid = 1000000000000000001
    with get_sessionmaker()() as db:
        actor = User(tenant_id=tid, login_name='schedule_guard_actor', real_name='调课入口验证', user_type='TEACHER', password_hash='unused-service-fixture', status='ACTIVE')
        target = User(tenant_id=tid, login_name='schedule_guard_target', real_name='调课转办验证', user_type='TEACHER', password_hash='unused-service-fixture', status='ACTIVE')
        db.add_all([actor, target]); db.flush()
        uid, target_id = actor.id, target.id
        inst = WorkflowInstance(tenant_id=tid, workflow_code='ACAD_SCHEDULE_CHANGE', source_module='academic-affairs', source_biz_type='AA_SCHEDULE_CHANGE', source_biz_id=999, applicant_id=uid, status='RUNNING', current_node='ACADEMIC_REVIEW', remark='内部恢复备注，绝不是申请人姓名')
        db.add(inst); db.flush()
        task = WorkflowTask(tenant_id=tid, instance_id=inst.id, node_code='ACADEMIC_REVIEW', assignee_id=uid, status='PENDING')
        db.add(task); db.flush()
        task_id, instance_id, version = task.id, inst.id, int(task.version or 0)
        db.commit()
    set_tenant({'tenantId': str(tid)})
    user = {'userId': f'db-{uid}', 'tenantId': str(tid), 'loginName': 'schedule_guard_actor', 'userType': 'TEACHER', 'currentRoleCode': 'TEACHER'}
    actions = [
        lambda: db_service.act_task(task_id, 'APPROVED', user=user, version=version),
        lambda: db_service.act_task(task_id, 'REJECTED', '入口隔离验证', user=user, version=version),
        lambda: db_service.act_task(task_id, 'TRANSFERRED', target=str(target_id), user=user, version=version),
        lambda: approval_service.return_for_revision(task_id, '入口隔离验证', user=user, version=version),
        lambda: runtime.approve(task_id, '', user=user, version=version, expected_source_version=0),
        lambda: runtime.return_for_revision(task_id, '入口隔离验证', user=user, version=version, expected_source_version=0),
        lambda: runtime.resubmit(instance_id, user=user, version=0),
    ]
    try:
        for action in actions:
            with pytest.raises(AppException) as denied:
                action()
            assert denied.value.http_status == 409
            assert '调停课审批' in denied.value.message
            with get_sessionmaker()() as db:
                assert db.get(WorkflowTask, task_id).status == 'PENDING'
                assert db.get(WorkflowTask, task_id).version == version
                assert db.get(WorkflowInstance, instance_id).status == 'RUNNING'
                assert db.query(WorkflowTask).filter_by(instance_id=instance_id).count() == 1
        # The public transfer wrapper rejects this deliberately unconfigured node earlier.
        with pytest.raises(AppException) as transfer_denied:
            runtime.transfer(task_id, str(target_id), '', user=user, version=version)
        assert transfer_denied.value.http_status == 403
        assert '转办责任角色' in transfer_denied.value.message
        with get_sessionmaker()() as db:
            assert db.get(WorkflowTask, task_id).status == 'PENDING'
            assert db.get(WorkflowInstance, instance_id).status == 'RUNNING'
            assert db.query(WorkflowTask).filter_by(instance_id=instance_id).count() == 1
        detail = runtime.get_task(str(task_id), user=user)
        assert detail['allowedActions'] == []
        assert detail['sourceBizId'] == '999'
        assert detail['applicantName'] == '调课入口验证'
        assert detail['history'][0]['assigneeName'] == '调课入口验证'
        rows, _ = runtime.list_tasks(1, 20, user=user)
        assert next(row for row in rows if row['taskId'] == str(task_id))['applicantName'] == '调课入口验证'
        with get_sessionmaker()() as db:
            foreign = User(tenant_id=tid+1, login_name='foreign_schedule_actor', real_name='外校姓名不得泄露', user_type='TEACHER', password_hash='unused-service-fixture')
            db.add(foreign); db.flush()
            foreign_id = foreign.id
            db.get(WorkflowInstance, instance_id).applicant_id = foreign_id
            db.add(WorkflowTask(tenant_id=tid, instance_id=instance_id, node_code='COLLEGE_REVIEW', assignee_id=foreign_id, status='APPROVED'))
            db.commit()
        masked = runtime.get_task(str(task_id), user=user)
        assert masked['applicantName'] == ''
        assert next(item for item in masked['history'] if item['assigneeId'] == str(foreign_id))['assigneeName'] == ''
        masked_rows, _ = runtime.list_tasks(1, 20, user=user)
        assert next(row for row in masked_rows if row['taskId'] == str(task_id))['applicantName'] == ''
        from types import SimpleNamespace
        from app.modules.academic_affairs.services.academic_affairs_schedule_change_service import _review_node
        with get_sessionmaker()() as db:
            db.get(WorkflowInstance, instance_id).status = 'APPROVED'
            db.flush()
            node = _review_node(db, SimpleNamespace(status='COLLEGE_REVIEW', workflow_instance_id=instance_id, origin_item_id=None), user)
            assert node['canReview'] is False
            assert '审批流程已结束' in node['reason']
    finally:
        set_tenant(None)
