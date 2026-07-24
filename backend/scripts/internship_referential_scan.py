#!/usr/bin/env python3
"""Read-only referential-integrity scan for internship records and positions."""
from __future__ import annotations

import argparse
import json


def _scan(db, tenant_id=None, sample_limit=100):
    from sqlalchemy import text
    clause = "AND r.tenant_id = :tid" if tenant_id else ""
    params = {"tid": tenant_id} if tenant_id else {}

    def issue(name, count_sql, sample_sql):
        total = int(db.execute(text(count_sql), params).scalar() or 0)
        samples = [dict(x) for x in db.execute(text(sample_sql + f" LIMIT {sample_limit}"), params).mappings()]
        return {name: {"totalCount": total, "sampleCount": len(samples),
                       "hasMore": total > len(samples), "samples": samples}}

    result = {"wroteData": False}
    result.update(issue("orphanBatch", f"""SELECT COUNT(*) FROM t_internship_record r
        LEFT JOIN t_internship_batch b ON b.id=r.batch_id AND b.tenant_id=r.tenant_id AND b.is_deleted=0
        WHERE r.is_deleted=0 AND r.batch_id IS NOT NULL AND b.id IS NULL {clause}""", f"""SELECT r.id,r.tenant_id,r.batch_id
        FROM t_internship_record r LEFT JOIN t_internship_batch b ON b.id=r.batch_id AND b.tenant_id=r.tenant_id AND b.is_deleted=0
        WHERE r.is_deleted=0 AND r.batch_id IS NOT NULL AND b.id IS NULL {clause} ORDER BY r.id"""))
    result.update(issue("orphanPosition", f"""SELECT COUNT(*) FROM t_internship_record r
        LEFT JOIN t_internship_position p ON p.id=r.position_id AND p.tenant_id=r.tenant_id AND p.is_deleted=0
        WHERE r.is_deleted=0 AND r.position_id IS NOT NULL AND p.id IS NULL {clause}""", f"""SELECT r.id,r.tenant_id,r.position_id
        FROM t_internship_record r LEFT JOIN t_internship_position p ON p.id=r.position_id AND p.tenant_id=r.tenant_id AND p.is_deleted=0
        WHERE r.is_deleted=0 AND r.position_id IS NOT NULL AND p.id IS NULL {clause} ORDER BY r.id"""))
    pos_clause = "AND p.tenant_id = :tid" if tenant_id else ""
    result.update(issue("allocationMismatch", f"""SELECT COUNT(*) FROM (
        SELECT p.id FROM t_internship_position p LEFT JOIN t_internship_record r
        ON r.position_id=p.id AND r.tenant_id=p.tenant_id AND r.is_deleted=0
        WHERE p.is_deleted=0 {pos_clause} GROUP BY p.id,p.allocated_count
        HAVING p.allocated_count<>COUNT(r.id)) AS mismatches""", f"""SELECT p.id,p.tenant_id,p.allocated_count,COUNT(r.id) AS record_count
        FROM t_internship_position p LEFT JOIN t_internship_record r ON r.position_id=p.id AND r.tenant_id=p.tenant_id AND r.is_deleted=0
        WHERE p.is_deleted=0 {pos_clause} GROUP BY p.id,p.allocated_count HAVING p.allocated_count<>COUNT(r.id) ORDER BY p.id"""))
    result.update(issue("invalidAllocation", f"""SELECT COUNT(*) FROM t_internship_position p
        WHERE p.is_deleted=0 {pos_clause} AND (p.allocated_count<0 OR p.allocated_count>p.headcount)""", f"""SELECT p.id,p.tenant_id,p.allocated_count,p.headcount FROM t_internship_position p
        WHERE p.is_deleted=0 {pos_clause} AND (p.allocated_count<0 OR p.allocated_count>p.headcount) ORDER BY p.id"""))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="岗位实习引用完整性只读扫描")
    parser.add_argument("--tenant-id", type=int)
    args = parser.parse_args(argv)
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        print(json.dumps(_scan(db, args.tenant_id), ensure_ascii=False, indent=2, default=str))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
