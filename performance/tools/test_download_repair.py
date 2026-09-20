import os
import unittest
from ephemeral_capacity_guard import assert_ephemeral_target
from evaluate_capacity_result import measured_route_failures, REQUIRED_STUDENT, REQUIRED_TEACHER, _identity_pool_assertion

class CapacityRepairTests(unittest.TestCase):
    def setUp(self):
        self.env={'APP_ENV':'test','DEPLOYMENT_MODE':'local','CAPACITY_EPHEMERAL_ACK':'student_lifecycle_test',
            'DATABASE_URL':'mysql+pymysql://u:p@127.0.0.1:3306/student_lifecycle_test?charset=utf8mb4',
            'TEST_DATABASE_URL':'mysql+pymysql://u:p@127.0.0.1:3306/student_lifecycle_test?charset=utf8mb4'}
    def test_exact_ephemeral_target_accepted(self):self.assertTrue(assert_ephemeral_target(self.env))
    def test_production_environment_rejected(self):
        for key,value in [('APP_ENV','production'),('DEPLOYMENT_MODE','production'),('DEPLOYMENT_MODE','development'),('CAPACITY_EPHEMERAL_ACK','')]:
            with self.subTest(key=key),self.assertRaises(ValueError):assert_ephemeral_target({**self.env,key:value})
    def test_remote_lookalike_socket_and_alt_database_rejected(self):
        for url in ['mysql+pymysql://u:p@example.test/student_lifecycle_test',
                    'mysql+pymysql://u:p@127.0.0.1/student_lifecycle_test_backup',
                    'mysql+pymysql://u:p@127.0.0.1/student_lifecycle_test?unix_socket=/tmp/prod.sock',
                    'sqlite:///student_lifecycle_test','mysql+pymysql://u:p@localhost:3310/student_lifecycle_test']:
            with self.subTest(url=url),self.assertRaises(ValueError):
                assert_ephemeral_target({**self.env,'DATABASE_URL':url,'TEST_DATABASE_URL':url})
    def test_database_url_mismatch_rejected(self):
        with self.assertRaises(ValueError):assert_ephemeral_target({**self.env,'TEST_DATABASE_URL':''})
    def test_zero_latency_metrics_and_advertised_empty_missing_array_do_not_prove_coverage(self):
        doc={'scenario':'mixed','measurementSchema':2,'missingRoutes':[], 'routes':{r:{'p95':0,'p99':0} for r in REQUIRED_STUDENT|REQUIRED_TEACHER}}
        self.assertEqual(set(measured_route_failures(doc)),REQUIRED_STUDENT|REQUIRED_TEACHER)
    def test_all_real_samples_pass(self):
        doc={'scenario':'mixed','measurementSchema':2,'measuredRoutes':{r:{'attempts':50,'successes':50} for r in REQUIRED_STUDENT|REQUIRED_TEACHER}}
        self.assertFalse(measured_route_failures(doc))
        doc['measuredRoutes']['teacher_visit']['successes']=0
        self.assertEqual(measured_route_failures(doc),['teacher_visit'])
    def test_inconsistent_samples_fail(self):
        doc={'scenario':'student','measurementSchema':2,'measuredRoutes':{r:{'attempts':1,'successes':2} for r in REQUIRED_STUDENT}}
        self.assertEqual(set(measured_route_failures(doc)),REQUIRED_STUDENT)
    def test_unique_jwts_for_same_student_are_not_identity_scale(self):
        doc={'scenario':'mixed','identity':{'studentTokensAvailable':300,'teacherTokensAvailable':300,
            'uniqueStudentTokens':300,'uniqueTeacherTokens':300,'uniqueTeacherContexts':300,
            'uniqueStudentSubjects':1,'uniqueTeacherSubjects':300,'identityClaimsComplete':True}}
        self.assertFalse(_identity_pool_assertion(doc,profile='p300',mode='cold')[0])
        doc['identity']['uniqueStudentSubjects']=300
        self.assertTrue(_identity_pool_assertion(doc,profile='p300',mode='cold')[0])

class CapacityCommercialFixtureTests(unittest.TestCase):
    def test_owned_paid_order_is_reused_without_mutation(self):
        from seed_local_capacity_env import _activate_owned_capacity_order, CAPACITY_ORDER_REMARK
        class Platform:
            def list_orders(self, **kwargs):
                return [{"orderNo":"OWNED", "remark":CAPACITY_ORDER_REMARK, "packageCode":"professional",
                         "orderType":"NEW", "status":"paid", "amount":1, "version":2}]
        class Commercial:
            def commercial_state(self, tid):
                return {"verified":True, "authoritySource":"PAID_ORDER", "commercialOrderNo":"OWNED",
                        "features":{"internship":True,"employment":True}}
        self.assertEqual(_activate_owned_capacity_order(Platform(),Commercial()),"OWNED")
    def test_foreign_order_fails_before_payment_or_activation(self):
        from seed_local_capacity_env import _activate_owned_capacity_order
        class Platform:
            def list_orders(self, **kwargs):return [{"remark":"foreign"}]
        with self.assertRaises(ValueError):_activate_owned_capacity_order(Platform(),None)
    def test_fixture_uses_new_order_and_canonical_activation(self):
        from seed_local_capacity_env import _activate_owned_capacity_order, CAPACITY_ORDER_REMARK
        class Commercial:
            paid=False
            def commercial_state(self, tid):
                return {"packageCode":"professional" if self.paid else "trial", "verified":self.paid,
                        "authoritySource":"PAID_ORDER" if self.paid else "TRIAL", "commercialOrderNo":"OWNED",
                        "features":{"internship":self.paid,"employment":self.paid}}
        c=Commercial()
        class Platform:
            def list_orders(self, **kwargs):return []
            def create_order(self, body):
                assert body["remark"]==CAPACITY_ORDER_REMARK and body["orderType"]=="NEW"
                return {"orderNo":"OWNED","status":"unpaid","version":1}
            def order_action(self, number, action, **kwargs):
                assert number=="OWNED" and action=="mark-paid" and kwargs["expected_version"]==1
                c.paid=True
                return {"tenantActivated":True,"version":2}
        self.assertEqual(_activate_owned_capacity_order(Platform(),c),"OWNED")

if __name__=='__main__':unittest.main()
