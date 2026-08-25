from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pymysql


def conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "e2e_root"),
        database=os.getenv("DB_NAME", "student_lifecycle_e2e"),
        charset="utf8mb4",
    )


def verify_config() -> None:
    evidence = json.loads(Path("../e2e/student-affairs-scholarship-config-v3-evidence.json").read_text(encoding="utf-8"))
    project_id = int(evidence["projectId"])
    batch_id = int(evidence["batchId"])
    db = conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT project_type, project_name, amount, quota, status FROM t_affairs_funding_project WHERE id=%s",
                (project_id,),
            )
            project = cur.fetchone()
            print("[PROJECT]", project)
            assert project
            assert project[0] == "SCHOLARSHIP"
            assert project[1] == evidence["projectName"]
            assert str(project[2]) == "3000.00"
            assert int(project[3]) == 1
            assert project[4] == "ENABLED"

            cur.execute(
                "SELECT project_id, project_type, year_code, publicity_days, quota, status FROM t_affairs_funding_batch WHERE id=%s",
                (batch_id,),
            )
            batch = cur.fetchone()
            print("[BATCH]", batch)
            assert batch
            assert int(batch[0]) == project_id
            assert batch[1] == "SCHOLARSHIP"
            assert batch[2] == evidence["schoolYear"]
            assert int(batch[3]) == 1
            assert int(batch[4]) == 1
            assert batch[5] == "OPEN"
    finally:
        db.close()
    assert evidence["exactHead"] == os.environ["E2E_TARGET_SHA"]
    assert evidence["result"] == "REAL_PASS"
    print("[RESULT] REAL_PASS SA-004 configuration Browser First")


def verify_journey() -> None:
    evidence = json.loads(Path("../e2e/student-affairs-scholarship-audit-evidence.json").read_text(encoding="utf-8"))
    app_id = int(evidence["applicationId"])
    appeal_id = int(evidence["appealId"])
    batch_id = int(evidence["batchId"])
    db = conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT student_id, project_type, status, statement, check_snapshot_json,
                          approved_amount, quota_reserved, publicity_at, version
                   FROM t_affairs_funding_application WHERE id=%s""",
                (app_id,),
            )
            app = cur.fetchone()
            print("[APPLICATION]", app)
            assert app
            student_id = int(app[0])
            assert app[1] == "SCHOLARSHIP"
            assert app[2] == "PUBLICITY"
            assert app[3] == evidence["revisedStatement"]
            snapshot = json.loads(app[4] or "{}")
            assert snapshot.get("type") == "SCHOLARSHIP"
            assert snapshot.get("ok") is True
            assert snapshot.get("ruleVersion")
            assert snapshot.get("evaluatedAt")
            assert app[5] is None
            assert bool(app[6]) is False
            assert app[7] is not None

            cur.execute(
                "SELECT publicity_days, UTC_TIMESTAMP(), DATE_ADD(%s, INTERVAL publicity_days DAY) FROM t_affairs_funding_batch WHERE id=%s",
                (app[7], batch_id),
            )
            time_gate = cur.fetchone()
            print("[TIME_GATE]", time_gate)
            assert time_gate
            assert int(time_gate[0]) >= 1
            assert time_gate[2] > time_gate[1]

            cur.execute(
                "SELECT status, result, reason, review_opinion, open_key FROM t_affairs_funding_appeal WHERE id=%s",
                (appeal_id,),
            )
            appeal = cur.fetchone()
            print("[APPEAL]", appeal)
            assert appeal
            assert appeal[0] == "CLOSED"
            assert appeal[1] == "OVERRULED"
            assert appeal[2] == evidence["appealReason"]
            assert appeal[3] == evidence["appealOpinion"]
            assert appeal[4] is None

            cur.execute(
                "SELECT COUNT(*) FROM t_student_stage_event WHERE student_id=%s AND to_stage='FUNDING_GRANTED' AND source_module='student-affairs'",
                (student_id,),
            )
            assert int(cur.fetchone()[0]) == 0

            cur.execute(
                "SELECT action FROM t_affairs_audit_trail WHERE biz_type='FUNDING' AND biz_id=%s ORDER BY id",
                (app_id,),
            )
            actions = [str(row[0]).upper() for row in cur.fetchall()]
            print("[AUDIT]", actions)
            required = {
                "APPLY",
                "RETURNED",
                "STUDENT_EDIT_RETURNED",
                "STUDENT_RESUBMIT",
                "TO_PUBLICITY",
                "FUNDING_APPEAL_SUBMIT",
                "FUNDING_APPEAL_REVIEW",
            }
            assert required.issubset(set(actions)), (required - set(actions), actions)
            assert "GRANTED" not in actions
    finally:
        db.close()
    assert evidence.get("exactHead") == os.environ["E2E_TARGET_SHA"]
    print("[RESULT] TIME_GATED_PRECHECK_PASS SA-004 scholarship journey")
    print("[RESULT] TIME_GATED_WAITING real publicity period remains unchanged")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["config", "journey"])
    args = parser.parse_args()
    if args.mode == "config":
        verify_config()
    else:
        verify_journey()


if __name__ == "__main__":
    main()
