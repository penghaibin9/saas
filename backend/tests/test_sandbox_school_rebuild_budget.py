"""20K 数据重建资源预算解析器合同；纯单元测试。"""
from scripts.check_sandbox_20k_rebuild_budget import parse_budget, parse_elapsed


def test_parse_elapsed_supports_minute_and_hour_formats():
    assert parse_elapsed("1:05.50") == 65.5
    assert parse_elapsed("1:02:03.25") == 3723.25


def test_parse_budget_reads_gnu_time_verbose_output():
    metrics = parse_budget("""
        Elapsed (wall clock) time (h:mm:ss or m:ss): 1:17.20
        Maximum resident set size (kbytes): 314572
    """)
    assert metrics == {"elapsedSeconds": 77.2, "maxRssMiB": 307.19921875}
