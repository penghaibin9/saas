"""Malformed legacy rule switches must remain repairable without bypassing scoring rules."""
import unittest
from types import SimpleNamespace

from app.core.exceptions import AppException
from app.modules.graduation.services import graduation_batch_service as batches
from app.modules.graduation.services import graduation_grade_service as grades


class GraduationRulesShapeTest(unittest.TestCase):
    def test_switches_and_numbers_are_not_rule_objects(self):
        for key, value in [("score", True), ("plagiarism", 30), ("review", False), ("defense", [])]:
            with self.subTest(key=key), self.assertRaises(AppException):
                batches._validate_and_merge_rules(None, {key: value})

    def test_explicit_valid_rules_repair_historical_seed(self):
        old = {"score": True, "review": True, "defense": True, "plagiarism": 30}
        repaired = batches._validate_and_merge_rules(old, batches.DEFAULT_RULES)
        self.assertEqual(repaired, batches.DEFAULT_RULES)
        self.assertIs(old["score"], True)

    def test_numeric_weights_still_must_sum_to_100_percent(self):
        with self.assertRaises(AppException):
            batches._validate_and_merge_rules(None, {"score": {"advisorWeight": 0.9}})

    def test_invalid_stored_weight_returns_business_conflict(self):
        for value in (True, False, 30, []):
            db = SimpleNamespace(get=lambda *args: SimpleNamespace(rules_config={"score": value}))
            with self.subTest(value=value), self.assertRaises(AppException):
                grades._weights(db, SimpleNamespace(batch_id=1))

    def test_explicit_valid_weight_is_preserved(self):
        configured = {"advisorWeight": 0.5, "reviewerWeight": 0.2, "defenseWeight": 0.3}
        db = SimpleNamespace(get=lambda *args: SimpleNamespace(rules_config={"score": configured}))
        self.assertEqual(grades._weights(db, SimpleNamespace(batch_id=1)), configured)
