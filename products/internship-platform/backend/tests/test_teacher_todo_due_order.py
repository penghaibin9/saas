from contextlib import contextmanager
from datetime import datetime,timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.api.v1 import teacher_mobile_workbench as workbench
from app.models import UnifiedTodo

def test_due_todos_precede_undated_and_counts_keep_teacher_tenant_scope(monkeypatch):
    engine=create_engine('sqlite+pysqlite:///:memory:')
    UnifiedTodo.__table__.create(engine)
    with Session(engine) as db:
        now=datetime(2026,10,28,12)
        for ident,due,tenant,assignee in [(1,None,1,11),(2,now-timedelta(days=1),1,11),(3,now+timedelta(days=1),1,11),(4,now-timedelta(days=2),2,11),(5,now-timedelta(days=2),1,12)]:
            db.add(UnifiedTodo(id=ident,tenant_id=tenant,assignee_id=assignee,source_module='internship',source_biz_id=ident,todo_type='INTERN_WEEKLY_REVIEW',title='虚构报告待办',status='PENDING',due_at=due))
        db.commit()
        @contextmanager
        def session():yield db
        monkeypatch.setattr(workbench,'session',session);monkeypatch.setattr(workbench,'_tid',lambda:1)
        first=workbench.todos(status='PENDING',group='ALL',page=1,pageSize=2,user={'userId':'db-11'})['data']
        assert [row['todoId'] for row in first['items']]==['2','3']
        assert first['total']==3 and first['groupCounts']['REPORT']==3 and first['hasMore']
        last=workbench.todos(status='PENDING',group='ALL',page=2,pageSize=2,user={'userId':'db-11'})['data']
        assert [row['todoId'] for row in last['items']]==['1']
    engine.dispose()
