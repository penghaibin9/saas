from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGED: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        CHANGED.append(rel)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, got {count}")
    return text.replace(old, new, 1)


def replace_function(text: str, name: str, block: str) -> str:
    match = re.search(rf"(?ms)^def {re.escape(name)}\(.*?(?=^def |\Z)", text)
    if not match:
        raise RuntimeError(f"function not found: {name}")
    return text[:match.start()] + block.rstrip() + "\n\n\n" + text[match.end():].lstrip("\n")


def patch_direct_position_api() -> None:
    rel = "backend/app/modules/internship/services/internship_student_service.py"
    text = read(rel)
    helper = '''def _assert_direct_position_change_allowed(record: InternshipRecord) -> None:
    if record.status in ("ONBOARD", "ASSESSING"):
        raise AppException(
            "DATA_CONFLICT",
            "在岗或考核中的学生禁止直接换岗/退岗，请通过实习变更申请审批流程办理",
        )
'''
    text = replace_function(text, "_assert_direct_position_change_allowed", helper)

    assign = '''def assign_position(rec_id, position_id, expected_version=None, user=None) -> dict:
    """锁学生记录后，在一个事务中完成岗位占用、释放、主档更新和审计。"""
    with session() as db:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == _as_id(rec_id),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
        ).with_for_update())
        if not record:
            raise not_found("实习学生记录不存在或不在当前数据范围内")
        _assert_direct_position_change_allowed(record)
        assign_position_in_tx(db, record, position_id, expected_version, user)
        db.commit()
        return _row_of(db, record)
'''
    text = replace_function(text, "assign_position", assign)

    unassign = '''def unassign_position(rec_id, reason: str = "", expected_version=None, user=None) -> dict:
    with session() as db:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == _as_id(rec_id),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False)).with_for_update())
        if not record:
            raise not_found("实习学生记录不存在或不在当前数据范围内")
        _assert_direct_position_change_allowed(record)
        unassign_position_in_tx(
            db, record, expected_version, reason, user=user)
        db.commit()
        return _row_of(db, record)
'''
    text = replace_function(text, "unassign_position", unassign)
    if "allow_active_change" in text:
        raise RuntimeError("active-position bypass parameter remains")
    write(rel, text)


def patch_complaint_scope_and_confidentiality() -> None:
    rel = "backend/app/modules/internship/services/internship_complaint_service.py"
    text = read(rel)
    if "import logging\n" not in text:
        text = replace_once(
            text,
            "from __future__ import annotations\n\nfrom datetime import datetime\n",
            "from __future__ import annotations\n\nimport logging\nfrom datetime import datetime\n",
            "complaint logging import",
        )
    if "_logger = logging.getLogger" not in text:
        text = replace_once(
            text,
            "_TRANSITIONS = {\n",
            "_logger = logging.getLogger(\"app.internship.complaint\")\n\n_TRANSITIONS = {\n",
            "complaint logger",
        )

    row = '''def _row(c, user=None, student_name: str = ""):
    from app.core.permissions import has_permission

    can_sensitive = has_permission(user or {}, "internship.complaint.sensitive")
    contact = ""
    contact_corrupted = False
    if c.complainant_contact_encrypted:
        try:
            contact = decrypt_sensitive(
                c.complainant_contact_encrypted,
                "internship_complaint_contact",
                allow_legacy_plaintext=True,
            ) or ""
        except Exception:  # noqa: BLE001 - 列表展示必须 fail-closed，解密错误已记录
            contact_corrupted = True
            _logger.exception("complaint_contact_decrypt_failed complaint_id=%s", c.id)
    confidential = str(c.confidential_level or "NORMAL").upper() != "NORMAL"
    hide_business_detail = confidential and not can_sensitive
    return {
        "id": str(c.id), "complaintNo": c.complaint_no or "", "source": c.source,
        "targetType": c.target_type or "",
        "enterpriseId": str(c.enterprise_id) if c.enterprise_id else "",
        "studentId": str(c.student_id) if c.student_id else "",
        "studentName": student_name or ("企业投诉" if not c.student_id else ""),
        "batchId": str(c.batch_id) if c.batch_id else "",
        "category": c.category or "", "severity": c.severity,
        "content": "" if hide_business_detail else (c.content or ""),
        "evidenceFileId": "" if hide_business_detail else (c.evidence_file_id or ""),
        "contentMasked": hide_business_detail,
        "evidenceMasked": hide_business_detail,
        "complainantContact": (
            "***" if contact_corrupted else (contact if can_sensitive else _mask(contact))
        ),
        "complainantContactMasked": (not can_sensitive) or contact_corrupted,
        "complainantContactCorrupted": contact_corrupted,
        "confidentialLevel": c.confidential_level,
        "status": c.status, "statusLabel": STATUS_LABEL.get(c.status, c.status),
        "acceptedByName": c.accepted_by_name or "", "ownerName": c.owner_name or "",
        "acceptDeadline": c.accept_deadline or "", "resolveDeadline": c.resolve_deadline or "",
        "conclusion": "" if hide_business_detail else (c.conclusion or ""),
        "followupResult": "" if hide_business_detail else (c.followup_result or ""),
        "riskId": str(c.risk_id) if c.risk_id else "", "createdAt": _iso(c.created_at) or "",
    }
'''
    text = replace_function(text, "_row", row)

    scope = '''def _complaint_in_scope(db, c, user) -> bool:
    """投诉范围使用明确 internship_id/batch_id；禁止按学生最新实习记录猜测。"""
    from app.modules.internship.services.internship_service import (
        _current_scope, _rec_in_scope, assert_student_in_scope)

    scope = _current_scope(user)
    if scope.get("mode") != "SCOPED":
        return True
    if not c.student_id:
        return False
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == c.student_id,
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ))
    if not student:
        return False
    record = None
    if c.internship_id:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == c.internship_id,
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.student_id == c.student_id,
            InternshipRecord.is_deleted.is_(False),
        ))
        if record is None:
            return False
    elif c.batch_id:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.student_id == c.student_id,
            InternshipRecord.batch_id == c.batch_id,
            InternshipRecord.is_deleted.is_(False),
        ))
        if record is None:
            return False
    if record is not None:
        return _rec_in_scope(scope, db, record, student)
    try:
        assert_student_in_scope(db, c.student_id, user)
        return True
    except Exception:  # noqa: BLE001 — no_permission → 不在范围
        return False
'''
    text = replace_function(text, "_complaint_in_scope", scope)

    create_start = text.index("def create_complaint")
    transition_start = text.index("def transition", create_start)
    create_block = text[create_start:transition_start]
    if "confidential_level =" not in create_block:
        create_block = create_block.replace(
            "    contact_plain = str(body.get(\"complainantContact\") or \"\").strip()\n",
            "    contact_plain = str(body.get(\"complainantContact\") or \"\").strip()\n"
            "    confidential_level = str(body.get(\"confidentialLevel\") or \"NORMAL\").strip().upper()\n"
            "    if confidential_level not in (\"NORMAL\", \"CONFIDENTIAL\", \"RESTRICTED\"):\n"
            "        raise AppException(\"VALIDATION_ERROR\", \"保密级别不合法\")\n",
            1,
        )
        create_block = create_block.replace(
            "            confidential_level=(body.get(\"confidentialLevel\") or \"NORMAL\").upper(),\n",
            "            confidential_level=confidential_level,\n",
            1,
        )
        text = text[:create_start] + create_block + text[transition_start:]
    write(rel, text)


