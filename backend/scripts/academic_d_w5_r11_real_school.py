#!/usr/bin/env python3
"""D-W5 R11 real-school completion proof on the isolated 20K sandbox database.

The script never manufactures semester facts. It scans existing AaTerm rows, evaluates each
through the production R11 stage readers, and only uses the public R11 create/check/complete
service chain when one real term already satisfies all six stages. A red run still writes a
complete blocker inventory so the next construction knife can fix facts instead of guessing.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import academic_affairs_semester_pilot_service as r11

SANDBOX_TENANT_ID = 1000000000000000007
SANDBOX_TENANT_CODE = "sandbox-school"
EXPECTED_DATABASE = "sandbox_20k_gate"
ALLOW_ENV = "ACADEMIC_D_W5_R11_ALLOW"


def _assert_safe_target() -> None:
    if str(os.getenv(ALLOW_ENV) or "").lower() != "true":
        raise SystemExit(f"{ALLOW_ENV}=true is required")
    raw = str(os.getenv("DATABASE_URL") or "")
    parsed = urlparse(raw)
    database = parsed.path.lstrip("/").split("?", 1)[0]
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("R11 real-school proof only accepts a local MySQL target")
    if database != EXPECTED_DATABASE:
        raise SystemExit(f"R11 real-school proof requires database {EXPECTED_DATABASE!r}, got {database!r}")
    if str(os.getenv("APP_ENV") or "").lower() not in {"prod", "production"}:
        raise SystemExit("APP_ENV=production is required to exercise the real R11 completion guard")
    if str(os.getenv("DEPLOYMENT_MODE") or "").lower() != "production":
        raise SystemExit("DEPLOYMENT_MODE=production is required to exercise the real R11 completion guard")
    if str(os.getenv("MOCK_LOGIN_ENABLED") or "").lower() not in {"0", "false", "no", "off"}:
        raise SystemExit("MOCK_LOGIN_ENABLED=false is required")


def _user() -> dict:
    return {
        "userId": "academic-d-w5-r11",
        "loginName": "academic-d-w5-r11",
        "realName": "D-W5真实学期验收",
        "userType": "ADMIN",
        "currentRoleCode": "ACADEMIC_ADMIN",
        "tenantId": str(SANDBOX_TENANT_ID),
    }


def _activate_context() -> dict:
    user = _user()
    set_tenant({"tenantId": str(SANDBOX_TENANT_ID), "tenantCode": SANDBOX_TENANT_CODE})
    set_current_user(user)
    return user


def _term_rows():
    from app.models import AaTerm

    db = get_sessionmaker()()
    try:
        return db.query(AaTerm).filter(
            AaTerm.tenant_id == SANDBOX_TENANT_ID,
            AaTerm.is_deleted.is_(False),
        ).order_by(AaTerm.id).all()
    finally:
        db.close()


def _proxy(term):
    return type(
        "DWR11PilotProbe",
        (),
        {
            "id": 0,
            "term_id": int(term.id),
            "term_code": f"{term.year_code}-{term.term_no}",
            "real_data_confirmed": True,
        },
    )()


def _candidate(term, user: dict) -> dict:
    try:
        stages = r11._run_stages(_proxy(term), user)
    except Exception as exc:  # production reader failures are blockers; never guess around them
        return {
            "termId": str(term.id),
            "termCode": f"{term.year_code}-{term.term_no}",
            "termName": getattr(term, "term_name", None) or "",
            "passedStageCount": 0,
            "stageCount": 6,
            "blockerCount": 1,
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            "stages": [],
        }
    stage_summary = [
        {
            "stageCode": row["stageCode"],
            "passed": bool(row["passed"]),
            "blockerCount": int(row["blockerCount"]),
            "warningCount": int(row["warningCount"]),
            "blockers": list(row.get("blockers") or []),
            "warnings": list(row.get("warnings") or []),
            "evidence": row.get("evidence") or {},
            "evidenceHash": row.get("evidenceHash") or "",
        }
        for row in stages
    ]
    return {
        "termId": str(term.id),
        "termCode": f"{term.year_code}-{term.term_no}",
        "termName": getattr(term, "term_name", None) or "",
        "passedStageCount": sum(1 for row in stages if row["passed"]),
        "stageCount": len(stages),
        "blockerCount": sum(int(row["blockerCount"]) for row in stages),
        "warningCount": sum(int(row["warningCount"]) for row in stages),
        "stages": stage_summary,
    }


def _rank_candidates(user: dict) -> tuple[object, dict, list[dict]]:
    terms = _term_rows()
    if not terms:
        raise RuntimeError("R11 cannot run: sandbox-school has no AaTerm rows")
    candidates = [(term, _candidate(term, user)) for term in terms]
    ranked = sorted(
        candidates,
        key=lambda item: (
            int(item[1]["passedStageCount"]),
            -int(item[1]["blockerCount"]),
            int(item[0].id),
        ),
        reverse=True,
    )
    selected_term, selected = ranked[0]
    return selected_term, selected, [item[1] for item in ranked]


def _selected_ready(selected: dict) -> bool:
    return (
        int(selected.get("stageCount") or 0) == 6
        and int(selected.get("passedStageCount") or 0) == 6
        and int(selected.get("blockerCount") or 0) == 0
    )


def _persisted_proof(pilot_id: int) -> dict:
    from app.models.academic_affairs_r11 import AaSemesterPilot, AaSemesterPilotCheckpoint

    db = get_sessionmaker()()
    try:
        pilot = db.query(AaSemesterPilot).filter(
            AaSemesterPilot.tenant_id == SANDBOX_TENANT_ID,
            AaSemesterPilot.id == int(pilot_id),
            AaSemesterPilot.is_deleted.is_(False),
        ).one()
        checkpoints = db.query(AaSemesterPilotCheckpoint).filter(
            AaSemesterPilotCheckpoint.tenant_id == SANDBOX_TENANT_ID,
            AaSemesterPilotCheckpoint.pilot_id == pilot.id,
            AaSemesterPilotCheckpoint.run_no == int(pilot.check_run_no),
            AaSemesterPilotCheckpoint.is_deleted.is_(False),
        ).order_by(AaSemesterPilotCheckpoint.id).all()
        return {
            "pilotStatus": pilot.status,
            "checkRunNo": int(pilot.check_run_no or 0),
            "passedStageCount": int(pilot.passed_stage_count or 0),
            "blockerCount": int(pilot.blocker_count or 0),
            "latestEvidenceHash": pilot.latest_evidence_hash or "",
            "completedAt": pilot.completed_at.isoformat() if pilot.completed_at else None,
            "completedBy": pilot.completed_by or "",
            "checkpointCount": len(checkpoints),
            "checkpointCodes": [row.stage_code for row in checkpoints],
            "checkpointHashes": [row.evidence_hash for row in checkpoints],
            "allCheckpointsPassed": all(bool(row.passed) for row in checkpoints),
        }
    finally:
        db.close()


def _write_output(output: str | Path, payload: dict) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(output: str | Path) -> dict:
    _assert_safe_target()
    user = _activate_context()
    term, selected, candidates = _rank_candidates(user)

    base_payload = {
        "schemaVersion": 2,
        "tenantId": str(SANDBOX_TENANT_ID),
        "tenantCode": SANDBOX_TENANT_CODE,
        "termId": str(term.id),
        "termCode": selected["termCode"],
        "selectedPreflight": selected,
        "candidateCount": len(candidates),
        "candidates": candidates,
        "r11RealDataCompleted": False,
    }
    _write_output(output, base_payload)

    if not _selected_ready(selected):
        blockers = [
            {
                "termCode": row["termCode"],
                "passedStageCount": row["passedStageCount"],
                "blockerCount": row["blockerCount"],
                "failedStages": [stage for stage in row.get("stages", []) if not stage.get("passed")],
                "error": row.get("error") or "",
            }
            for row in candidates
        ]
        base_payload["blockers"] = blockers
        _write_output(output, base_payload)
        raise RuntimeError(
            "no existing real term satisfies all six R11 stages; blocker inventory written to "
            f"{Path(output)}"
        )

    created = r11.create_pilot(
        user,
        term_id=int(term.id),
        pilot_name=f"D-W5真实学校学期-{selected['termCode']}",
        purpose="D-W5最终Gold真实学校完整学期签字",
        real_data_confirmed=True,
    )
    pilot_id = int(created["pilotId"])
    checked = r11.run_check(user, pilot_id)
    if checked.get("status") != "READY_TO_COMPLETE":
        raise RuntimeError(f"R11 persisted check did not reach READY_TO_COMPLETE: {checked}")
    if int(checked.get("passedStageCount") or 0) != 6 or int(checked.get("blockerCount") or 0) != 0:
        raise RuntimeError(f"R11 persisted check is not six-stage green: {checked}")

    completed = r11.complete_pilot(
        user,
        pilot_id,
        confirm_text="CONFIRM_REAL_SEMESTER_COMPLETED",
        completion_note="D-W5真实学校20K数据六阶段全通过并完成签字",
    )
    if completed.get("status") != "COMPLETED" or completed.get("externalSemesterActuallyCompleted") is not True:
        raise RuntimeError(f"R11 completion did not persist COMPLETED: {completed}")

    persisted = _persisted_proof(pilot_id)
    if persisted["pilotStatus"] != "COMPLETED":
        raise RuntimeError(f"persisted R11 pilot is not COMPLETED: {persisted}")
    if persisted["checkpointCount"] != 6 or not persisted["allCheckpointsPassed"]:
        raise RuntimeError(f"persisted R11 checkpoints are incomplete: {persisted}")
    if persisted["checkpointCodes"] != [code for code, _name in r11._STAGE_ORDER]:
        raise RuntimeError(f"persisted R11 stage order drifted: {persisted}")

    payload = {
        **base_payload,
        "pilotId": str(pilot_id),
        "persisted": persisted,
        "environment": completed.get("environment") or {},
        "r11RealDataCompleted": True,
    }
    _write_output(output, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = run(args.output)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
