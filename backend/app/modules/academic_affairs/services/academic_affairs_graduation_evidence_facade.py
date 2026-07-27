"""R10 毕业资格逐项证据最终层。

保留现有十一项判定逻辑，只把每项结果升级为可追溯证据：来源域、来源主键、事实字段、
下钻地址、检查时点和内容哈希。预审结果仍写原 item_results_json，旧页面可继续读取。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from . import academic_affairs_graduation_service as _legacy

_original_run_items = _legacy._run_items

_ROUTES = {
    "STATUS": "/admin/academic-affairs/student-status",
    "CREDIT": "/admin/academic-affairs/graduation-audit",
    "COURSE_REQUIRED": "/admin/academic-affairs/grade-records",
    "COURSE_ELECTIVE": "/admin/academic-affairs/grade-records",
    "PRACTICE": "/admin/academic-affairs/programs",
    "INTERNSHIP": "/admin/internship/students",
    "GRADUATION_DESIGN": "/admin/graduation/students",
    "DISCIPLINE": "/admin/student-affairs/discipline",
    "EMPLOYMENT": "/admin/employment/students",
    "ARCHIVE": "/admin/student-affairs/archive",
    "FEE": "/admin/academic-affairs/textbook-fees",
}

_SOURCE_TYPES = {
    "STATUS": "STUDENT_PROFILE",
    "CREDIT": "ACADEMIC_GRADE",
    "COURSE_REQUIRED": "ACADEMIC_GRADE",
    "COURSE_ELECTIVE": "ACADEMIC_GRADE",
    "PRACTICE": "PROGRAM_AND_GRADE",
    "INTERNSHIP": "INTERNSHIP_RECORD",
    "GRADUATION_DESIGN": "GRADUATION_STUDENT",
    "DISCIPLINE": "DISCIPLINE_RECORD",
    "EMPLOYMENT": "EMPLOYMENT_STUDENT",
    "ARCHIVE": "ARCHIVE_PACKAGE",
    "FEE": "TEXTBOOK_FEE_LEDGER",
}


def _hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_evidence_item(item: dict, *, student_id=None, checked_at=None) -> dict:
    source = dict(item or {})
    code = str(source.get("item") or "UNKNOWN").upper()
    ref_id = source.get("refId")
    source_ids = [str(ref_id)] if ref_id not in (None, "") else []
    facts = {
        key: value for key, value in source.items()
        if key not in {"evidenceHash", "checkedAt", "drillRoute", "sourceType", "sourceIds", "facts"}
    }
    facts["studentId"] = str(student_id) if student_id not in (None, "") else None
    hash_payload = {
        "item": code,
        "result": source.get("result"),
        "owner": source.get("owner"),
        "sourceType": _SOURCE_TYPES.get(code, "UNKNOWN"),
        "sourceIds": source_ids,
        "facts": facts,
    }
    return {
        **source,
        "evidenceCode": f"GRAD-{code}",
        "sourceType": _SOURCE_TYPES.get(code, "UNKNOWN"),
        "sourceIds": source_ids,
        "facts": facts,
        "drillRoute": _ROUTES.get(code, "/admin/academic-affairs/graduation-audit"),
        "checkedAt": checked_at or datetime.utcnow().isoformat(),
        "evidenceHash": _hash(hash_payload),
    }


def _run_items(db, student) -> list:
    checked_at = datetime.utcnow().isoformat()
    return [
        normalize_evidence_item(item, student_id=student.id, checked_at=checked_at)
        for item in _original_run_items(db, student)
    ]


_legacy._run_items = _run_items
