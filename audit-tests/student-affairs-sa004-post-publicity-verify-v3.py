from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path

import pymysql


EVIDENCE = Path("../e2e/student-affairs-scholarship-audit-evidence.json")
MANIFEST = Path("../e2e/student-affairs-sa004-time-gate-manifest.json")
POST_EVIDENCE = Path("../e2e/student-affairs-sa004-post-publicity-evidence.json")


def conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "e2e_root"),
        database=os.getenv("DB_NAME", "student_lifecycle_e2e"),
        charset="utf8mb4",
    )


def _load_json(path: Path) -> dict:
    assert path.exists(), f"missing evidence: {path.resolve()}"
    return json.loads(path.read_text(encoding="utf-8"))


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _same_second(left, right) -> bool:
    return abs((_dt(left) - _dt(right)).total_seconds()) < 1


def _base() -> tuple[dict, dict]:
    evidence = _load_json(EVIDENCE)
    manifest = _load_json(MANIFEST)
    target = os.environ["E2E_TARGET_SHA"]
    assert str(evidence.get("exactHead") or "") == target
    assert str(manifest.get("productSha") or "") == target
    assert str(manifest.get("applicationId") or "") == str(evidence.get("applicationId") or "")
    assert str(manifest.get("batchId") or "") == str(evidence.get("batchId") or "")
    assert str(manifest.get("appealId") or "") == str(evidence.get("appealId") or "")
    assert int(manifest.get("publicityDays") or 0) >= 1
    assert manifest.get("dueAt")
    return evidence, manifest


