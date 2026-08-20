"""校验 20K 沙箱全量重建的 Runner 资源预算。

解析 /usr/bin/time -v 输出。门槛不是生产接口 SLA，而是防止数据生成器把大表全部物化到 Python：
- wall clock 目标 <= 150 秒；GitHub hosted runner 仅允许 5% 调度/资源抖动带；
- maximum RSS <= 700 MiB。

专业化前真实基线约 45 秒 / 232 MiB；曾出现的 ORM 全量成绩改名约 197 秒 / 1.1 GiB，
本门禁专门阻止这类规模回退重新混入。
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

MAX_SECONDS = 150.0
MAX_RSS_MIB = 700.0
GITHUB_RUNNER_JITTER_RATIO = 0.05


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


def runner_jitter_ratio() -> float:
    """只给 GitHub hosted Actions 一个小的 wall-clock 抖动带；本地/自托管保持 150s 硬目标。"""
    return GITHUB_RUNNER_JITTER_RATIO if os.getenv("GITHUB_ACTIONS") == "true" else 0.0


def check_budget(log_path: Path, *, max_seconds: float = MAX_SECONDS,
                 max_rss_mib: float = MAX_RSS_MIB,
                 wall_clock_jitter_ratio: float | None = None) -> dict[str, float]:
    metrics = parse_budget(log_path.read_text(encoding="utf-8", errors="replace"))
    if wall_clock_jitter_ratio is None:
        wall_clock_jitter_ratio = runner_jitter_ratio()
    if not 0.0 <= wall_clock_jitter_ratio <= 0.10:
        raise ValueError("wall_clock_jitter_ratio 必须位于 0.0~0.10")
    hard_max_seconds = max_seconds * (1.0 + wall_clock_jitter_ratio)

    failures = []
    if metrics["elapsedSeconds"] > hard_max_seconds:
        failures.append(
            "重建耗时 {:.2f}s > {:.2f}s（目标 {:.2f}s + {:.0%} runner 抖动带）".format(
                metrics["elapsedSeconds"], hard_max_seconds, max_seconds, wall_clock_jitter_ratio
            )
        )
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
    jitter_ratio = runner_jitter_ratio()
    hard_max_seconds = args.max_seconds * (1.0 + jitter_ratio)
    try:
        metrics = check_budget(
            args.log,
            max_seconds=args.max_seconds,
            max_rss_mib=args.max_rss_mib,
            wall_clock_jitter_ratio=jitter_ratio,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"[20k-budget] FAIL {exc}")
        return 1
    print(
        "[20k-budget] PASS elapsed={:.2f}s <= {:.2f}s hard ceiling "
        "(target {:.2f}s + {:.0%} runner jitter), maxRSS={:.2f}MiB <= {:.2f}MiB".format(
            metrics["elapsedSeconds"], hard_max_seconds, args.max_seconds, jitter_ratio,
            metrics["maxRssMiB"], args.max_rss_mib,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
