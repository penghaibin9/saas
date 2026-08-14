"""20K 数据重建资源预算解析器合同；纯单元测试。"""
from pathlib import Path

from scripts.check_sandbox_20k_rebuild_budget import parse_budget, parse_elapsed


ROOT = Path(__file__).resolve().parents[2]


def test_parse_elapsed_supports_minute_and_hour_formats():
    assert parse_elapsed("1:05.50") == 65.5
    assert parse_elapsed("1:02:03.25") == 3723.25


def test_parse_budget_reads_gnu_time_verbose_output():
    metrics = parse_budget("""
        Elapsed (wall clock) time (h:mm:ss or m:ss): 1:17.20
        Maximum resident set size (kbytes): 314572
    """)
    assert metrics == {"elapsedSeconds": 77.2, "maxRssMiB": 307.19921875}


def test_acceptance_budget_keeps_measured_rss_and_limit_separate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "test-results/sandbox-20k/rebuild.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        """
        Elapsed (wall clock) time (h:mm:ss or m:ss): 1:17.20
        Maximum resident set size (kbytes): 314572
        """,
        encoding="utf-8",
    )

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
