"""
学生主档服务（BACKEND-OVERNIGHT 阶段11）
────────────────────────────────────────────────────────────
- DB_ENABLED=false：内存 mock（本文件 _MOCK_STUDENTS），结构对齐 t_student_profile。
- DB_ENABLED=true：走 SQLAlchemy（TODO P3：真实 CRUD 联调，当前已留查询骨架）。
- 一律按 tenant_id 过滤 + is_deleted=false；void=逻辑作废；敏感字段恒返回脱敏口径。
"""
from __future__ import annotations

import itertools
from datetime import datetime
from typing import Optional

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.core.pagination import page_slice
from app.db.session import db_enabled

_id_seq = itertools.count(1001)
_now = lambda: datetime.now().isoformat(timespec="seconds")  # noqa: E731


def _mask_phone(v: str | None) -> str:
    v = v or ""
    return v[:3] + "****" + v[-4:] if len(v) >= 7 else ("***" if v else "")


def _mask_id_card(v: str | None) -> str:
    v = v or ""
    return v[:3] + "*" * max(len(v) - 7, 4) + v[-4:] if len(v) >= 8 else ("***" if v else "")


def _mk(no, name, gender, college, major, cls, grade, stage, status, risk, phone, id_card):
    sid = str(next(_id_seq))
    return {
        "id": sid, "studentId": sid, "tenantId": "1000000000000000001",
        "studentNo": no, "realName": name, "gender": gender,
        "collegeId": "c1", "collegeName": college, "majorId": "m1", "majorName": major,
        "classId": "k1", "className": cls, "grade": grade,
        "currentStage": stage, "studentStatus": status, "riskLevel": risk,
        "phoneMasked": _mask_phone(phone), "idCardMasked": _mask_id_card(id_card),
        "isDeleted": False, "createdAt": _now(), "updatedAt": _now(), "version": 0,
    }


_MOCK_STUDENTS: list[dict] = [
    _mk("2023115001", "赵一凡", "男", "软件学院", "软件技术", "软件2301", "2023", "INTERNSHIP", "NORMAL", "NONE", "13812340001", "430102200501011234"),
    _mk("2023115002", "钱雨桐", "女", "软件学院", "软件技术", "软件2301", "2023", "INTERNSHIP", "NORMAL", "MEDIUM", "13812340002", "430102200502021234"),
    _mk("2023115003", "孙浩然", "男", "软件学院", "软件技术", "软件2301", "2023", "ON_CAMPUS", "NORMAL", "NONE", "13812340003", "430102200503031234"),
    _mk("2024115001", "李雨萌", "女", "软件学院", "大数据技术", "大数据2401", "2024", "ORIENTATION", "NORMAL", "NONE", "13812340004", "430102200601011234"),
    _mk("2022115001", "王晨", "男", "护理学院", "护理", "护理2201", "2022", "GRADUATION_DESIGN", "NORMAL", "HIGH", "13812340005", "430102200401011234"),
    _mk("2022115002", "陈浩宇", "男", "机电学院", "机电一体化", "机电2201", "2022", "EMPLOYMENT", "NORMAL", "MEDIUM", "13812340006", "430102200402021234"),
]

_TIMELINE = {
    "default": [
        {"eventCategory": "ORIENTATION", "title": "迎新报到完成", "occurredAt": "2023-09-01 09:30"},
        {"eventCategory": "IDENTITY", "title": "身份核验通过", "occurredAt": "2023-09-05 10:00"},
        {"eventCategory": "ACADEMIC", "title": "学籍信息录入", "occurredAt": "2023-09-10 15:00"},
    ]
}


def _visible(rows: list[dict]) -> list[dict]:
    tid = current_tenant_id() or "1000000000000000001"
    return [r for r in rows if not r["isDeleted"] and r["tenantId"] == tid]


def list_students(page: int, page_size: int, keyword: Optional[str] = None, college: Optional[str] = None,
                  major: Optional[str] = None, class_name: Optional[str] = None, status: Optional[str] = None,
                  risk_level: Optional[str] = None, class_ids=None, student_ids=None) -> tuple[list[dict], int]:
    if db_enabled():
        from app.services import db_service
        return db_service.list_students(page, page_size, keyword, college, major,
                                        class_name, status, risk_level,
                                        class_ids=class_ids, student_ids=student_ids)
    rows = _visible(_MOCK_STUDENTS)
    if keyword:
        rows = [r for r in rows if keyword in r["realName"] or keyword in r["studentNo"] or keyword in r["className"]]
    if college:
        rows = [r for r in rows if r["collegeName"] == college or r["collegeId"] == college]
    if major:
        rows = [r for r in rows if r["majorName"] == major or r["majorId"] == major]
    if class_name:
        rows = [r for r in rows if r["className"] == class_name]
    if status:
        rows = [r for r in rows if r["studentStatus"] == status or r["currentStage"] == status]
    if risk_level:
        rows = [r for r in rows if r["riskLevel"] == risk_level]
    return page_slice(rows, page, page_size), len(rows)


