#!/usr/bin/env python3
"""换钥后的重加密任务：把所有 `*_encrypted` 列刷成当前密钥版本。

换钥完整流程（缺一步就会解不开历史数据）：

1. 生成新密钥：`python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`
2. 把**旧**密钥写进 FIELD_ENCRYPTION_PREVIOUS_KEYS，格式 `旧版本号:旧密钥`
3. 把**新**密钥写进 FIELD_ENCRYPTION_KEY，FIELD_ENCRYPTION_KEY_ID 递增
4. 重启服务（此时新写入用新钥，历史密文仍能用旧钥解开）
5. 跑本脚本：先 `--dry-run` 看清有多少行、有没有解不开的，再实跑
6. `--dry-run` 显示 legacy/旧版本行数归零后，才可以从配置里移除旧密钥

用法：
    python scripts/rewrap_encrypted_fields.py --dry-run
    python scripts/rewrap_encrypted_fields.py --batch-size 500

注意：本脚本只改密文列，不改业务语义；SENSITIVE_SEARCH_HMAC_KEY 不在此处理
（检索哈希与加密密钥解耦，换它需要整表重算检索列，属于另一件事）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core import field_crypto as fc  # noqa: E402


def _encrypted_columns():
    """扫描 ORM，列出所有 `*_encrypted` 列。"""
    from app.db.base import metadata
    for table in metadata.sorted_tables:
        cols = [c.name for c in table.columns if c.name.endswith("_encrypted")]
        if cols:
            yield table, cols


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    from app.db.session import get_sessionmaker

    status = fc.key_rotation_status()
    current_kid = status["currentKeyId"]
    print(f"当前密钥版本 = {current_kid}；可用历史版本 = {status['previousKeyIds'] or '无'}")

    totals = {"scanned": 0, "rewrapped": 0, "already_current": 0, "undecryptable": 0}
    failures: list[str] = []
    db = get_sessionmaker()()
    try:
        for table, cols in _encrypted_columns():
            pk = list(table.primary_key.columns)
            if not pk:
                print(f"跳过 {table.name}（无主键，无法定位行）")
                continue
            pk_col = pk[0]
            rows = db.execute(select(pk_col, *[table.c[c] for c in cols])).all()
            for row in rows:
                row_id, values = row[0], row[1:]
                updates = {}
                for col_name, stored in zip(cols, values):
                    if not stored:
                        continue
                    totals["scanned"] += 1
                    kid, _ = fc.split_key_id(str(stored))
                    if kid == current_kid:
                        totals["already_current"] += 1
                        continue
                    try:
                        updates[col_name] = fc.rewrap(stored)
                        totals["rewrapped"] += 1
                    except ValueError as exc:
                        totals["undecryptable"] += 1
                        failures.append(f"{table.name}.{col_name} id={row_id}: {exc}")
                if updates and not args.dry_run:
                    db.execute(table.update().where(pk_col == row_id).values(**updates))
            if not args.dry_run:
                db.commit()
    finally:
        db.close()

    print(f"\n扫描密文 {totals['scanned']} 条："
          f"已是当前版本 {totals['already_current']}，"
          f"{'待重加密' if args.dry_run else '已重加密'} {totals['rewrapped']}，"
          f"解不开 {totals['undecryptable']}")
    if failures:
        print("\n以下密文用任何已知密钥都解不开——先把对应旧密钥补进 "
              "FIELD_ENCRYPTION_PREVIOUS_KEYS，不要在这个状态下移除旧钥：")
        for line in failures[:50]:
            print(f"  - {line}")
        if len(failures) > 50:
            print(f"  ...（另有 {len(failures) - 50} 条）")
        return 1
    if args.dry_run and totals["rewrapped"]:
        print("\n（dry-run：以上为将要重加密的行数，未写库）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
