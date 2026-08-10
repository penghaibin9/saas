#!/usr/bin/env python
"""比对两条安装路径产出的库结构，不一致即判 FAIL。

为什么需要这条门禁（P0）：

`0001_init_core_tables` 不是冻结的历史 DDL，它执行的是
`from app.db.base import metadata; metadata.create_all(bind)` ——
也就是"用**今天**的 ORM 建表"。于是：

- 2026-07 装的学校：跑 0001（当时的 ORM）+ 0002..N 逐个升级；
- 今天新装的学校：跑 0001（今天的 ORM，已经把后续迁移要加的列全建好了）+ 0002..N。

两条路径的终点**理论上可能不同**，而且后续迁移里已经出现
"表已存在就直接 return" 的兼容写法，会把差异继续掩盖起来。

本脚本不修复这个设计，但让它**不可能悄悄发生**：CI 用一个历史基线 commit 建库、
一路升到 HEAD，再和"全新库直接升到 HEAD"逐字段比对，不一致就红。

用法：
    python scripts/check/compare-schema-dumps.py --upgraded upgraded.txt --fresh fresh.txt
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upgraded", type=Path, required=True,
                        help="老库一路 upgrade 到 HEAD 后的结构")
    parser.add_argument("--fresh", type=Path, required=True,
                        help="全新库直接 upgrade head 后的结构")
    args = parser.parse_args()

    upgraded = args.upgraded.read_text(encoding="utf-8").splitlines()
    fresh = args.fresh.read_text(encoding="utf-8").splitlines()

    if upgraded == fresh:
        print("迁移路径收敛 OK：老库升级结果与全新安装结果完全一致")
        return 0

    diff = list(difflib.unified_diff(
        upgraded, fresh, fromfile="老库一路升级", tofile="全新安装", lineterm=""))
    print("迁移路径未收敛：同一个 HEAD，两种安装方式产出的库结构不同。")
    print("这意味着老学校和新学校跑在不同的表结构上——必须先修迁移，不得发版。\n")
    for line in diff[:400]:
        print(line)
    if len(diff) > 400:
        print(f"...（另有 {len(diff) - 400} 行差异）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