def _find(student_id: str) -> dict:
    row = next((r for r in _visible(_MOCK_STUDENTS) if r["id"] == str(student_id)), None)
    if not row:
        raise not_found("学生不存在或不在当前数据范围内")
    return row


def get_student(student_id: str) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.get_student(student_id)
    row = _find(student_id)
    return {
        **row,
        "contacts": [
            {"contactType": "PHONE", "valueMasked": row["phoneMasked"], "verifiedStatus": "VERIFIED", "isPrimary": True},
            {"contactType": "GUARDIAN_PHONE", "valueMasked": "139****0000", "verifiedStatus": "UNVERIFIED", "isPrimary": False},
        ],
        "statusRecord": {"currentStage": row["currentStage"], "studentStatus": row["studentStatus"]},
        "timeline": _TIMELINE["default"],
    }


def create_student(body) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.create_student(body)
    if any(r["studentNo"] == body.studentNo for r in _visible(_MOCK_STUDENTS)):
        raise AppException("DATA_CONFLICT", "学号已存在（租户内唯一，不可复用为新档）")
    tid = current_tenant_id() or "1000000000000000001"
    voided = next((r for r in _MOCK_STUDENTS
                   if r["tenantId"] == tid and r["studentNo"] == body.studentNo and r["isDeleted"]), None)
    if voided:
        voided["isDeleted"] = False
        voided["realName"] = body.realName
        voided["gender"] = body.gender or voided.get("gender") or ""
        voided["grade"] = body.grade or voided.get("grade") or ""
        voided["studentStatus"] = "NORMAL"
        voided["currentStage"] = "ORIENTATION"
        voided["phoneMasked"] = _mask_phone(body.phone or "")
        voided["updatedAt"] = _now()
        voided["version"] = int(voided.get("version") or 0) + 1
        voided["restored"] = True
        return voided
    row = _mk(body.studentNo, body.realName, body.gender or "", "", "", "", body.grade or "",
              "ORIENTATION", "NORMAL", "NONE", body.phone or "", body.idCard or "")
    row["restored"] = False
    _MOCK_STUDENTS.append(row)
    return row


def update_student(student_id: str, body) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.update_student(student_id, body)
    row = _find(student_id)
    for src, dst in [("realName", "realName"), ("gender", "gender"), ("grade", "grade"), ("remark", "remark")]:
        v = getattr(body, src, None)
        if v is not None:
            row[dst] = v
    if getattr(body, "phone", None):
        row["phoneMasked"] = _mask_phone(body.phone)
    row["updatedAt"] = _now()
    row["version"] += 1
    return row


def void_student(student_id: str, reason: str) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.void_student(student_id, reason)
    row = _find(student_id)
    row["isDeleted"] = True          # 逻辑作废：不物理删除，档案可追溯（回收站冷冻期见冻结册 t_student_recycle_bin）
    row["studentStatus"] = "RECYCLED"
    row["voidReason"] = reason
    row["updatedAt"] = _now()
    return {"studentId": row["id"], "studentStatus": "RECYCLED", "isDeleted": True, "physicalDelete": False}


def get_timeline(student_id: str) -> list[dict]:
    if db_enabled():
        from app.services import db_service
        return db_service.get_timeline(student_id)
    _find(student_id)
    return _TIMELINE["default"]


def get_risk_summary(student_id: str) -> dict:
    if db_enabled():
        from app.services import db_service
        return db_service.get_risk_summary(student_id)
    row = _find(student_id)
    return {
        "studentId": row["id"], "riskLevel": row["riskLevel"],
        "signals": [] if row["riskLevel"] == "NONE" else [
            {"type": "ACADEMIC" if row["riskLevel"] == "HIGH" else "INTERNSHIP",
             "title": "学业预警 · 3门不及格" if row["riskLevel"] == "HIGH" else "实习周报逾期",
             "level": row["riskLevel"], "occurredAt": _now()},
        ],
    }
