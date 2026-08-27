from __future__ import annotations

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


def main() -> None:
    evidence_path = Path("../e2e/student-affairs-sa011-evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence.get("result") == "REAL_PASS", evidence
    assert evidence.get("exactHead") == os.environ["E2E_TARGET_SHA"], evidence
    assert evidence.get("surface") == "STAFF_PC+STUDENT_PC+TEACHER_MINI_BROWSER+STUDENT_MINI_BROWSER", evidence
    assert int(evidence.get("crossScopeHttpStatus") or 0) == 403
    assert int(evidence.get("duplicateSourceHttpStatus") or 0) == 409
    assert evidence.get("teacherMobileRisk") == "PASS"
    assert int(evidence.get("teacherMobileVersion") or 0) >= 1
    assert evidence.get("teacherMiniBrowser") == "PASS"
    assert evidence.get("teacherMiniProcess") == "PASS"
    assert evidence.get("studentPcSafeResult") == "PASS"
    assert evidence.get("studentMobilePrivacy") == "PASS"
    assert evidence.get("studentMiniSafeResult") == "PASS"
    assert evidence.get("studentMiniBrowserPrivacy") == "PASS"
    assert evidence.get("studentPrivacy") == "PASS"

    risk_id = int(evidence["riskId"])
    student_id = int(evidence["studentId"])
    source_ref = int(evidence["sourceRefId"])
    title = str(evidence["title"])
    detail = str(evidence["detailText"])

    db = conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT student_id, source, source_ref_id, risk_level, status, owner_id,
                          closed_reason, version, detail, is_archived
                   FROM t_affairs_risk_record WHERE id=%s""",
                (risk_id,),
            )
            row = cur.fetchone()
            print("[SA011_MAIN_RISK]", row)
            assert row, f"risk {risk_id} missing"
            assert int(row[0]) == student_id
            assert row[1] == "MANUAL"
            assert row[2] is None, row
            assert row[4] == "CLOSED", row
            assert row[5] is not None, row
            assert str(row[6] or "").strip(), row
            assert int(row[7] or 0) >= 10, row
            assert row[8] == detail, (row[8], detail)
            assert bool(row[9]) is False

            cur.execute(
                """SELECT action, content, operator, from_status, to_status
                   FROM t_affairs_risk_handle_record
                   WHERE risk_id=%s AND is_deleted=0 ORDER BY id""",
                (risk_id,),
            )
            handles = cur.fetchall()
            for item in handles:
                print("[SA011_HANDLE]", item)
            actions = [str(item[0]).upper() for item in handles]
            required = {"ASSIGN", "PROCESS", "FOLLOW", "ESCALATE", "TAKEOVER", "CLOSE", "REOPEN"}
            assert required.issubset(set(actions)), (required - set(actions), actions)
            assert actions.count("ASSIGN") >= 2, actions
            assert actions.count("PROCESS") >= 2, actions
            assert actions.count("CLOSE") >= 2, actions
            assert actions.count("REOPEN") == 1, actions
            mini_process = [item for item in handles if str(item[0]).upper() == "PROCESS" and "教师小程序真实处置" in str(item[1] or "")]
            assert mini_process, handles

            cur.execute(
                """SELECT action, operator, role_name, detail
                   FROM t_affairs_audit_trail
                   WHERE biz_type='RISK' AND biz_id=%s ORDER BY id""",
                (risk_id,),
            )
            trail = cur.fetchall()
            for item in trail:
                print("[SA011_AUDIT]", item)
            audit_actions = [str(item[0]).upper() for item in trail]
            assert required.issubset(set(audit_actions)), (required - set(audit_actions), audit_actions)

            cur.execute(
                """SELECT COUNT(*) FROM t_student_stage_event
                   WHERE tenant_id=(SELECT tenant_id FROM t_affairs_risk_record WHERE id=%s)
                     AND student_id=%s AND to_stage='RISK_CLOSED'
                     AND source_module='student-affairs'""",
                (risk_id, student_id),
            )
            closed_events = int(cur.fetchone()[0])
            print("[SA011_STAGE_EVENTS]", closed_events)
            assert closed_events == 2, closed_events

            cur.execute(
                """SELECT status, assignee_id FROM t_unified_todo
                   WHERE source_module='student-affairs' AND source_biz_id=%s
                     AND todo_type='RISK_HANDLE' AND is_deleted=0""",
                (risk_id,),
            )
            todos = cur.fetchall()
            print("[SA011_TODOS]", todos)
            assert todos, "risk todo missing"
            assert all(str(item[0]).upper() == "DONE" for item in todos), todos

            cur.execute(
                """SELECT title, content, rendered_title, rendered_content_plain
                   FROM t_unified_message
                   WHERE source_module='student-affairs' AND source_biz_id=%s AND is_deleted=0""",
                (risk_id,),
            )
            messages = cur.fetchall()
            print("[SA011_MESSAGES]", messages)
            assert messages, "risk message delivery missing"
            safe_close_messages = 0
            for msg in messages:
                text = " ".join(str(v or "") for v in msg)
                assert title not in text, text
                assert detail not in text, text
                if "风险已关闭" in text and "相关风险已处置关闭" in text:
                    safe_close_messages += 1
            assert safe_close_messages >= 2, messages

            cur.execute(
                """SELECT source, COUNT(*) FROM t_affairs_risk_record
                   WHERE source_ref_id=%s AND source IN ('ACADEMIC_WARNING','DORM')
                     AND is_deleted=0 GROUP BY source ORDER BY source""",
                (source_ref,),
            )
            source_counts = {str(src): int(total) for src, total in cur.fetchall()}
            print("[SA011_SOURCE_DEDUPE]", source_counts)
            assert source_counts.get("ACADEMIC_WARNING") == 1, source_counts
            assert source_counts.get("DORM") == 1, source_counts

            cur.execute(
                """SELECT COUNT(*) FROM t_affairs_risk_record
                   WHERE student_id=%s AND title=%s AND is_deleted=0""",
                (student_id, title),
            )
            assert int(cur.fetchone()[0]) == 1
    finally:
        db.close()

    print("[sa011-mysql-seal]", json.dumps({
        "result": "REAL_PASS",
        "riskId": str(risk_id),
        "finalStatus": "CLOSED",
        "crossScope": 403,
        "duplicateSource": 409,
        "reopenSameRecord": True,
        "teacherMiniBrowser": "PASS",
        "teacherMiniProcess": "PASS",
        "studentPcSafeResult": "PASS",
        "studentMiniSafeResult": "PASS",
        "studentPrivacy": "PASS",
        "riskClosedStageEvents": 2,
        "safeCloseMessages": safe_close_messages,
    }, ensure_ascii=False, sort_keys=True))
    print("[RESULT] REAL_PASS SA-011 four-end Browser First + API + MySQL + safe-result/privacy/scope seal")


if __name__ == "__main__":
    main()
