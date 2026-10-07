"""Regression cases found in the second pre-delivery review; no application DB."""
import unittest
from optimizer.contracts import Snapshot
from optimizer.solver import solve
from optimizer.validation import validate_solution
from fixtures import snapshot, activity, option


def fixed(identifier, start=480, end=530, actor='teacher:t1'):
    return {'id': identifier, 'actors': [actor], 'roomId': None, 'campus': 'A',
            'occurrences': [{'key': 'old', 'date': '2026-09-14',
                             'start': start, 'end': end, 'periods': 1}]}


class PreflightReview(unittest.TestCase):
    def test_fixed_lessons_participate_in_quality(self):
        raw = snapshot([activity(options=[option('far', start=1000, end=1050),
            option('near', start=540, end=590, cost=1)])])
        raw['occupied'] = [fixed('existing')]
        result = solve(Snapshot.parse(raw), time_limit=2)
        self.assertEqual(result['choices']['1'], 'near')
        self.assertEqual(result['quality']['teacherGapMinutes'], 10)

    def test_fixed_conflicts_are_not_a_valid_snapshot(self):
        raw = snapshot()
        raw['occupied'] = [fixed('a', 600, 650, 'teacher:other'),
                           fixed('b', 600, 650, 'teacher:other')]
        result = solve(Snapshot.parse(raw), time_limit=2)
        self.assertEqual(result['status'], 'INPUT_CONFLICT')
        self.assertFalse(result['choices'])
