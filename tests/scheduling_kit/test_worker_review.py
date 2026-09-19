import unittest
from optimizer.contracts import Snapshot,InputError
from optimizer.options import normalize_options
from optimizer.persistence import run_one
from fixtures import snapshot

class FakeRepository:
    def __init__(self, options=None):
        self.options=options or {};self.result=None;self.state='RUNNING';self.claims=0
    def claim(self,tenant_id):
        self.claims+=1
        return {'jobId':'1','leaseToken':'fixture','snapshot':Snapshot.parse(snapshot()),'options':self.options}
    def finish(self,tenant_id,job_id,token,result,**kw):
        self.result=result;self.state=result['status'];return True
    def get(self,*args):return {'state':self.state}

class WorkerReviewTests(unittest.TestCase):
    def test_invalid_options_rejected_and_receipted(self):
        repo=FakeRepository({'time_limit':-1})
        run_one(repo,'1000000000000000007',source_validator=lambda s:True,execution_allowed=lambda:True,actor_allowed=lambda job:True)
        self.assertEqual(repo.result['status'],'REJECTED')
        self.assertEqual(repo.result['diagnostics'][0]['code'],'INVALID_TIME_LIMIT')
    def test_source_reader_failure_receipted_without_secret(self):
        repo=FakeRepository()
        def fail(_):raise RuntimeError('private database password')
        run_one(repo,'1000000000000000007',source_validator=fail,execution_allowed=lambda:True,actor_allowed=lambda job:True)
        self.assertEqual(repo.result['status'],'FAILED')
        self.assertNotIn('password',str(repo.result))
    def test_revoked_school_does_not_claim(self):
        repo=FakeRepository()
        self.assertIsNone(run_one(repo,'1000000000000000007',source_validator=lambda s:True,execution_allowed=lambda:False,actor_allowed=lambda job:True))
        self.assertEqual(repo.claims,0)
    def test_stale_source_never_solves(self):
        repo=FakeRepository()
        run_one(repo,'1000000000000000007',source_validator=lambda s:False,execution_allowed=lambda:True,actor_allowed=lambda job:True)
        self.assertEqual(repo.result['status'],'STALE')
        self.assertEqual(repo.result['choices'],{})
    def test_options_fingerprint_defaults_are_stable(self):
        self.assertEqual(normalize_options({}),normalize_options({'profile':'BALANCED','time_limit':10,'seed':0}))
    def test_nan_bool_budget_and_unknown_options(self):
        for data in [{'time_limit':float('nan')},{'time_limit':True},{'seed':False},{'publish':True}]:
            with self.subTest(data=data),self.assertRaises(InputError):normalize_options(data)
    def test_outside_repair_scope_rejected_before_enqueue(self):
        with self.assertRaisesRegex(InputError,'UNKNOWN_REPAIR_ACTIVITY'):
            normalize_options({'allowed_change_ids':['99']},Snapshot.parse(snapshot()))

    def test_revoked_creator_cannot_execute_queued_work(self):
        repo=FakeRepository()
        run_one(repo,'1000000000000000007',source_validator=lambda s:True,
                execution_allowed=lambda:True,actor_allowed=lambda job:False)
        self.assertEqual(repo.result['status'],'REJECTED')
        self.assertEqual(repo.result['diagnostics'][0]['code'],'CREATOR_AUTHORIZATION_LOST')
