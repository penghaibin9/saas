from __future__ import annotations

import argparse
from datetime import datetime, timedelta
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


def _dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise AssertionError(f"unexpected datetime: {value!r}")


def _load():
    root = Path("../e2e")
    evidence = json.loads((root / "student-affairs-grant-audit-evidence.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "student-affairs-sa005-time-gate-manifest.json").read_text(encoding="utf-8"))
    return root, evidence, manifest


def preflight() -> None:
    _, evidence, manifest = _load()
    assert evidence.get("exactHead") == os.environ["E2E_TARGET_SHA"]
    assert manifest.get("productSha") == os.environ["E2E_TARGET_SHA"]
    assert evidence.get("qualificationPrecondition") == "SA002_APPROVED_DIFFICULT_LIBRARY"
    app_id = int(manifest["applicationId"])
    batch_id = int(manifest["batchId"])
    appeal_id = int(manifest["appealId"])

    db = conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT student_id, project_type, status, check_snapshot_json,
                          publicity_at, version, workflow_instance_id
                   FROM t_affairs_funding_application WHERE id=%s""",
                (app_id,),
            )
            app = cur.fetchone()
            print("[PRE_APPLICATION]", app)
            assert app
            student_id = int(app[0])
            assert app[1] == "GRANT"
            assert app[2] == "PUBLICITY"
            snapshot = json.loads(app[3] or "{}")
            assert snapshot.get("type") == "GRANT"
            assert snapshot.get("ok") is True
            assert snapshot.get("inDifficultLibrary") is True
            assert snapshot.get("aidLevel") == "SPECIAL"
            assert "grantEligibilityRecheck" not in snapshot
            assert int(app[5]) == int(manifest["preVersion"])
            assert app[4] is not None

            cur.execute("SELECT publicity_days FROM t_affairs_funding_batch WHERE id=%s", (batch_id,))
            batch = cur.fetchone()
            assert batch
            days = max(1, int(batch[0] or 5))
            due_at = _dt(app[4]) + timedelta(days=days)
            manifest_due = _dt(manifest["dueAt"])
            assert due_at == manifest_due, (due_at, manifest_due)
            cur.execute("SELECT UTC_TIMESTAMP(6)")
            now = _dt(cur.fetchone()[0])
            print("[REAL_TIME_GATE]", {"now": now.isoformat(), "dueAt": due_at.isoformat()})
            if now < due_at:
                raise AssertionError(f"REAL_TIME_GATE_NOT_DUE now={now.isoformat()} dueAt={due_at.isoformat()}")

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

            cur.execute("SELECT status, result, open_key FROM t_affairs_funding_appeal WHERE id=%s", (appeal_id,))
            assert cur.fetchone() == ("CLOSED", "OVERRULED", None)
            cur.execute(
                "SELECT action FROM t_affairs_audit_trail WHERE biz_type='FUNDING' AND biz_id=%s ORDER BY id",
                (app_id,),
            )
            actions = [str(row[0]).upper() for row in cur.fetchall()]
            assert "GRANT_ELIGIBILITY_RECHECK" not in actions
            assert "GRANTED" not in actions
    finally:
        db.close()
    print("[RESULT] REAL_TIME_GATE_DUE SA-005 restored authority may continue")


def final() -> None:
    root, evidence, manifest = _load()
    browser = json.loads((root / "student-affairs-sa005-post-publicity-evidence.json").read_text(encoding="utf-8"))
    assert browser.get("result") == "REAL_PASS"
    assert browser.get("exactHead") == os.environ["E2E_TARGET_SHA"]
    assert int(browser.get("confirmHttpStatus") or 0) == 200
    assert str(browser.get("applicationId") or "") == str(manifest["applicationId"])

    app_id = int(manifest["applicationId"])
    appeal_id = int(manifest["appealId"])
    db = conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT student_id, project_type, status, check_snapshot_json,
                          approved_amount, quota_reserved, result_at, version, workflow_instance_id
                   FROM t_affairs_funding_application WHERE id=%s""",
                (app_id,),
            )
            app = cur.fetchone()
            print("[FINAL_APPLICATION]", app)
            assert app
            student_id = int(app[0])
            assert app[1] == "GRANT"
            assert app[2] == "GRANTED"
            snapshot = json.loads(app[3] or "{}")
            recheck = snapshot.get("grantEligibilityRecheck") or {}
            print("[GRANT_ELIGIBILITY_RECHECK]", json.dumps(recheck, ensure_ascii=False, sort_keys=True))
            assert recheck.get("type") == "GRANT"
            assert recheck.get("ok") is True
            assert recheck.get("inDifficultLibrary") is True
            assert recheck.get("aidLevel") == "SPECIAL"
            assert recheck.get("aidLevelAllowed") is True
            assert recheck.get("ruleVersion")
            assert recheck.get("evaluatedAt")
            amount_authority = snapshot.get("amountAuthority") or {}
            assert amount_authority.get("source") in {"FUNDING_PROJECT", "DUAL_REVIEW_ADJUSTMENT"}
            assert str(app[4]) == "2500.00"
            assert bool(app[5]) is True
            assert app[6] is not None
            assert int(app[7]) > int(manifest["preVersion"])

            if app[8]:
                cur.execute("SELECT status FROM t_workflow_instance WHERE id=%s", (int(app[8]),))
                workflow = cur.fetchone()
                assert workflow and workflow[0] == "APPROVED"

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
            assert aid and aid[0] == "APPROVED" and aid[1] == "SPECIAL" and aid[2] == evidence["schoolYear"]

            cur.execute(
                "SELECT COUNT(*) FROM t_student_stage_event WHERE student_id=%s AND to_stage='FUNDING_GRANTED' AND source_module='student-affairs'",
                (student_id,),
            )
            assert int(cur.fetchone()[0]) == 1
            cur.execute(
                "SELECT COUNT(*) FROM t_affairs_funding_disbursement WHERE application_id=%s AND is_deleted=0",
                (app_id,),
            )
            assert int(cur.fetchone()[0]) == 0
            cur.execute(
                """SELECT COUNT(*) FROM t_unified_todo
                   WHERE source_module='student-affairs' AND source_biz_id=%s
                     AND todo_type='FUNDING_APPROVAL' AND status='PENDING' AND is_deleted=0""",
                (app_id,),
            )
            assert int(cur.fetchone()[0]) == 0
            cur.execute("SELECT status, result, open_key FROM t_affairs_funding_appeal WHERE id=%s", (appeal_id,))
            assert cur.fetchone() == ("CLOSED", "OVERRULED", None)

            cur.execute(
                "SELECT action FROM t_affairs_audit_trail WHERE biz_type='FUNDING' AND biz_id=%s ORDER BY id",
                (app_id,),
            )
            actions = [str(row[0]).upper() for row in cur.fetchall()]
            print("[FINAL_AUDIT]", actions)
            required = {
                "APPLY", "RETURNED", "STUDENT_EDIT_RETURNED", "STUDENT_RESUBMIT",
                "TO_PUBLICITY", "FUNDING_APPEAL_SUBMIT", "FUNDING_APPEAL_REVIEW",
                "GRANT_ELIGIBILITY_RECHECK", "APPROVED_AMOUNT_FROZEN", "GRANTED",
            }
            assert required.issubset(set(actions)), (required - set(actions), actions)
            assert actions.count("GRANT_ELIGIBILITY_RECHECK") == 1
            assert actions.count("GRANTED") == 1
    finally:
        db.close()

    print("[sa005-post-publicity-mysql-seal]", json.dumps({
        "result": "REAL_PASS",
        "applicationId": str(app_id),
        "status": "GRANTED",
        "grantEligibilityRecheck": "PASS",
        "aidLevel": "SPECIAL",
        "fundingGrantedStageEvents": 1,
        "pendingFundingTodos": 0,
    }, ensure_ascii=False, sort_keys=True))
    print("[RESULT] REAL_PASS SA-005 real-time GRANT continuation + SA-002 grant-time recheck")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preflight", "final"])
    args = parser.parse_args()
    if args.mode == "preflight":
        preflight()
    else:
        final()


if __name__ == "__main__":
    main()
