from types import SimpleNamespace
from sqlalchemy.dialects import mysql
from app.modules.internship.services import internship_enterprise_application_decision_service as service

def test_search_keeps_scope_count_pagination_and_literal_wildcards():
    class DB:
        statements=[]
        def scalar(self,q):self.statements.append(q);return 0
        def execute(self,q):self.statements.append(q);return SimpleNamespace(all=lambda:[])
    db=DB()
    assert service.list_owned_applications_in_tx(db,context=SimpleNamespace(tenant_id=11,batch_id=22,campaign_id=33,company_id=44),keyword='岗位%_',page=2,page_size=20)==([],0)
    for query in db.statements:
        sql=str(query.compile(dialect=mysql.dialect(),compile_kwargs={'literal_binds':True}))
        assert 'company_id = 44' in sql and 'tenant_id = 11' in sql and 'campaign_id = 33' in sql
        assert 'JSON_EXTRACT' in sql and '/%%/_' in sql
    assert 'LIMIT 20, 20' in str(db.statements[1].compile(dialect=mysql.dialect(),compile_kwargs={'literal_binds':True}))
