"""Create read-only MySQL truth seals for the eight Graduation V8 journeys.

The script is deliberately restricted to a ``graduation_v8_*`` database.  It
does not seed, update, or delete data; every statement is a SELECT used to bind
browser evidence to authoritative rows and cross-row invariants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymysql


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def _canonical(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_value).encode("utf-8")


def _snapshot(cursor, sql: str, params: tuple[Any, ...]) -> dict[str, Any]:
    cursor.execute(sql, params)
    rows = [{key: _json_value(value) for key, value in row.items()} for row in cursor.fetchall()]
    return {
        "rowCount": len(rows),
        "sha256": hashlib.sha256(_canonical(rows)).hexdigest(),
        "rows": rows[:20],
        "truncated": len(rows) > 20,
    }


def _git_head(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def _queries(batch_id: int) -> dict[str, dict[str, str]]:
    students = "SELECT id FROM t_gd_student WHERE batch_id=%s AND is_deleted=0"
    return {
        "GDJ-01": {
            "batch": "SELECT id,batch_no,status,archive_status,version FROM t_gd_batch WHERE id=%s AND is_deleted=0",
            "students": "SELECT id,student_no,batch_id,mentor_id,topic_id,record_status,eligibility_status,version FROM t_gd_student WHERE batch_id=%s AND is_deleted=0 ORDER BY id",
            "mentorAssignments": f"SELECT gd_student_id,mentor_id,status,confirmed_by_mentor,version FROM t_gd_mentor_assignment WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
        },
        "GDJ-02": {
            "topics": "SELECT id,batch_id,capacity,selected,review_status,status,version FROM t_gd_topic WHERE batch_id=%s AND is_deleted=0 ORDER BY id",
            "choices": f"SELECT gd_student_id,topic_id,choice_order,status,submission_version,version FROM t_gd_topic_choice WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "topicChanges": f"SELECT gd_student_id,old_topic_id,new_topic_id,status,version FROM t_gd_topic_change_request WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
        },
        "GDJ-03": {
            "taskbooks": f"SELECT gd_student_id,mentor_id,taskbook_version,status,confirmed_at,version FROM t_gd_task_book WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "proposals": f"SELECT gd_student_id,version AS proposal_version,is_resubmit,status,active_key,review_time FROM t_gd_proposal WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "proposalReviews": f"SELECT id,gd_student_id,status,reviewer,review_comment,review_time,version AS proposal_version FROM t_gd_proposal WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
        },
        "GDJ-04": {
            "guidance": f"SELECT gd_student_id,mentor_id,guidance_date,method,version FROM t_gd_guidance WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "midterms": f"SELECT gd_student_id,batch_id,status,conclusion,rectify_attempts,version FROM t_gd_midterm WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "risks": f"SELECT gd_student_id,risk_code,level,status,condition_active,reopen_count,version FROM t_gd_risk_case WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
        },
        "GDJ-05": {
            "finals": f"SELECT id,gd_student_id,final_type,version AS final_version,status,plagiarism_status FROM t_gd_final WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "plagiarism": f"SELECT gd_student_id,gd_final_id,status,rate,threshold,over_threshold,version FROM t_gd_plagiarism WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "formalReviews": f"SELECT gd_student_id,gd_final_id,reviewer_mentor_id,status,score,file_version_id,source_sha256,version FROM t_gd_review WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "materials": f"SELECT gd_student_id,material_code,business_status,review_status,current_version_id,last_reviewed_version_id,version FROM t_gd_student_material WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
        },
        "GDJ-06": {
            "groups": "SELECT id,batch_id,group_name,defense_date,location,student_count,conflict,published,version FROM t_gd_defense_group WHERE batch_id=%s AND is_deleted=0 ORDER BY id",
            "scores": f"SELECT gd_student_id,defense_group_id,judge_mentor_id,score,absent,round_no,status,version FROM t_gd_defense_score WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "delays": f"SELECT gd_student_id,status,version FROM t_gd_defense_delay WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
        },
        "GDJ-07": {
            "grades": f"SELECT id,gd_student_id,total_score,grade_level,status,source_snapshot_hash,version FROM t_gd_grade WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "appeals": f"SELECT gd_student_id,status,active_key,version FROM t_gd_grade_appeal WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "excellentOutcomes": f"SELECT gd_student_id,status,version FROM t_gd_excellent_outcome WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
        },
        "GDJ-08": {
            "risks": f"SELECT gd_student_id,risk_code,status,condition_active,condition_hash,version FROM t_gd_risk_case WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "materials": f"SELECT gd_student_id,material_code,required_status,business_status,review_status,archive_status,current_version_id,version FROM t_gd_student_material WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "archives": f"SELECT id,gd_student_id,status,archive_batch_no,manifest_hash,version FROM t_gd_archive_record WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
            "archiveVersions": f"SELECT archive_record_id,gd_student_id,archive_version,current_flag,source_manifest_hash,archive_batch_no,version FROM t_gd_archive_version WHERE gd_student_id IN ({students}) AND is_deleted=0 ORDER BY gd_student_id,id",
        },
    }


def _invariants(batch_id: int) -> dict[str, dict[str, str]]:
    students = "SELECT id FROM t_gd_student WHERE batch_id=%s AND is_deleted=0"
    return {
        "GDJ-01": {
            "duplicateActiveMentor": f"SELECT gd_student_id,COUNT(*) AS total FROM t_gd_mentor_assignment WHERE gd_student_id IN ({students}) AND status='ACTIVE' AND is_deleted=0 GROUP BY gd_student_id HAVING COUNT(*)>1",
            "unstableStudentRelation": "SELECT id,student_no FROM t_gd_student WHERE batch_id=%s AND is_deleted=0 AND (record_status<>'ACTIVE' OR eligibility_status<>'QUALIFIED' OR mentor_id IS NULL)",
        },
        "GDJ-02": {
            "topicCapacityOverflow": "SELECT id,selected,capacity FROM t_gd_topic WHERE batch_id=%s AND is_deleted=0 AND (selected<0 OR selected>capacity)",
            "crossBatchChoice": f"SELECT c.id,c.gd_student_id,c.topic_id FROM t_gd_topic_choice c JOIN t_gd_topic t ON t.id=c.topic_id WHERE c.gd_student_id IN ({students}) AND c.is_deleted=0 AND (t.batch_id<>%s OR t.is_deleted<>0)",
        },
        "GDJ-03": {
            "invalidTaskbookVersion": f"SELECT id,gd_student_id FROM t_gd_task_book WHERE gd_student_id IN ({students}) AND is_deleted=0 AND taskbook_version<1",
            "duplicateProposalActiveKey": f"SELECT active_key,COUNT(*) AS total FROM t_gd_proposal WHERE gd_student_id IN ({students}) AND is_deleted=0 AND active_key IS NOT NULL GROUP BY active_key HAVING COUNT(*)>1",
        },
        "GDJ-04": {
            "crossBatchMidterm": f"SELECT m.id,m.gd_student_id,m.batch_id FROM t_gd_midterm m WHERE m.gd_student_id IN ({students}) AND m.is_deleted=0 AND m.batch_id<>%s",
            "closedActiveRisk": f"SELECT id,gd_student_id,risk_code FROM t_gd_risk_case WHERE gd_student_id IN ({students}) AND is_deleted=0 AND status='CLOSED' AND condition_active=1",
        },
        "GDJ-05": {
            "reviewMissingBoundVersion": f"SELECT id,gd_student_id FROM t_gd_review WHERE gd_student_id IN ({students}) AND is_deleted=0 AND status IN ('APPROVED','REJECTED','COMPLETED') AND file_version_id IS NULL",
            "materialVersionMissing": f"SELECT m.id,m.gd_student_id,m.current_version_id FROM t_gd_student_material m LEFT JOIN t_file_version v ON v.id=m.current_version_id AND v.is_deleted=0 WHERE m.gd_student_id IN ({students}) AND m.is_deleted=0 AND m.current_version_id IS NOT NULL AND v.id IS NULL",
        },
        "GDJ-06": {
            "publishedConflict": "SELECT id,group_name,conflict FROM t_gd_defense_group WHERE batch_id=%s AND is_deleted=0 AND published=1 AND COALESCE(conflict,'')<>''",
            "scoreGroupMismatch": f"SELECT s.id,s.gd_student_id,s.defense_group_id FROM t_gd_defense_score s JOIN t_gd_defense_group g ON g.id=s.defense_group_id WHERE s.gd_student_id IN ({students}) AND s.is_deleted=0 AND (g.batch_id<>%s OR g.is_deleted<>0)",
        },
        "GDJ-07": {
            "duplicatePendingAppeal": f"SELECT gd_student_id,COUNT(*) AS total FROM t_gd_grade_appeal WHERE gd_student_id IN ({students}) AND is_deleted=0 AND status='PENDING' GROUP BY gd_student_id HAVING COUNT(*)>1",
            "publishedGradeMissingHash": f"SELECT id,gd_student_id FROM t_gd_grade WHERE gd_student_id IN ({students}) AND is_deleted=0 AND status='PUBLISHED' AND COALESCE(source_snapshot_hash,'')=''",
        },
        "GDJ-08": {
            "duplicateCurrentArchive": f"SELECT gd_student_id,COUNT(*) AS total FROM t_gd_archive_version WHERE gd_student_id IN ({students}) AND is_deleted=0 AND current_flag=1 GROUP BY gd_student_id HAVING COUNT(*)>1",
            "filedArchiveMissingManifest": f"SELECT id,gd_student_id FROM t_gd_archive_record WHERE gd_student_id IN ({students}) AND is_deleted=0 AND status IN ('GENERATED','SUBMITTED','FILED') AND COALESCE(manifest_hash,'')=''",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=43319)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="graduation_v8_e2e")
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.database.startswith("graduation_v8_"):
        raise SystemExit("refusing to inspect a database outside graduation_v8_*")
    password = os.environ.get("MYSQL_PASSWORD")
    if not password:
        raise SystemExit("MYSQL_PASSWORD is required")

    repo = Path(__file__).resolve().parents[2]
    connection = pymysql.connect(
        host=args.host, port=args.port, user=args.user, password=password,
        database=args.database, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        read_timeout=30, write_timeout=30, autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute("SELECT VERSION() AS mysqlVersion, DATABASE() AS databaseName")
            server = {key: _json_value(value) for key, value in cursor.fetchone().items()}
            cursor.execute("SELECT id,batch_no FROM t_gd_batch WHERE id=%s AND is_deleted=0", (args.batch_id,))
            batch = cursor.fetchone()
            if not batch:
                raise SystemExit(f"batch {args.batch_id} does not exist")
            common = {
                "implementationHead": _git_head(repo),
                "generatedAt": datetime.now().astimezone().isoformat(),
                "server": server,
                "batch": {key: _json_value(value) for key, value in batch.items()},
                "readOnly": True,
            }
            results = []
            query_map = _queries(args.batch_id)
            invariant_map = _invariants(args.batch_id)
            for journey in sorted(query_map):
                evidence = {}
                for name, sql in query_map[journey].items():
                    evidence[name] = _snapshot(cursor, sql, (args.batch_id,))
                invariants = {}
                for name, sql in invariant_map[journey].items():
                    parameter_count = sql.count("%s")
                    invariants[name] = _snapshot(cursor, sql, tuple(args.batch_id for _ in range(parameter_count)))
                anomalies = sum(item["rowCount"] for item in invariants.values())
                seal = {**common, "journey": journey, "result": "MYSQL_PASS" if anomalies == 0 else "MYSQL_FAIL", "evidence": evidence, "invariants": invariants, "anomalyCount": anomalies}
                args.output.mkdir(parents=True, exist_ok=True)
                (args.output / f"{journey}-mysql-seal.json").write_text(json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")
                results.append({"journey": journey, "result": seal["result"], "anomalyCount": anomalies})
            aggregate = {**common, "result": "MYSQL_PASS" if all(item["result"] == "MYSQL_PASS" for item in results) else "MYSQL_FAIL", "journeys": results}
            (args.output / "mysql-seals.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(aggregate, ensure_ascii=False, indent=2))
            connection.rollback()
            return 0 if aggregate["result"] == "MYSQL_PASS" else 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
