"""Real FastAPI/Pydantic HTTP contract tests with explicit auth/service doubles.
These do NOT prove the project's real authorization, SQL or registration startup.
"""
import pathlib,sys,types,unittest
from contextlib import contextmanager
from fastapi import FastAPI,Header,HTTPException
from fastapi.testclient import TestClient

ROOT=pathlib.Path(__file__).resolve().parents[2]

@contextmanager
def router_fixture():
    names=['app','app.core','app.core.permissions','app.core.response','app.modules',
           'app.modules.academic_affairs','app.modules.academic_affairs.services']
    saved={name:sys.modules.get(name) for name in names};calls=[]
    for name in names:
        module=types.ModuleType(name);module.__path__=[];sys.modules[name]=module
    def permission(code):
        def dependency(x_test_permission:str=Header(default='')):
            if x_test_permission not in {code,'all'}:raise HTTPException(403,'test permission denied')
            return {'userId':'fixture-admin'}
        return dependency
    def module_guard(code):
        def dependency(x_test_module:str=Header(default='enabled')):
            if x_test_module!='enabled':raise HTTPException(403,'test module disabled')
            return True
        return dependency
    sys.modules['app.core.permissions'].require_permission=permission
    sys.modules['app.core.permissions'].require_module=module_guard
    sys.modules['app.core.response'].success=lambda data:{'code':0,'data':data}
    def action(name):
        def handler(*args):calls.append((name,args));return {'handler':name,'batchId':args[1]}
        return handler
    jobs=types.SimpleNamespace(**{name:action(name) for name in ['_authorize','context','enqueue','get_job','cancel_job','preview_rows','lookup_job']})
    services=sys.modules['app.modules.academic_affairs.services']
    services.schedule_optimizer_jobs_service=jobs
    jobs._tid=lambda:'1000000000000000007'
    jobs.dispatch_worker=lambda tenant_id:None
    services.schedule_optimizer_readiness_service=types.SimpleNamespace(readiness=action('readiness'))
    try:
        path=ROOT/'backend/app/modules/academic_affairs/routers/schedule_optimizer_router.py'
        scope={'__name__':'isolated_router_under_test'};exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),scope)
        app=FastAPI();app.include_router(scope['router'],prefix='/api/v1')
        with TestClient(app) as client:yield client,calls
    finally:
        for name,value in saved.items():
            if value is None:sys.modules.pop(name,None)
            else:sys.modules[name]=value

BASE='/api/v1/academic-affairs/scheduling/batches/20/optimizer'
VIEW={'x-test-permission':'academicAffairs.schedule.view'}
MANAGE={'x-test-permission':'academicAffairs.schedule.rule.manage'}
BODY={'expectedSourceRevision':'a'*64,'idempotencyKey':'test-request-123',
      'reason':'confirmed sample','plan':{'version':1},'options':{}}

class CandidateHttpContract(unittest.TestCase):
    def test_read_uses_existing_view_permission(self):
        with router_fixture() as (client,calls):
            self.assertEqual(client.get(BASE+'/context',headers=VIEW).status_code,200)
            self.assertEqual(calls[-1][0],'context')
    def test_view_permission_is_not_write_permission(self):
        with router_fixture() as (client,calls):
            self.assertEqual(client.post(BASE+'/jobs',headers=VIEW,json=BODY).status_code,403)
            self.assertEqual(calls,[])
    def test_valid_enqueue_passes_exact_body_and_string_id(self):
        with router_fixture() as (client,calls):
            self.assertEqual(client.post(BASE+'/jobs',headers=MANAGE,json=BODY).status_code,200)
            self.assertEqual(calls[-1][1][1],'20');self.assertEqual(calls[-1][1][2],BODY)
    def test_body_extra_fields_cannot_claim_direct_publication(self):
        with router_fixture() as (client,calls):
            self.assertEqual(client.post(BASE+'/jobs',headers=MANAGE,json={**BODY,'publish':True}).status_code,422)
            self.assertEqual(calls,[])
    def test_cancel_requires_strict_integer_version(self):
        with router_fixture() as (client,calls):
            for value in [True,'1',-1,1.5,None]:
                self.assertEqual(client.post(BASE+'/jobs/1/cancel',headers=MANAGE,json={'expectedVersion':value}).status_code,422)
            self.assertEqual(calls,[])
    def test_wrong_job_path_and_week_rejected_before_service(self):
        with router_fixture() as (client,calls):
            self.assertEqual(client.get(BASE+'/jobs/not-a-number',headers=VIEW).status_code,422)
            self.assertEqual(client.get(BASE+'/jobs/1/preview?week=W99',headers=VIEW).status_code,422)
            self.assertEqual(calls,[])
    def test_module_guard_remains_attached(self):
        with router_fixture() as (client,calls):
            self.assertEqual(client.get(BASE+'/context',headers={**VIEW,'x-test-module':'disabled'}).status_code,403)
            self.assertEqual(calls,[])
    def test_draft_apply_route_without_independent_publish(self):
        with router_fixture() as (client,calls):
            paths=client.get('/openapi.json').json()['paths']
            self.assertEqual(len(paths),8)
            self.assertTrue(any(path.endswith('/apply') for path in paths))
            self.assertFalse(any(path.endswith('/publish') for path in paths))