def add_tests() -> None:
    rel = "backend/tests/test_internship_review_closeout_static.py"
    content = '''from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_position_services_have_no_active_change_bypass():
    source = _read(
        "backend/app/modules/internship/services/internship_student_service.py"
    )
    assert "allow_active_change" not in source
    assert "def assign_position_in_tx" in source
    assert "def unassign_position_in_tx" in source
    assert "在岗或考核中的学生禁止直接换岗/退岗" in source


def test_complaint_scope_never_guesses_latest_record():
    source = _read(
        "backend/app/modules/internship/services/internship_complaint_service.py"
    )
    block = source[source.index("def _complaint_in_scope"):source.index("def list_complaints")]
    assert "c.internship_id" in block
    assert "c.batch_id" in block
    assert "order_by(InternshipRecord.id.desc())" not in block


def test_confidential_complaint_details_are_permission_gated():
    source = _read(
        "backend/app/modules/internship/services/internship_complaint_service.py"
    )
    block = source[source.index("def _row"):source.index("def _assert_complaint_writable")]
    assert "internship.complaint.sensitive" in block
    assert "hide_business_detail" in block
    assert '"contentMasked"' in block
    assert '"evidenceMasked"' in block
    assert "complaint_contact_decrypt_failed" in block
'''
    write(rel, content)


def patch_contract_checker() -> None:
    rel = "scripts/check/check-internship-production-contracts.py"
    text = read(rel)
    if "active-position bypass parameter remains" not in text:
        anchor = '''students = (ROOT / "backend/app/modules/internship/services/internship_student_service.py").read_text(encoding="utf-8")
if "在岗或考核中的学生禁止直接换岗/退岗" not in students:
    errors.append("direct active-position mutation is not blocked")
'''
        addition = anchor + '''if "allow_active_change" in students:
    errors.append("active-position bypass parameter remains in public service")
'''
        text = replace_once(text, anchor, addition, "production checker bypass")
    write(rel, text)


def main() -> None:
    patch_direct_position_api()
    patch_complaint_scope_and_confidentiality()
    add_tests()
    patch_contract_checker()
    for rel in CHANGED:
        if rel.endswith(".py"):
            ast.parse(read(rel), filename=rel)
    print("changed files:")
    for rel in CHANGED:
        print(f" - {rel}")
    if not CHANGED:
        print("review closeout already applied")


if __name__ == "__main__":
    main()
