import time,unittest
from optimizer.contracts import Snapshot
from optimizer.supervisor import solve_supervised
from fixtures import snapshot

class ProcessBoundaryTests(unittest.TestCase):
    def test_real_solver_subprocess_returns_validated_candidate(self):
        result=solve_supervised(Snapshot.parse(snapshot()),time_limit=2,hard_timeout=15)
        self.assertEqual(result['status'],'FEASIBLE')
        self.assertEqual(result['processExitCode'],0)
        self.assertFalse(result['publishable'])
    def test_process_deadline_stops_child(self):
        result=solve_supervised(Snapshot.parse(snapshot()),time_limit=2,hard_timeout=.02)
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual(result['diagnostics'][0]['code'],'PROCESS_DEADLINE')
        self.assertTrue(result['workerTerminated'])
    def test_cancellation_stops_only_own_solver_child(self):
        start=time.perf_counter()
        result=solve_supervised(Snapshot.parse(snapshot()),time_limit=2,hard_timeout=15,
                                cancelled=lambda:time.perf_counter()-start>.02)
        self.assertEqual(result['status'],'CANCELLED')
        self.assertEqual(result['choices'],{})
