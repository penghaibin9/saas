"""校验 20K 沙箱全量重建的 Runner 资源预算。

解析 /usr/bin/time -v 输出。门槛不是生产接口 SLA，而是防止数据生成器把大表全部物化到 Python：
- wall clock <= 150 秒；
- maximum RSS <= 700 MiB。

专业化前真实基线约 45 秒 / 232 MiB；曾出现的 ORM 全量成绩改名约 197 秒 / 1.1 GiB，
本门禁专门阻止这类规模回退重新混入。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

MAX_SECONDS = 150.0
MAX_RSS_MIB = 700.0


def parse_elapsed(raw: str) -> float:
    parts = raw.strip().split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"unrecognized elapsed format: {raw!r}")


def parse_budget(log_text: str) -> dict[str, float]:
    # GNU time -v 的标签是 "Elapsed (wall clock) time (h:mm:ss or m:ss): 1:17.20"；
    # 必须锚定标签右括号后的最终冒号，不能误吃格式说明里的 h:mm:ss 冒号。
    elapsed_match = re.search(
        r"Elapsed \(wall clock\) time .*?\):\s*([0-9:.]+)",
        log_text,
    )
    rss_match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", log_text)
    if elapsed_match is None or rss_match is None:
        raise ValueError("rebuild.log 缺少 /usr/bin/time -v 的 elapsed 或 max RSS 指标")
    return {
        "elapsedSeconds": parse_elapsed(elapsed_match.group(1)),
        "maxRssMiB": int(rss_match.group(1)) / 1024,
    }


def check_budget(log_path: Path, *, max_seconds: float = MAX_SECONDS,
                 max_rss_mib: float = MAX_RSS_MIB) -> dict[str, float]:
    metrics = parse_budget(log_path.read_text(encoding="utf-8", errors="replace"))
    failures = []
    if metrics["elapsedSeconds"] > max_seconds:
        failures.append(f"重建耗时 {metrics['elapsedSeconds']:.2f}s > {max_seconds:.2f}s")
    if metrics["maxRssMiB"] > max_rss_mib:
        failures.append(f"峰值内存 {metrics['maxRssMiB']:.2f}MiB > {max_rss_mib:.2f}MiB")
    if failures:
        raise RuntimeError("; ".join(failures))
    return metrics


def main() -> int:
    ap = argparse.ArgumentParser(description="检查 20K 沙箱重建资源预算")
    ap.add_argument("log", type=Path)
    ap.add_argument("--max-seconds", type=float, default=MAX_SECONDS)
    ap.add_argument("--max-rss-mib", type=float, default=MAX_RSS_MIB)
    args = ap.parse_args()
    try:
        metrics = check_budget(
            args.log,
            max_seconds=args.max_seconds,
            max_rss_mib=args.max_rss_mib,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"[20k-budget] FAIL {exc}")
        return 1
    print(
        "[20k-budget] PASS elapsed={:.2f}s <= {:.2f}s, maxRSS={:.2f}MiB <= {:.2f}MiB".format(
            metrics["elapsedSeconds"], args.max_seconds,
            metrics["maxRssMiB"], args.max_rss_mib,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
