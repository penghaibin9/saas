#!/usr/bin/env python3
"""岗位实习 · 历史脏数据只读扫描 + 可选 dry-run 修复台账（默认不写库）。

用法（在 backend 目录，需 MySQL）：
  python -m scripts.internship_batch_null_scan
  python -m scripts.internship_batch_null_scan --tenant-id 1000000000000000001
  python -m scripts.internship_batch_null_scan --export-xlsx /tmp/internship_null_batch.xlsx

禁止：
  - 自动按日期/专业/最新批次猜测归属
  - 本脚本默认不会执行 UPDATE/DELETE
  - apply 必须显式 --apply 且提供映射 JSON（本轮验收禁止执行 apply）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _scan(db, tenant_id: int | None):
    from sqlalchemy import text

    tid_clause = "AND r.tenant_id = :tid" if tenant_id else ""
    params = {"tid": tenant_id} if tenant_id else {}

    null_rows = db.execute(text(f"""
        SELECT r.id, r.tenant_id, r.student_id, r.status, r.is_deleted
        FROM t_internship_record r
        WHERE r.batch_id IS NULL AND r.is_deleted = 0 {tid_clause}
        ORDER BY r.tenant_id, r.id
        LIMIT 5000
    """), params).mappings().all()

    dup_rows = db.execute(text(f"""
        SELECT r.tenant_id, r.student_id, r.batch_id, COUNT(*) AS cnt,
               GROUP_CONCAT(r.id ORDER BY r.id) AS ids
        FROM t_internship_record r
        WHERE r.is_deleted = 0 AND r.batch_id IS NOT NULL {tid_clause}
        GROUP BY r.tenant_id, r.student_id, r.batch_id
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 2000
    """), params).mappings().all()

    orphan_rows = db.execute(text(f"""
        SELECT r.id, r.tenant_id, r.student_id, r.batch_id, r.status
        FROM t_internship_record r
        LEFT JOIN t_internship_batch b
          ON b.id = r.batch_id AND b.tenant_id = r.tenant_id AND b.is_deleted = 0
        WHERE r.is_deleted = 0 AND r.batch_id IS NOT NULL AND b.id IS NULL {tid_clause}
        ORDER BY r.id
        LIMIT 5000
    """), params).mappings().all()

    deleted_batch_rows = db.execute(text(f"""
        SELECT r.id, r.tenant_id, r.student_id, r.batch_id, b.status AS batch_status
        FROM t_internship_record r
        JOIN t_internship_batch b ON b.id = r.batch_id AND b.tenant_id = r.tenant_id
        WHERE r.is_deleted = 0 AND b.is_deleted = 1 {tid_clause}
        LIMIT 5000
    """), params).mappings().all()

    illegal_status = db.execute(text(f"""
        SELECT r.id, r.tenant_id, r.student_id, r.batch_id, r.status AS rec_status, b.status AS batch_status
        FROM t_internship_record r
        JOIN t_internship_batch b ON b.id = r.batch_id AND b.tenant_id = r.tenant_id AND b.is_deleted = 0
        WHERE r.is_deleted = 0
          AND b.status IN ('VOIDED', 'ARCHIVED')
          AND r.status IN ('PREPARING', 'READY', 'ONBOARD')
          {tid_clause}
        LIMIT 5000
    """), params).mappings().all()

    return {
        "nullBatchCount": len(null_rows),
        "nullBatchIds": [int(r["id"]) for r in null_rows],
        "duplicateCount": len(dup_rows),
        "duplicates": [dict(r) for r in dup_rows],
        "orphanBatchCount": len(orphan_rows),
        "orphanIds": [int(r["id"]) for r in orphan_rows],
        "deletedBatchLinkCount": len(deleted_batch_rows),
        "illegalStatusCount": len(illegal_status),
        "illegalStatusIds": [int(r["id"]) for r in illegal_status],
        "wroteData": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="岗位实习 batch_id 脏数据只读扫描")
    parser.add_argument("--tenant-id", type=int, default=None)
    parser.add_argument("--export-xlsx", type=str, default="")
    parser.add_argument("--apply", action="store_true",
                        help="危险：按映射写库。本轮验收禁止使用。")
    parser.add_argument("--mapping-json", type=str, default="",
                        help='形如 {"recordId": batchId} 的人工映射文件')
    args = parser.parse_args(argv)

    if args.apply:
        print("REFUSE: 本轮禁止对真实数据执行 apply。请人工确认映射后再单独执行。", file=sys.stderr)
        return 2

    # 延迟导入，保证脚本在无 DB 时也能提示
    try:
        from app.db.session import get_sessionmaker
    except Exception as e:  # noqa: BLE001
        print(f"未执行真实扫描：无法导入数据库会话（{e}）")
        return 1

    Session = get_sessionmaker()
    db = Session()
    try:
        result = _scan(db, args.tenant_id)
    except Exception as e:  # noqa: BLE001
        print(f"未执行真实扫描：数据库不可用或查询失败（{e}）")
        return 1
    finally:
        db.close()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    if args.export_xlsx:
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "null_batch"
            ws.append(["recordId"])
            for i in result["nullBatchIds"]:
                ws.append([i])
            ws2 = wb.create_sheet("duplicates")
            ws2.append(["tenantId", "studentId", "batchId", "cnt", "ids"])
            for d in result["duplicates"]:
                ws2.append([d.get("tenant_id"), d.get("student_id"), d.get("batch_id"),
                            d.get("cnt"), d.get("ids")])
            path = Path(args.export_xlsx)
            path.parent.mkdir(parents=True, exist_ok=True)
            wb.save(path)
            print(f"台账已写出（仅清单，无写库）: {path}")
        except Exception as e:  # noqa: BLE001
            print(f"导出 xlsx 失败: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
