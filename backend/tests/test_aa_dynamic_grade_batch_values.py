"""Pure contract tests; no DB/service imports or fixture dependency when run directly.

Run: python backend/tests/test_aa_dynamic_grade_batch_values.py
The transaction/real-roster tests are specified in the candidate validation plan.
"""
import ast
import math
import re
import unittest
from pathlib import Path
from types import SimpleNamespace


class ContractError(Exception):
    def __init__(self, code, message, **_kwargs):
        super().__init__(message)
        self.code = code


def namespace():
    source = Path(__file__).parents[1] / "app/modules/academic_affairs/services/academic_affairs_dynamic_grade_service.py"
    names = {"normalize_components", "_score", "_conflict", "prepare_component_row", "roster_identity", "require_expected_identity"}
    tree = ast.parse(source.read_text(encoding="utf-8"))
    selected = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
    scope = {"math": math, "re": re, "AppException": ContractError,
             "_CODE_RE": re.compile(r"^[A-Z][A-Z0-9_]{1,39}$"),
             "_ALLOWED_FLAGS": {"NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"}}
    exec(compile(selected, str(source), "exec"), scope)
    return scope


class DynamicValues(unittest.TestCase):
    def setUp(self):
        self.fn = namespace()
        self.scheme = self.fn["normalize_components"]([
            {"code": "PROJECT", "name": "项目", "weight": 70},
            {"code": "LAB", "name": "实训", "weight": 30, "required": False}])

    def test_optional_score_zero_keeps_full_weight(self):
        result = self.fn["prepare_component_row"](self.scheme, {"PROJECT": 80})
        self.assertEqual(result["totalScore"], 56)
        self.assertEqual(result["components"][1]["score"], 0)
        self.assertTrue(result["components"][1]["defaultedToZero"])

    def test_nonfinite_boolean_unknown_and_duplicate_codes_are_rejected(self):
        for value in [True, float("nan"), float("inf"), -1, 101]:
            with self.subTest(value=value), self.assertRaises(ContractError):
                self.fn["prepare_component_row"](self.scheme, {"PROJECT": value})
        for payload in [{"PROJECT": 80, "FINAL": 90}, {"project": 70, "PROJECT": 80}, {}]:
            with self.subTest(payload=payload), self.assertRaises(ContractError):
                self.fn["prepare_component_row"](self.scheme, payload)

    def test_nonfinite_weight_rejected(self):
        with self.assertRaises(ContractError):
            self.fn["normalize_components"]([{"code": "ALL", "name": "全部", "weight": float("nan")}])

    def test_canonical_rounding_and_exception(self):
        result = self.fn["prepare_component_row"](self.scheme, {"PROJECT": 59.995, "LAB": 60.001})
        expected = round(round(round(59.995, 2) * .7, 4) + round(round(60.001, 2) * .3, 4), 2)
        self.assertEqual(result["totalScore"], expected)
        special = self.fn["prepare_component_row"](self.scheme, {}, "ABSENT")
        self.assertIsNone(special["totalScore"])
        self.assertEqual(special["components"], [])

    def test_stale_task_scheme_and_roster_never_match(self):
        task = SimpleNamespace(version=2)
        scheme = SimpleNamespace(id=10, scheme_version=3, is_deleted=False)
        roster = {"source": "SELECTION_LOCK", "teachingClassId": "20", "rosterVersionId": "30",
                  "rosterVersionNo": 2, "rosterHash": "a" * 64, "memberCount": 1, "studentIds": [1]}
        expected = {"expectedTaskVersion": 2, "expectedSchemeId": "10", "expectedSchemeVersion": 3,
                    "rosterIdentity": self.fn["roster_identity"](roster)}
        self.fn["require_expected_identity"](task, scheme, roster, expected)
        for key, value in [("expectedTaskVersion", 1), ("expectedSchemeId", "11"), ("expectedSchemeVersion", 2),
                           ("rosterIdentity", {**expected["rosterIdentity"], "rosterVersionId": "29"})]:
            with self.subTest(key=key), self.assertRaises(ContractError):
                self.fn["require_expected_identity"](task, scheme, roster, {**expected, key: value})


if __name__ == "__main__":
    unittest.main()
