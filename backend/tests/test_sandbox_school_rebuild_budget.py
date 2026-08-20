"""20K 数据重建资源预算解析器合同；纯单元测试。"""
from pathlib import Path

import pytest

from scripts.check_sandbox_20k_rebuild_budget import check_budget, parse_budget, parse_elapsed


ROOT = Path(__file__).resolve().parents[2]


def _write_budget_log(path: Path, *, elapsed: str, rss_kib: int = 314572) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
        Elapsed (wall clock) time (h:mm:ss or m:ss): {elapsed}
        Maximum resident set size (kbytes): {rss_kib}
        """,
        encoding="utf-8",
    )
    return path


def test_parse_elapsed_supports_minute_and_hour_formats():
    assert parse_elapsed("1:05.50") == 65.5
    assert parse_elapsed("1:02:03.25") == 3723.25


def test_parse_budget_reads_gnu_time_verbose_output():
    metrics = parse_budget("""
        Elapsed (wall clock) time (h:mm:ss or m:ss): 1:17.20
        Maximum resident set size (kbytes): 314572
    """)
    assert metrics == {"elapsedSeconds": 77.2, "maxRssMiB": 307.19921875}


def test_github_runner_jitter_accepts_small_wall_clock_variance(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    log_path = _write_budget_log(tmp_path / "rebuild.log", elapsed="2:34.84")

    metrics = check_budget(log_path)

    assert metrics["elapsedSeconds"] == 154.84


def test_github_runner_jitter_still_rejects_historical_scale_regression(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    log_path = _write_budget_log(tmp_path / "rebuild.log", elapsed="3:17.00")

    with pytest.raises(RuntimeError, match="重建耗时"):
        check_budget(log_path)


def test_non_github_execution_keeps_150_second_hard_target(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    log_path = _write_budget_log(tmp_path / "rebuild.log", elapsed="2:30.10")

    with pytest.raises(RuntimeError, match="目标 150.00s"):
        check_budget(log_path)


def test_acceptance_budget_keeps_measured_rss_and_limit_separate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "test-results/sandbox-20k/rebuild.log"
    _write_budget_log(log_path, elapsed="1:17.20")

    from scripts.check_sandbox_20k_school import _rebuild_budget_audit

    report = _rebuild_budget_audit()
    assert report is not None
    assert report["elapsedSeconds"] == 77.2
    assert report["maxRssMiB"] == 307.19921875
    assert report["maxSeconds"] == 150.0
    assert report["maxRssLimitMiB"] == 700.0


def test_grade_snapshot_debt_stays_sql_bounded_at_school_scale():
    source = (
        ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_effective_grade_policy_service.py"
    ).read_text(encoding="utf-8")
    body = source.split("def policy_snapshot_debt", 1)[1].split("\ndef _policy_dto", 1)[0]

    assert "grades = query.all()" not in body
    assert "grade_ids = [int(row.id) for row in grades]" not in body
    assert "snapshot_exists" in body
    assert "~snapshot_exists" in body
    assert "func.count(AcademicGrade.id)" in body
    assert "func.trim(func.coalesce(AcademicGrade.course_code" in body
    assert ".limit(50).all()" in body
