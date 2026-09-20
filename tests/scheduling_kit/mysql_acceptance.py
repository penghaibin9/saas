"""Opt-in isolated candidate repository test; does not create or clean any database."""

import os,sys,json,pathlib


def main():
    if os.environ.get('YUEKE_OPTIMIZER_TEST_ALLOW_WRITES') != 'isolated-candidate-repository-test':
        print(json.dumps({'status':'BLOCKED_NOT_RUN','reason':'EXPLICIT_ISOLATED_TEST_OPT_IN_REQUIRED'}));return 77
    url=os.environ.get('YUEKE_OPTIMIZER_TEST_URL','')
    if not url:
        print(json.dumps({'status':'BLOCKED_NOT_RUN','reason':'ISOLATED_MYSQL_URL_REQUIRED'}));return 77
    root=pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/'backend/app/modules/academic_affairs'))
    sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
    dep=os.environ.get('YUEKE_OPTIMIZER_TEST_DEPENDENCIES')
    if dep:sys.path.insert(0,dep)
    from sqlalchemy import create_engine,select,func,text,update
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.exc import IntegrityError
    from optimizer.persistence import Repository,snapshots,jobs
    from optimizer.contracts import Snapshot,InputError
    from optimizer.solver import solve
    from fixtures import snapshot
    parsed=make_url(url)
    if not parsed.drivername.startswith('mysql') or parsed.host not in {'127.0.0.1','localhost','::1'} or not (parsed.database or '').startswith('yueke_optimizer_test_'):
        print(json.dumps({'status':'REFUSED','reason':'ONLY_LOOPBACK_DEDICATED_TEST_NAMESPACE_ALLOWED'}));return 78
    engine=create_engine(url,pool_size=4,max_overflow=0,pool_timeout=3,connect_args={'connect_timeout':5})
    factory=sessionmaker(engine,expire_on_commit=False)
    results=[];audit=[]
    def ok(name,condition):
        if not condition:raise AssertionError(name)
        results.append({'test':name,'status':'PASS'})
    try:
        with engine.connect() as db:
            actual=db.scalar(text('SELECT DATABASE()'));version=db.scalar(text('SELECT VERSION()'))
            tables=set(db.scalars(text('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')))
            required={snapshots.name,jobs.name}
            if tables not in (required,required|{'alembic_version'}):
                raise RuntimeError('Target must contain only the candidate test tables and optional Alembic metadata')
            if any(db.scalar(select(func.count()).select_from(table)) for table in [snapshots,jobs]):
                raise RuntimeError('Target is not empty; no data has been deleted')
            if actual!=parsed.database or not str(version).startswith('8.'):
                raise RuntimeError('Verified isolated MySQL 8 target required')
        def audit_hook(db,action,job,detail):audit.append((action,job))
        def no_business_admission(db,snap):
            # Repository-only fixture; the application batch lock is explicitly NOT tested here.
            if snap.batch!='20':raise RuntimeError('Fixture batch mismatch')
        a='9000000000000000001';b='9000000000000000002'
        ra=Repository(factory,tenant_id=a,audit_hook=audit_hook,admission_hook=no_business_admission)
        rb=Repository(factory,tenant_id=b,audit_hook=audit_hook,admission_hook=no_business_admission)
        ca={'userId':'fixture-teacher','tenantId':a,'roleCode':'TEST_ONLY'}
        cb={'userId':'fixture-teacher','tenantId':b,'roleCode':'TEST_ONLY'}
        raw=snapshot();raw['scope']['tenantId']=a;sa=Snapshot.parse(raw)
        raw=snapshot();raw['scope']['tenantId']=b;sb=Snapshot.parse(raw)
        first=ra.enqueue_verified(sa,actor='fixture-teacher',idempotency_key='fixture-request-0001',options={},reason='isolated test only',actor_context=ca)
        again=ra.enqueue_verified(sa,actor='fixture-teacher',idempotency_key='fixture-request-0001',options={},reason='isolated test only',actor_context=ca)
        ok('idempotent_same_key_same_job',first['jobId']==again['jobId'])
        ok('same_command_one_audit',sum(x[0]=='CANDIDATE_ENQUEUE' for x in audit)==1)
        try:ra.get(b,first['jobId'])
        except InputError as error:ok('bound_repository_rejects_other_tenant',error.code=='TENANT_SCOPE_MISMATCH')
        else:raise AssertionError('cross tenant repository access')
        try:rb.get(b,first['jobId'])
        except InputError as error:ok('other_school_cannot_read_local_id',error.code=='JOB_NOT_FOUND')
        else:raise AssertionError('cross tenant row access')
        try:ra.enqueue_verified(sa,actor='fixture-teacher',idempotency_key='fixture-request-0001',options={},reason='different request',actor_context=ca)
        except InputError as error:ok('idempotency_payload_conflict',error.code=='IDEMPOTENCY_CONFLICT')
        else:raise AssertionError('idempotency conflict not rejected')
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:claimed=list(pool.map(lambda _:ra.claim(a),[0,1]))
        actual_claims=[x for x in claimed if x]
        ok('two_workers_single_claim',len(actual_claims)==1)
        claim=actual_claims[0];solved=solve(sa,time_limit=2)
        ok('wrong_lease_cannot_finish',ra.finish(a,first['jobId'],'wrong',solved,source_current=True) is False)
        ok('valid_lease_finishes',ra.finish(a,first['jobId'],claim['leaseToken'],solved,source_current=True) is True)
        ok('result_readback',ra.get(a,first['jobId'])['state']=='SUCCEEDED')
        def failing_audit(*args):raise RuntimeError('synthetic audit failure')
        rf=Repository(factory,tenant_id=a,audit_hook=failing_audit,admission_hook=no_business_admission)
        try:rf.enqueue_verified(sa,actor='fixture-teacher',idempotency_key='fixture-audit-fail',options={},reason='audit rollback test',actor_context=ca)
        except RuntimeError:pass
        else:raise AssertionError('audit failure not propagated')
        ok('failed_audit_rolls_back_job',ra.find_by_key(a,'20','fixture-audit-fail') is None)
        cancel=rb.enqueue_verified(sb,actor='fixture-teacher',idempotency_key='fixture-cancel-0001',options={},reason='cancel test only',actor_context=cb)
        running=rb.claim(b);version_now=rb.get(b,cancel['jobId'])['version']
        receipt=rb.cancel(b,cancel['jobId'],version_now)
        ok('cancel_receipt',receipt['state']=='CANCELLED')
        ok('cancelled_lease_cannot_overwrite',rb.finish(b,cancel['jobId'],running['leaseToken'],solve(sb,time_limit=2),source_current=True) is False)
        print(json.dumps({'status':'PASS_REPOSITORY_ONLY','database':actual,'version':version,'tests':results,
            'notProven':['application principal and permissions','school batch admission lock','same-transaction application audit model','four-end publication','real school inputs'],
            'cleanup':'None. Isolated fixture rows retained for inspection.'},indent=2));return 0
    finally:engine.dispose()

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'FAIL','errorType':type(error).__name__,
                          'reason':'Review the isolated environment; connection strings and SQL parameters are not printed.'}));raise SystemExit(1)