def verify_preflight() -> None:
    evidence, manifest = _base()
    app_id = int(evidence["applicationId"])
    appeal_id = int(evidence["appealId"])
    batch_id = int(evidence["batchId"])

    db = conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT student_id, project_type, status, publicity_at, version, workflow_instance_id
                   FROM t_affairs_funding_application WHERE id=%s""",
                (app_id,),
            )
            app = cur.fetchone()
            print("[APPLICATION_PRE]", app)
            assert app
            assert app[1] == "SCHOLARSHIP"
            assert app[2] == "PUBLICITY"
            assert app[3] is not None
            assert int(app[4]) == int(manifest["preVersion"])
            assert str(app[0]) == str(manifest["studentId"])
            assert str(app[5] or "") == str(manifest.get("workflowInstanceId") or "")

            cur.execute(
                "SELECT publicity_days FROM t_affairs_funding_batch WHERE id=%s",
                (batch_id,),
            )
            batch = cur.fetchone()
            assert batch
            days = max(1, int(batch[0] or 5))
            assert days == int(manifest["publicityDays"])
            due = _dt(app[3]) + timedelta(days=days)
            assert _same_second(due, manifest["dueAt"]), (due.isoformat(), manifest["dueAt"])
            assert _same_second(app[3], manifest["publicityAt"]), (app[3], manifest["publicityAt"])

            cur.execute("SELECT UTC_TIMESTAMP(6)")
            now = _dt(cur.fetchone()[0])
            print("[REAL_TIME_GATE]", {"now": now.isoformat(), "dueAt": due.isoformat()})
            assert now >= due, f"REAL_TIME_GATE_NOT_DUE now={now.isoformat()} dueAt={due.isoformat()}"

            cur.execute(
                "SELECT status, result, open_key FROM t_affairs_funding_appeal WHERE id=%s",
                (appeal_id,),
            )
            appeal = cur.fetchone()
            assert appeal == ("CLOSED", "OVERRULED", None), appeal

            cur.execute(
                "SELECT COUNT(*) FROM t_student_stage_event WHERE student_id=%s AND to_stage='FUNDING_GRANTED' AND source_module='student-affairs'",
                (int(app[0]),),
            )
            assert int(cur.fetchone()[0]) == 0

            cur.execute(
                "SELECT COUNT(*) FROM t_affairs_audit_trail WHERE biz_type='FUNDING' AND biz_id=%s AND action='GRANTED'",
                (app_id,),
            )
            assert int(cur.fetchone()[0]) == 0
    finally:
        db.close()

    print("[sa004-post-publicity-preflight]", json.dumps({
        "sa": "SA-004",
        "result": "REAL_TIME_GATE_DUE",
        "applicationId": str(app_id),
        "dueAt": manifest["dueAt"],
        "sourceRunId": str(manifest.get("sourceRunId") or ""),
    }, ensure_ascii=False, sort_keys=True))


def verify_final() -> None:
    evidence, manifest = _base()
    post = _load_json(POST_EVIDENCE)
    app_id = int(evidence["applicationId"])
    appeal_id = int(evidence["appealId"])

    assert str(post.get("exactHead") or "") == os.environ["E2E_TARGET_SHA"]
    assert str(post.get("applicationId") or "") == str(app_id)
    assert post.get("result") == "REAL_PASS"
    assert post.get("surface") == "STAFF_PC_REAL_PUBLICITY_CONFIRM"
    assert int(post.get("confirmHttpStatus") or 0) == 200

    db = conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT student_id, project_type, status, result_at, version, workflow_instance_id
                   FROM t_affairs_funding_application WHERE id=%s""",
                (app_id,),
            )
            app = cur.fetchone()
            print("[APPLICATION_FINAL]", app)
            assert app
            student_id = int(app[0])
            assert app[1] == "SCHOLARSHIP"
            assert app[2] == "GRANTED"
            assert app[3] is not None
            assert int(app[4]) > int(manifest["preVersion"])

            if app[5]:
                cur.execute("SELECT status FROM t_workflow_instance WHERE id=%s", (int(app[5]),))
                wf = cur.fetchone()
                assert wf and wf[0] == "APPROVED", wf

            cur.execute(
                """SELECT COUNT(*) FROM t_student_stage_event
                   WHERE student_id=%s AND to_stage='FUNDING_GRANTED' AND source_module='student-affairs'""",
                (student_id,),
            )
            granted_events = int(cur.fetchone()[0])
            assert granted_events == 1, granted_events

            cur.execute(
                "SELECT action FROM t_affairs_audit_trail WHERE biz_type='FUNDING' AND biz_id=%s ORDER BY id",
                (app_id,),
            )
            actions = [str(row[0]).upper() for row in cur.fetchall()]
            print("[AUDIT_FINAL]", actions)
            required = {
                "APPLY",
                "RETURNED",
                "STUDENT_EDIT_RETURNED",
                "STUDENT_RESUBMIT",
                "TO_PUBLICITY",
                "FUNDING_APPEAL_SUBMIT",
                "FUNDING_APPEAL_REVIEW",
                "GRANTED",
            }
            assert required.issubset(set(actions)), (required - set(actions), actions)
            assert actions.count("GRANTED") == 1, actions

            cur.execute(
                """SELECT COUNT(*) FROM t_unified_todo
                   WHERE source_module='student-affairs' AND source_biz_id=%s
                     AND todo_type='FUNDING_APPROVAL' AND status='PENDING' AND is_deleted=0""",
                (app_id,),
            )
            pending_todos = int(cur.fetchone()[0])
            assert pending_todos == 0, pending_todos

            cur.execute(
                "SELECT status, result, open_key FROM t_affairs_funding_appeal WHERE id=%s",
                (appeal_id,),
            )
            appeal = cur.fetchone()
            assert appeal == ("CLOSED", "OVERRULED", None), appeal
    finally:
        db.close()

    print("[sa004-post-publicity-mysql-seal]", json.dumps({
        "sa": "SA-004",
        "result": "REAL_PASS",
        "applicationId": str(app_id),
        "status": "GRANTED",
        "grantedStageEvents": granted_events,
        "pendingTodos": pending_todos,
        "sourceRunId": str(manifest.get("sourceRunId") or ""),
    }, ensure_ascii=False, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preflight", "final"])
    args = parser.parse_args()
    if args.mode == "preflight":
        verify_preflight()
    else:
        verify_final()


if __name__ == "__main__":
    main()
