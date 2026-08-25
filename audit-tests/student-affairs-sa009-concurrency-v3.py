from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import CsDormRecord, CsServiceStudent, DormBed, StudentProfile
from app.services.identity_import_file_service import build_student_template
from scripts.e2e_bootstrap_graduation_accounts_ci import _canonical_import, _workbook_with_rows
from scripts.e2e_bootstrap_student_affairs_accounts import (
    CLASS_A,
    COLLEGE,
    MAJOR,
    TENANT,
    _req,
    ensure_org,
)

API_BASE = "http://127.0.0.1:8000/api/v1"
STUDENTS = [
    ("E2E20260901", "SA009并发甲"),
    ("E2E20260902", "SA009并发乙"),
]


def _login_admin() -> str:
    result = _req(
        "POST",
        "/auth/login",
        headers={"X-Forwarded-For": "10.254.9.250"},
        body={"loginName": "admin2", "password": "123456", "tenantCode": TENANT},
    )
    assert result.get("code") == 0, result
    return result["data"]["accessToken"]


def _bootstrap_students(token: str) -> dict[str, int]:
    ensure_org(token)
    workbook = _workbook_with_rows(
        build_student_template(),
        [
            [student_no, real_name, COLLEGE, MAJOR, CLASS_A, "2024", "男", ""]
            for student_no, real_name in STUDENTS
        ],
    )
    _canonical_import(
        token,
        kind="students",
        content=workbook,
        idempotency_namespace="e2e-sa009-v3-concurrency",
    )

    with get_sessionmaker()() as db:
        rows = db.scalars(
            select(StudentProfile).where(
                StudentProfile.student_no.in_([item[0] for item in STUDENTS]),
                StudentProfile.is_deleted.is_(False),
            )
        ).all()
        result = {row.student_no: int(row.id) for row in rows}
    missing = [student_no for student_no, _ in STUDENTS if student_no not in result]
    assert not missing, f"missing SA-009 race students after canonical import: {missing}"
    return result


def _create_single_bed(token: str) -> int:
    created = _req(
        "POST",
        "/student-affairs/dorm/buildings",
        token=token,
        body={
            "buildingName": "E2E SA009 并发宿舍楼",
            "buildingCode": "E2E-SA009-RACE",
            "genderLimit": "MALE",
        },
    )
    assert created.get("code") == 0, created
    building_id = str(created["data"]["buildingId"])

    generated = _req(
        "POST",
        f"/student-affairs/dorm/buildings/{building_id}/generate",
        token=token,
        body={"floors": 1, "roomsPerFloor": 1, "bedsPerRoom": 1},
    )
    assert generated.get("code") == 0, generated

    rooms = _req(
        "GET",
        f"/student-affairs/dorm/buildings/{building_id}/rooms",
        token=token,
        params={"floor": 1, "pageSize": 10},
    )
    assert rooms.get("code") == 0, rooms
    room_rows = (rooms.get("data") or {}).get("items") or []
    assert len(room_rows) == 1, room_rows
    room_id = str(room_rows[0]["roomId"])

    beds = _req(
        "GET",
        f"/student-affairs/dorm/rooms/{room_id}/beds",
        token=token,
        params={"pageSize": 10},
    )
    assert beds.get("code") == 0, beds
    bed_rows = (beds.get("data") or {}).get("items") or []
    assert len(bed_rows) == 1 and bed_rows[0].get("status") == "VACANT", bed_rows
    return int(bed_rows[0]["bedId"])


def _post_checkin(token: str, bed_id: int, student_id: int, forwarded_for: str,
                  barrier: threading.Barrier) -> dict:
    barrier.wait(timeout=10)
    payload = json.dumps({"studentId": str(student_id)}).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}/student-affairs/dorm/beds/{bed_id}/checkin",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Forwarded-For": forwarded_for,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return {"status": int(response.status), "body": json.loads(raw or "{}")}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            body = {"raw": raw}
        return {"status": int(exc.code), "body": body}


def _verify_mysql(bed_id: int, student_ids: list[int]) -> dict:
    with get_sessionmaker()() as db:
        bed = db.get(DormBed, int(bed_id))
        assert bed is not None, f"target bed {bed_id} missing"
        assert bed.status == "OCCUPIED", {
            "bedId": bed_id,
            "status": bed.status,
            "studentId": bed.student_id,
        }
        assert int(bed.student_id or 0) in set(student_ids), {
            "bedStudentId": bed.student_id,
            "candidateStudentIds": student_ids,
        }

        occupied = db.scalars(
            select(DormBed).where(
                DormBed.student_id.in_(student_ids),
                DormBed.status == "OCCUPIED",
                DormBed.is_deleted.is_(False),
            )
        ).all()
        assert len(occupied) == 1, [
            {"bedId": int(item.id), "studentId": int(item.student_id or 0), "status": item.status}
            for item in occupied
        ]

        cs_ids: list[int] = []
        for student_id in student_ids:
            cs = db.scalars(
                select(CsServiceStudent).where(
                    CsServiceStudent.student_id == int(student_id),
                    CsServiceStudent.is_deleted.is_(False),
                )
            ).first()
            cs_ids.append(int(cs.id) if cs else int(student_id))

        records = db.scalars(
            select(CsDormRecord).where(
                CsDormRecord.cs_student_id.in_(cs_ids),
                CsDormRecord.status == "IN",
                CsDormRecord.record_status == "ACTIVE",
                CsDormRecord.is_deleted.is_(False),
            )
        ).all()
        assert len(records) == 1, [
            {
                "recordId": int(item.id),
                "csStudentId": int(item.cs_student_id or 0),
                "status": item.status,
                "recordStatus": item.record_status,
            }
            for item in records
        ]

        return {
            "bedId": int(bed.id),
            "winnerStudentId": int(bed.student_id),
            "occupiedBedsAcrossCandidates": len(occupied),
            "activeInDormRecordsAcrossCandidates": len(records),
            "dormRecordId": int(records[0].id),
        }


def main() -> None:
    token = _login_admin()
    student_map = _bootstrap_students(token)
    student_ids = [student_map[item[0]] for item in STUDENTS]
    bed_id = _create_single_bed(token)

    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _post_checkin,
                token,
                bed_id,
                student_ids[index],
                f"10.254.9.{index + 1}",
                barrier,
            )
            for index in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    statuses = sorted(item["status"] for item in results)
    assert statuses == [200, 409], {
        "expected": [200, 409],
        "actual": statuses,
        "responses": results,
    }
    success = next(item for item in results if item["status"] == 200)
    conflict = next(item for item in results if item["status"] == 409)
    assert success.get("body", {}).get("code") == 0, success
    conflict_body = conflict.get("body", {})
    assert conflict_body.get("bizCode") == "DATA_CONFLICT", conflict
    assert int(conflict_body.get("code") or 0) == 409001, conflict

    mysql_truth = _verify_mysql(bed_id, student_ids)
    evidence = {
        "sa": "SA-009",
        "gate": "REAL_CONCURRENT_SAME_BED_CHECKIN",
        "result": "REAL_PASS",
        "expectedHttpStatuses": [200, 409],
        "actualHttpStatuses": statuses,
        "responses": results,
        "studentIds": student_ids,
        "mysql": mysql_truth,
    }
    print("[sa009-concurrency] " + json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    with open("../e2e/runtime-logs/sa009-concurrency-evidence.json", "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, ensure_ascii=False, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
