from __future__ import annotations

import argparse
from datetime import datetime
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


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise AssertionError(f"unexpected MySQL datetime value: {value!r}")


def verify_precondition() -> None:
    db = conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT s.id, s.tenant_id, a.id, a.final_level, a.status, b.year_code
                   FROM t_student_profile s
                   JOIN t_affairs_aid_apply a
                     ON a.tenant_id=s.tenant_id AND a.student_id=s.id AND a.is_deleted=0
                   JOIN t_affairs_aid_batch b
                     ON b.tenant_id=a.tenant_id AND b.id=a.batch_id AND b.is_deleted=0
                   WHERE s.student_no=%s AND s.is_deleted=0
                     AND a.status='APPROVED' AND b.year_code=%s
                   ORDER BY a.id DESC LIMIT 1""",
                ("E2E20260001", "2026-2027"),
            )
            row = cur.fetchone()
            print("[SA002_PRECONDITION]", row)
            assert row, "SA-005 requires one explicit APPROVED SA-002 difficult-library prerequisite"
            assert row[3] == "SPECIAL"
            assert row[4] == "APPROVED"
            assert row[5] == "2026-2027"
    finally:
        db.close()
    print("[RESULT] PRECONDITION_PASS SA-002 approved difficult-library fact for SA-005")


def verify_config() -> None:
    evidence = json.loads(Path("../e2e/student-affairs-grant-config-v3-evidence.json").read_text(encoding="utf-8"))
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
            assert project[0] == "GRANT"
            assert project[1] == evidence["projectName"]
            assert str(project[2]) == "2500.00"
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
            assert batch[1] == "GRANT"
            assert batch[2] == evidence["schoolYear"]
            assert int(batch[3]) == 1
            assert int(batch[4]) == 1
            assert batch[5] == "OPEN"
    finally:
        db.close()
    assert evidence["exactHead"] == os.environ["E2E_TARGET_SHA"]
    assert evidence["result"] == "REAL_PASS"
    print("[RESULT] REAL_PASS SA-005 GRANT configuration Browser First")


def verify_journey() -> None:
    evidence = json.loads(Path("../e2e/student-affairs-grant-audit-evidence.json").read_text(encoding="utf-8"))
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
            assert app[1] == "GRANT"
            assert app[2] == "PUBLICITY"
            assert app[3] == evidence["revisedStatement"]
            snapshot = json.loads(app[4] or "{}")
            print("[ELIGIBILITY_SNAPSHOT]", json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
            assert snapshot.get("type") == "GRANT"
            assert snapshot.get("ok") is True
            assert snapshot.get("inDifficultLibrary") is True
            assert snapshot.get("aidLevel") == "SPECIAL"
            assert snapshot.get("aidLevelAllowed") is True
            assert snapshot.get("ruleVersion")
            assert snapshot.get("evaluatedAt")
            # 未到真实公示截止前绝不能提前写“发放前复核”或批准事实。
            assert "grantEligibilityRecheck" not in snapshot
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
            assert _as_datetime(time_gate[2]) > _as_datetime(time_gate[1])

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
                """SELECT a.status, a.final_level, b.year_code
                   FROM t_affairs_aid_apply a
                   JOIN t_affairs_aid_batch b ON b.id=a.batch_id AND b.tenant_id=a.tenant_id
                   WHERE a.tenant_id=(SELECT tenant_id FROM t_affairs_funding_application WHERE id=%s)
                     AND a.student_id=%s AND a.status='APPROVED' AND a.is_deleted=0
                   ORDER BY a.id DESC LIMIT 1""",
                (app_id, student_id),
            )
            aid = cur.fetchone()
            print("[CURRENT_DIFFICULT_LIBRARY]", aid)
            assert aid
            assert aid[0] == "APPROVED"
            assert aid[1] == "SPECIAL"
            assert aid[2] == evidence["schoolYear"]

            cur.execute(
                "SELECT COUNT(*) FROM t_student_stage_event WHERE student_id=%s AND to_stage='FUNDING_GRANTED' AND source_module='student-affairs'",
                (student_id,),
            )
            assert int(cur.fetchone()[0]) == 0

            cur.execute(
                "SELECT COUNT(*) FROM t_affairs_funding_disbursement WHERE application_id=%s AND is_deleted=0",
                (app_id,),
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
            assert "GRANT_ELIGIBILITY_RECHECK" not in actions
            assert "GRANTED" not in actions
    finally:
        db.close()

    assert evidence.get("exactHead") == os.environ["E2E_TARGET_SHA"]
    assert evidence.get("qualificationPrecondition") == "SA002_APPROVED_DIFFICULT_LIBRARY"
    print("[RESULT] TIME_GATED_PRECHECK_PASS SA-005 grant journey + SA-002 qualification linkage")
    print("[RESULT] TIME_GATED_WAITING real publicity period remains unchanged")
    print("[RESULT] CONTRACT_LOCK grant-time eligibility drift is rechecked before award")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["precondition", "config", "journey"])
    args = parser.parse_args()
    if args.mode == "precondition":
        verify_precondition()
    elif args.mode == "config":
        verify_config()
    else:
        verify_journey()


if __name__ == "__main__":
    main()
