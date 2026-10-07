import copy
import unittest
from selected_pytest_shards import make_plan, verify

class ShardReceiptTests(unittest.TestCase):
    def setUp(self):
        self.plan=make_plan([f"tests/test_case_{i}.py" for i in range(50)],"a"*40,4)
        self.receipts=[{"shard":s["id"],"files":s["files"],"sha":self.plan["sha"],
            "unionHash":self.plan["unionHash"],"exitCode":0,"junitValid":True,
            "tests":len(s["files"]),"failures":0,"errors":0} for s in self.plan["shards"]]
    def test_union_is_exact(self):
        self.assertFalse(verify(self.plan,self.receipts))
    def test_timeout_never_passes(self):
        self.receipts[0]["exitCode"]=124
        self.assertTrue(verify(self.plan,self.receipts))
    def test_lost_receipt_rejected(self):
        self.assertTrue(verify(self.plan,self.receipts[:-1]))
    def test_duplicate_receipt_rejected(self):
        self.assertTrue(verify(self.plan,self.receipts+[self.receipts[0]]))
    def test_changed_source_rejected(self):
        self.receipts[0]["sha"]="b"*40
        self.assertTrue(verify(self.plan,self.receipts))
    def test_reduced_union_rejected(self):
        self.receipts[0]["files"]=[]
        self.assertTrue(verify(self.plan,self.receipts))
    def test_missing_junit_rejected(self):
        self.receipts[0]["junitValid"]=False
        self.assertTrue(verify(self.plan,self.receipts))
    def test_empty_selection_rejected(self):
        with self.assertRaises(ValueError): make_plan([],"a",4)
    def test_failing_assertion_rejected(self):
        self.receipts[0]["failures"]=1
        self.assertTrue(verify(self.plan,self.receipts))
    def test_deterministic(self):
        self.assertEqual(self.plan,make_plan(list(reversed(self.plan["files"])),"a"*40,4))

if __name__=="__main__": unittest.main()
