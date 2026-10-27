"""真实隔离库核验四域待办来源；状态夹具不代表浏览器业务流程验收。"""
from types import SimpleNamespace
import pytest
from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.services.todo_task_service import _completed_source


def test_source_validation_uses_matching_domain_tenant_and_current_state(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationProposal, AaGradeTask, InternshipLeave
    from app.models.affairs_funding_ext import FeeReduction
    tid = 1000000000000000001
    set_tenant({'tenantId': str(tid)})
    try:
        with get_sessionmaker()() as db:
            examples = [
                ('student-affairs','FEE_REDUCTION','FEE_REDUCTION_REVIEW',FeeReduction(tenant_id=tid,student_id=1,status='ISSUED'),'SUBMITTED'),
                ('academic-affairs','AA_GRADE_TASK','AA_GRADE_ENTRY',AaGradeTask(tenant_id=tid,status='SUBMITTED'),'RETURNED'),
                ('graduation','GD_PROPOSAL','GD_PROPOSAL_REVIEW',GraduationProposal(tenant_id=tid,gd_student_id=1,status='APPROVED'),'PENDING_REVIEW'),
                ('internship','INTERN_LEAVE','INTERN_LEAVE_APPROVAL',InternshipLeave(tenant_id=tid,internship_id=1,student_id=1,start_date='2026-10-01',end_date='2026-10-02',reason='独立来源核验',status='APPROVED'),'PENDING'),
            ]
            for module, biz, kind, source, pending in examples:
                db.add(source);db.flush()
                todo=SimpleNamespace(source_module=module,source_biz_type=biz,source_biz_id=source.id,todo_type=kind)
                assert _completed_source(db,todo).id == source.id
                terminal=source.status
                source.status=pending;db.flush()
                with pytest.raises(AppException,match='来源业务') as rejected:
                    _completed_source(db,todo)
                from app.core.response import fail
                assert fail(rejected.value.code,rejected.value.message)['code']==409001
                source.status=terminal;source.is_deleted=True;db.flush()
                with pytest.raises(AppException) as unknown: _completed_source(db,todo)
                assert fail(unknown.value.code,unknown.value.message)['code']==409001
                source.is_deleted=False;db.flush()
                set_tenant({'tenantId':str(tid+99)})
                with pytest.raises(AppException): _completed_source(db,todo)
                set_tenant({'tenantId':str(tid)})
                todo.source_biz_type='UNREGISTERED'
                with pytest.raises(AppException): _completed_source(db,todo)
            db.rollback()
    finally:
        set_tenant(None)
