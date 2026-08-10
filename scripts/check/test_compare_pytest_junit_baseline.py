from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys


def _load():
    path = Path(__file__).with_name("compare-pytest-junit-baseline.py")
    spec = importlib.util.spec_from_file_location("compare_pytest_junit_baseline", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_junit_parser_collects_failure_error_class_and_parameter(tmp_path):
    module = _load()
    report = tmp_path / "report.xml"
    report.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite>
  <testcase classname="tests.test_alpha" name="test_ok" />
  <testcase classname="tests.test_alpha" name="test_failed[param/a]"><failure /></testcase>
  <testcase classname="tests.test_beta.TestScope" name="test_error"><error /></testcase>
</testsuite></testsuites>
""",
        encoding="utf-8",
    )
    assert module.failing_nodeids(report) == {
        "tests/test_alpha.py::test_failed[param/a]",
        "tests/test_beta.py::TestScope::test_error",
    }


def test_compare_revokes_allowance_for_changed_test_file():
    module = _load()
    old = "tests/test_old.py::test_known"
    changed = "tests/test_changed.py::test_known"
    new = "tests/test_new.py::test_regression"
    unexpected, resolved = module.compare(
        {old, changed, new},
        {old, changed},
        {"tests/test_changed.py"},
    )
    assert unexpected == {changed, new}
    assert resolved == set()


def test_baseline_is_read_from_base_ref_not_pr_worktree(tmp_path):
    module = _load()
    baseline = tmp_path / "scripts" / "check" / "backend-known-failures-main.txt"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("tests/test_old.py::test_known\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "ci@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "CI Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=tmp_path, check=True)
    base_ref = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()

    baseline.write_text("tests/test_new.py::test_should_not_be_allowed\n", encoding="utf-8")
    assert module.baseline_from_base_ref(tmp_path, base_ref, baseline) == {
        "tests/test_old.py::test_known"
    }


def test_collection_error_is_compared_as_error(tmp_path):
    module = _load()
    report = tmp_path / "collection.xml"
    report.write_text(
        """<testsuite>
  <testcase classname="" name="tests/test_broken.py"><error message="collection failure" /></testcase>
</testsuite>""",
        encoding="utf-8",
    )
    assert module.failing_nodeids(report) == {"tests/test_broken.py"}


def test_parser_reads_real_pytest_junit_failure_and_error(tmp_path):
    module = _load()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tests_dir / "test_real_junit.py").write_text(
        """import pytest

@pytest.mark.parametrize("value", ["case-a"])
def test_failed(value):
    assert value == "pass"

def test_error(missing_fixture):
    pass
""",
        encoding="utf-8",
    )
    report = tmp_path / "real.xml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-c",
            str(tmp_path / "pytest.ini"),
            "--junitxml",
            str(report),
            str(tests_dir),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert module.failing_nodeids(report) == {
        "tests/test_real_junit.py::test_failed[case-a]",
        "tests/test_real_junit.py::test_error",
    }
