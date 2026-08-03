from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGED: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != text:
        path.write_text(text, encoding="utf-8")
        CHANGED.append(rel)


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, got {count}")
    return text.replace(old, new, 1)


def function_block(text: str, name: str) -> tuple[int, int, str]:
    match = re.search(rf"(?ms)^def {re.escape(name)}\(.*?(?=^def |\Z)", text)
    if not match:
        raise RuntimeError(f"function not found: {name}")
    return match.start(), match.end(), match.group(0)


def replace_function(text: str, name: str, new_block: str) -> str:
    start, end, _ = function_block(text, name)
    return text[:start] + new_block.rstrip() + "\n\n\n" + text[end:].lstrip("\n")


def class_block(text: str, name: str) -> tuple[int, int, str]:
    match = re.search(rf"(?ms)^class {re.escape(name)}\b.*?(?=^class |\Z)", text)
    if not match:
        raise RuntimeError(f"class not found: {name}")
    return match.start(), match.end(), match.group(0)


def replace_class(text: str, name: str, block: str) -> str:
    start, end, _ = class_block(text, name)
    return text[:start] + block.rstrip() + "\n\n\n" + text[end:].lstrip("\n")


def patch_student_portal_uploads() -> None:
    rel = "student-portal/src/services/internshipCoreApi.js"
    text = read(rel)
    text = text.replace(
        "uploadFile('/files/upload?bizType=INTERNSHIP_APPLICATION_EVIDENCE', file)",
        "uploadFile('/files?bizType=INTERNSHIP_APPLICATION_EVIDENCE', file)",
    )
    text = text.replace(
        "uploadFile('/files/upload?bizType=INTERNSHIP_INSURANCE_POLICY', file)",
        "uploadFile('/files?bizType=INTERNSHIP_INSURANCE_POLICY', file)",
    )
    if "/files/upload?bizType=INTERNSHIP_" in text:
        raise RuntimeError("legacy internship upload path remains")
    write(rel, text)


def patch_models() -> None:
    rel = "backend/app/models/internship.py"
    text = read(rel)

    _, _, complaint = class_block(text, "InternshipComplaint")
    if "internship_id:" not in complaint:
        complaint = replace_once(
            complaint,
            "    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)\n",
            "    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)\n"
            "    internship_id: Mapped[int | None] = mapped_column(\n"
            "        BigInteger, index=True, comment=\"投诉明确关联的实习主记录；禁止按最新记录猜测\")\n",
            label="complaint internship id",
        )
    if "complainant_contact_hash" not in complaint:
        complaint = replace_once(
            complaint,
            "    complainant_contact_encrypted: Mapped[str | None] = mapped_column(String(200), comment=\"投诉人联系方式(敏感,密文)\")\n",
            "    complainant_contact_encrypted: Mapped[str | None] = mapped_column(\n"
            "        String(500), comment=\"投诉人联系方式(敏感,Fernet密文)\")\n"
            "    complainant_contact_hash: Mapped[str | None] = mapped_column(\n"
            "        String(64), index=True, comment=\"投诉人联系方式HMAC检索摘要\")\n",
            label="complaint contact hash",
        )
    text = replace_class(text, "InternshipComplaint", complaint)

    _, _, risk = class_block(text, "RiskRecord")
    if "uk_risk_source" not in risk:
        risk = replace_once(
            risk,
            "    __tablename__ = \"t_risk_record\"\n",
            "    __tablename__ = \"t_risk_record\"\n"
            "    __table_args__ = (\n"
            "        UniqueConstraint(\"tenant_id\", \"source_type\", \"source_id\", \"risk_code\",\n"
            "                         name=\"uk_risk_source\"),\n"
            "        Index(\"ix_risk_source\", \"tenant_id\", \"source_type\", \"source_id\"),\n"
            "    )\n",
            label="risk source constraints",
        )
    if "source_type:" not in risk:
        risk = replace_once(
            risk,
            "    source_module: Mapped[str] = mapped_column(String(50), nullable=False, default=\"system\",\n                                               comment=\"system/manual\")\n",
            "    source_module: Mapped[str] = mapped_column(String(50), nullable=False, default=\"system\",\n"
            "                                               comment=\"system/manual/complaint/internship_leave\")\n"
            "    source_type: Mapped[str | None] = mapped_column(\n"
            "        String(50), index=True, comment=\"来源单据类型，如 COMPLAINT/LEAVE\")\n"
            "    source_id: Mapped[int | None] = mapped_column(\n"
            "        BigInteger, index=True, comment=\"来源单据主键\")\n"
            "    source_version: Mapped[int | None] = mapped_column(\n"
            "        Integer, comment=\"创建风险时来源单据版本\")\n",
            label="risk source fields",
        )
    text = replace_class(text, "RiskRecord", risk)

    for class_name, constraint_name in (
        ("InternshipFinalScore", "uk_internship_final_score_record"),
        ("InternshipArchive", "uk_internship_archive_record"),
    ):
        _, _, block = class_block(text, class_name)
        if constraint_name not in block:
            table_match = re.search(r'(?m)^    __tablename__ = "([^"]+)"\n', block)
            if not table_match:
                raise RuntimeError(f"tablename not found for {class_name}")
            anchor = table_match.group(0)
            block = block.replace(
                anchor,
                anchor +
                "    __table_args__ = (\n"
                f"        UniqueConstraint(\"tenant_id\", \"internship_id\", name=\"{constraint_name}\"),\n"
                "    )\n",
                1,
            )
        text = replace_class(text, class_name, block)

    write(rel, text)


def patch_complaints() -> None:
    rel = "backend/app/modules/internship/services/internship_complaint_service.py"
    text = read(rel)
    if "from app.core.field_crypto import" not in text:
        text = replace_once(
            text,
            "from app.core.exceptions import AppException, no_permission, not_found\n",
            "from app.core.exceptions import AppException, no_permission, not_found\n"
            "from app.core.field_crypto import decrypt_sensitive, encrypt_sensitive, hash_sensitive\n",
            label="complaint crypto import",
        )
    text = replace_once(
        text,
        "    contact = c.complainant_contact_encrypted or \"\"\n",
        "    contact = decrypt_sensitive(\n"
        "        c.complainant_contact_encrypted, \"internship_complaint_contact\",\n"
        "        allow_legacy_plaintext=True) or \"\"\n",
        label="complaint decrypt",
    )

    create_block = '''def create_complaint(body, user=None):
    body = body or {}
    content = (body.get("content") or "").strip()
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "投诉内容不少于 5 个字符")
    source = (body.get("source") or "STUDENT").upper()
    severity = (body.get("severity") or "MEDIUM").upper()
    if severity not in ("LOW", "MEDIUM", "HIGH"):
        raise AppException("VALIDATION_ERROR", "严重级别不合法")
    contact_plain = str(body.get("complainantContact") or "").strip()
    with session() as db:
        internship_id = int(body["internshipId"]) if body.get("internshipId") else None
        student_id = int(body["studentId"]) if body.get("studentId") else None
        batch_id = int(body["batchId"]) if body.get("batchId") else None
        rec = None
        if internship_id:
            rec = db.scalar(select(InternshipRecord).where(
                InternshipRecord.id == internship_id,
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.is_deleted.is_(False)))
            if not rec:
                raise not_found("关联实习记录不存在或不在当前租户")
            if student_id and rec.student_id != student_id:
                raise AppException("DATA_CONFLICT", "投诉学生与实习记录不一致")
            if batch_id and rec.batch_id != batch_id:
                raise AppException("DATA_CONFLICT", "投诉批次与实习记录不一致")
            student_id, batch_id = rec.student_id, rec.batch_id
        elif student_id:
            if not batch_id:
                raise AppException("VALIDATION_ERROR", "关联学生投诉必须明确 internshipId 或 batchId")
            rec = db.scalar(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.student_id == student_id,
                InternshipRecord.batch_id == batch_id,
                InternshipRecord.is_deleted.is_(False)))
            if not rec:
                raise not_found("该学生在所选批次下无实习记录")
            internship_id = rec.id
        if student_id:
            from app.modules.internship.services.internship_service import assert_student_in_scope
            assert_student_in_scope(db, student_id, user, "该学生不在你的数据范围内，无法登记投诉")
        else:
            from app.modules.internship.services.internship_service import assert_admin_tenant
            assert_admin_tenant(user, "登记无关联学生的企业投诉")
        c = InternshipComplaint(
            tenant_id=_tid(), source=source,
            target_type=(body.get("targetType") or "").upper() or None,
            enterprise_id=int(body["enterpriseId"]) if body.get("enterpriseId") else None,
            position_id=int(body["positionId"]) if body.get("positionId") else None,
            student_id=student_id, internship_id=internship_id, batch_id=batch_id,
            category=(body.get("category") or "").strip() or None,
            severity=severity, content=content,
            evidence_file_id=(body.get("evidenceFileId") or "").strip() or None,
            complainant_contact_encrypted=encrypt_sensitive(
                contact_plain, "internship_complaint_contact") if contact_plain else None,
            complainant_contact_hash=hash_sensitive(
                contact_plain, "internship_complaint_contact") if contact_plain else None,
            confidential_level=(body.get("confidentialLevel") or "NORMAL").upper(),
            status="RECEIVED", created_by=None)
        db.add(c)
        db.flush()
        c.complaint_no = f"CPL-{datetime.utcnow():%Y%m}-{c.id:05d}"
        _trail(db, c.id, "CREATE", {
            "source": source, "severity": severity,
            "internshipId": str(internship_id or ""), "contactEncrypted": bool(contact_plain),
        }, user)
        db.commit()
        return _row(c, user)
'''
    text = replace_function(text, "create_complaint", create_block)

    risk_block = '''def to_risk(cid, user=None):
    with session() as db:
        c = db.scalar(select(InternshipComplaint).where(
            InternshipComplaint.id == _as_id(cid),
            InternshipComplaint.tenant_id == _tid(),
            InternshipComplaint.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("投诉不存在或不在当前数据范围内")
        _assert_complaint_writable(db, c, user, "该投诉不在你的可写范围内")
        if c.risk_id:
            raise AppException("DATA_CONFLICT", "该投诉已转风险单")
        if c.status in ("WITHDRAWN", "CLOSED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "已撤回/关闭/不成立的投诉不可转风险")
        if not c.student_id:
            raise AppException("DATA_CONFLICT", "仅关联学生的投诉可转风险单")
        rec = None
        if c.internship_id:
            rec = db.scalar(select(InternshipRecord).where(
                InternshipRecord.id == c.internship_id,
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.student_id == c.student_id,
                InternshipRecord.is_deleted.is_(False)).with_for_update())
        elif c.batch_id:
            rec = db.scalar(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.student_id == c.student_id,
                InternshipRecord.batch_id == c.batch_id,
                InternshipRecord.is_deleted.is_(False)).with_for_update())
            if rec:
                c.internship_id = rec.id
        if not rec:
            raise not_found("投诉未精确关联实习记录，禁止按学生最新记录猜测转风险")
        risk_code = f"INT-CPL-{c.id}"
        existing = db.scalar(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(),
            RiskRecord.source_type == "COMPLAINT",
            RiskRecord.source_id == c.id,
            RiskRecord.risk_code == risk_code,
            RiskRecord.is_deleted.is_(False)).with_for_update())
        if existing:
            c.risk_id = existing.id
            db.commit()
            return _row(c, user)
        risk = RiskRecord(
            tenant_id=_tid(), internship_id=rec.id, risk_code=risk_code,
            risk_title=f"企业投诉转风险：{c.category or '企业投诉'}",
            risk_level=c.severity or "MEDIUM", source_module="complaint",
            source_type="COMPLAINT", source_id=c.id,
            source_version=int(c.version or 0),
            owner_name=c.owner_name or _op_name(user), status="PENDING_HANDLE")
        db.add(risk)
        db.flush()
        c.risk_id = risk.id
        if c.status in ("RECEIVED", "ACCEPTED"):
            c.status = "INVESTIGATING"
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "TO_RISK", {
            "riskId": str(risk.id), "internshipId": str(rec.id),
            "sourceVersion": int(risk.source_version or 0),
        }, user)
        db.commit()
        return _row(c, user)
'''
    text = replace_function(text, "to_risk", risk_block)
    write(rel, text)


def patch_position_archive_guard() -> None:
    rel = "backend/app/modules/internship/services/internship_position_service.py"
    text = read(rel)
    old = '''        elif action == "ARCHIVE":
            p.status = "ARCHIVED"
            p.archived_at = datetime.utcnow()
            p.archived_by = _op_name()
'''
    new = '''        elif action == "ARCHIVE":
            active_count = int(db.scalar(select(func.count()).select_from(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.position_id == p.id,
                InternshipRecord.status.in_(("PREPARING", "READY", "ONBOARD", "ASSESSING")),
                InternshipRecord.is_deleted.is_(False))) or 0)
            if int(p.allocated_count or 0) > 0 or active_count > 0:
                raise AppException(
                    "DATA_CONFLICT",
                    f"岗位仍有 {max(int(p.allocated_count or 0), active_count)} 名有效学生，不可归档；请先完成正式调岗/退岗")
            p.status = "ARCHIVED"
            p.archived_at = datetime.utcnow()
            p.archived_by = _op_name()
'''
    if old in text:
        text = replace_once(text, old, new, label="position archive guard")
    elif "岗位仍有" not in text:
        raise RuntimeError("position archive anchor missing")
    write(rel, text)


def patch_direct_assignment_guard() -> None:
    rel = "backend/app/modules/internship/services/internship_student_service.py"
    text = read(rel)
    if "def _assert_direct_position_change_allowed" not in text:
        anchor = "\ndef assign_position(rec_id, position_id, expected_version=None, user=None) -> dict:\n"
        helper = '''
def _assert_direct_position_change_allowed(record: InternshipRecord, *, allow_active_change: bool) -> None:
    if record.status in ("ONBOARD", "ASSESSING") and not allow_active_change:
        raise AppException(
            "DATA_CONFLICT",
            "在岗或考核中的学生禁止直接换岗/退岗，请通过实习变更申请审批流程办理",
        )


def assign_position(rec_id, position_id, expected_version=None, user=None, *, allow_active_change=False) -> dict:
'''
        text = replace_once(text, anchor, "\n" + helper, label="assignment guard helper")
    start, end, block = function_block(text, "assign_position")
    if "_assert_direct_position_change_allowed" not in block:
        block = replace_once(
            block,
            "        assign_position_in_tx(db, r, position_id, expected_version, user)\n",
            "        _assert_direct_position_change_allowed(\n"
            "            r, allow_active_change=bool(allow_active_change))\n"
            "        assign_position_in_tx(db, r, position_id, expected_version, user)\n",
            label="assign active guard",
        )
        text = text[:start] + block + text[end:]
    text = text.replace(
        "def unassign_position(rec_id, reason: str = \"\", expected_version=None, user=None) -> dict:",
        "def unassign_position(rec_id, reason: str = \"\", expected_version=None, user=None, *, allow_active_change=False) -> dict:",
        1,
    )
    start, end, block = function_block(text, "unassign_position")
    if "allow_active_change=bool(allow_active_change)" not in block:
        marker = "        ver = extract_expected_version({\"expectedVersion\": expected_version})\n"
        if marker not in block:
            raise RuntimeError("unassign version anchor missing")
        block = block.replace(
            marker,
            "        _assert_direct_position_change_allowed(\n"
            "            r, allow_active_change=bool(allow_active_change))\n" + marker,
            1,
        )
        text = text[:start] + block + text[end:]
    write(rel, text)

    rel = "backend/app/modules/internship/services/internship_change_service.py"
    text = read(rel)
    text = text.replace(
        "stu_svc.unassign_position(rid, reason or \"退岗审核通过\", user=user)",
        "stu_svc.unassign_position(\n                    rid, reason or \"退岗审核通过\", user=user, allow_active_change=True)",
    )
    text = text.replace(
        "stu_svc.assign_position(rid, str(tpid), user=user)",
        "stu_svc.assign_position(\n                    rid, str(tpid), user=user, allow_active_change=True)",
    )
    write(rel, text)


def patch_leave_risk_binding() -> None:
    rel = "backend/app/modules/internship/services/internship_leave_service.py"
    text = read(rel)
    text = text.replace(
        '''            RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == lv.internship_id,
            RiskRecord.risk_code == "INT-R06",
''',
        '''            RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == lv.internship_id,
            RiskRecord.source_type == "LEAVE", RiskRecord.source_id == lv.id,
            RiskRecord.risk_code == "INT-R06",
''',
    )
    text = text.replace(
        '''                RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == lv.internship_id,
                RiskRecord.risk_code == "INT-R06", RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
''',
        '''                RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == lv.internship_id,
                RiskRecord.source_type == "LEAVE", RiskRecord.source_id == lv.id,
                RiskRecord.risk_code == "INT-R06", RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
''',
    )
    text = text.replace(
        '''                db.add(RiskRecord(tenant_id=_tid(), internship_id=lv.internship_id, risk_code="INT-R06",
                                  risk_title="实习请假超期未销假", risk_level="MEDIUM",
                                  source_module="internship_leave", status="PENDING_HANDLE",
''',
        '''                db.add(RiskRecord(tenant_id=_tid(), internship_id=lv.internship_id, risk_code="INT-R06",
                                  risk_title="实习请假超期未销假", risk_level="MEDIUM",
                                  source_module="internship_leave", source_type="LEAVE", source_id=lv.id,
                                  source_version=int(lv.version or 0), status="PENDING_HANDLE",
''',
    )
    write(rel, text)

    rel = "backend/app/modules/internship/services/internship_student_leave_context_service.py"
    text = read(rel)
    old = '''            RiskRecord.tenant_id == _tid(),
            RiskRecord.internship_id == row.internship_id,
            RiskRecord.risk_code == "INT-R06",
'''
    new = '''            RiskRecord.tenant_id == _tid(),
            RiskRecord.internship_id == row.internship_id,
            RiskRecord.source_type == "LEAVE",
            RiskRecord.source_id == row.id,
            RiskRecord.risk_code == "INT-R06",
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "RiskRecord.source_id == row.id" not in text:
        raise RuntimeError("versioned leave risk anchor missing")
    write(rel, text)


def patch_score_lock() -> None:
    rel = "backend/app/modules/internship/services/internship_score_service.py"
    text = read(rel)
    start, end, block = function_block(text, "compute")
    old = "        rec = db.get(InternshipRecord, _as_id(iid))\n"
    new = '''        rec = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == _as_id(iid),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False)).with_for_update())
'''
    if old in block:
        block = block.replace(old, new, 1)
    elif "with_for_update()" not in block:
        raise RuntimeError("score record lock anchor missing")
    text = text[:start] + block + text[end:]
    write(rel, text)


def detect_migration_dir() -> Path:
    candidates = [
        ROOT / "backend/alembic/versions",
        ROOT / "backend/migrations/versions",
    ]
    for path in candidates:
        if path.exists():
            return path
    found = list((ROOT / "backend").glob("**/versions"))
    found = [p for p in found if any(p.glob("*.py"))]
    if len(found) != 1:
        raise RuntimeError(f"cannot resolve migration directory: {found}")
    return found[0]


def detect_alembic_head(path: Path) -> str:
    revisions: set[str] = set()
    referenced: set[str] = set()
    for file in path.glob("*.py"):
        text = file.read_text(encoding="utf-8")
        rev = re.search(r'(?m)^revision(?:\s*:[^=]+)?\s*=\s*["\']([^"\']+)', text)
        if rev:
            revisions.add(rev.group(1))
        down = re.search(r'(?m)^down_revision(?:\s*:[^=]+)?\s*=\s*(.+)$', text)
        if down:
            referenced.update(re.findall(r'["\']([^"\']+)["\']', down.group(1)))
    heads = sorted(revisions - referenced)
    if len(heads) != 1:
        raise RuntimeError(f"expected one alembic head, got {heads}")
    return heads[0]


def add_migration() -> None:
    path = detect_migration_dir()
    revision = "20260803_internship_prod_hardening"
    target = path / f"{revision}.py"
    if target.exists():
        return
    down = detect_alembic_head(path)
    migration = f'''"""internship production data invariants and sensitive-field hardening.

Revision ID: {revision}
Revises: {down}
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "{revision}"
down_revision = "{down}"
branch_labels = None
depends_on = None


def _soft_delete_duplicates(table: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        f"SELECT tenant_id, internship_id, MAX(id) AS keep_id FROM {{table}} "
        "WHERE is_deleted = 0 GROUP BY tenant_id, internship_id HAVING COUNT(*) > 1"
    )).mappings().all()
    for row in rows:
        bind.execute(sa.text(
            f"UPDATE {{table}} SET is_deleted = 1 WHERE tenant_id = :tenant_id "
            "AND internship_id = :internship_id AND id <> :keep_id AND is_deleted = 0"
        ), dict(row))


def upgrade() -> None:
    op.add_column("t_internship_complaint", sa.Column("internship_id", sa.BigInteger(), nullable=True))
    op.add_column("t_internship_complaint", sa.Column("complainant_contact_hash", sa.String(64), nullable=True))
    op.create_index("ix_internship_complaint_internship_id", "t_internship_complaint", ["internship_id"])
    op.create_index("ix_internship_complaint_contact_hash", "t_internship_complaint", ["complainant_contact_hash"])

    op.add_column("t_risk_record", sa.Column("source_type", sa.String(50), nullable=True))
    op.add_column("t_risk_record", sa.Column("source_id", sa.BigInteger(), nullable=True))
    op.add_column("t_risk_record", sa.Column("source_version", sa.Integer(), nullable=True))
    op.create_index("ix_risk_source", "t_risk_record", ["tenant_id", "source_type", "source_id"])

    bind = op.get_bind()
    complaints = bind.execute(sa.text(
        "SELECT id, student_id, batch_id, complainant_contact_encrypted "
        "FROM t_internship_complaint"
    )).mappings().all()
    from app.core.field_crypto import encrypt_sensitive, hash_sensitive, looks_like_fernet
    for row in complaints:
        values = {{}}
        contact = row["complainant_contact_encrypted"]
        if contact:
            plain = str(contact)
            if not looks_like_fernet(plain):
                values["encrypted"] = encrypt_sensitive(plain, "internship_complaint_contact")
            values["contact_hash"] = hash_sensitive(plain, "internship_complaint_contact")
        if row["student_id"] and row["batch_id"]:
            rec = bind.execute(sa.text(
                "SELECT id FROM t_internship_record WHERE tenant_id = "
                "(SELECT tenant_id FROM t_internship_complaint WHERE id=:id) "
                "AND student_id=:student_id AND batch_id=:batch_id AND is_deleted=0 LIMIT 1"
            ), row).scalar()
            if rec:
                values["internship_id"] = rec
        if values:
            bind.execute(sa.text(
                "UPDATE t_internship_complaint SET "
                "complainant_contact_encrypted=COALESCE(:encrypted, complainant_contact_encrypted), "
                "complainant_contact_hash=COALESCE(:contact_hash, complainant_contact_hash), "
                "internship_id=COALESCE(:internship_id, internship_id) WHERE id=:id"
            ), {{"id": row["id"], "encrypted": values.get("encrypted"),
                 "contact_hash": values.get("contact_hash"),
                 "internship_id": values.get("internship_id")}})

    bind.execute(sa.text(
        "UPDATE t_risk_record SET source_type='COMPLAINT', "
        "source_id=CAST(SUBSTRING(risk_code, 9) AS UNSIGNED), source_version=0, "
        "source_module='complaint' WHERE risk_code LIKE 'INT-CPL-%' AND source_id IS NULL"
    ))

    _soft_delete_duplicates("t_internship_final_score")
    _soft_delete_duplicates("t_internship_archive")
    op.create_unique_constraint(
        "uk_internship_final_score_record", "t_internship_final_score",
        ["tenant_id", "internship_id"])
    op.create_unique_constraint(
        "uk_internship_archive_record", "t_internship_archive",
        ["tenant_id", "internship_id"])
    op.create_unique_constraint(
        "uk_risk_source", "t_risk_record",
        ["tenant_id", "source_type", "source_id", "risk_code"])


def downgrade() -> None:
    op.drop_constraint("uk_risk_source", "t_risk_record", type_="unique")
    op.drop_constraint("uk_internship_archive_record", "t_internship_archive", type_="unique")
    op.drop_constraint("uk_internship_final_score_record", "t_internship_final_score", type_="unique")
    op.drop_index("ix_risk_source", table_name="t_risk_record")
    op.drop_column("t_risk_record", "source_version")
    op.drop_column("t_risk_record", "source_id")
    op.drop_column("t_risk_record", "source_type")
    op.drop_index("ix_internship_complaint_contact_hash", table_name="t_internship_complaint")
    op.drop_index("ix_internship_complaint_internship_id", table_name="t_internship_complaint")
    op.drop_column("t_internship_complaint", "complainant_contact_hash")
    op.drop_column("t_internship_complaint", "internship_id")
'''
    write(str(target.relative_to(ROOT)), migration)


def add_contract_gate() -> None:
    rel = "scripts/check/check-internship-production-contracts.py"
    content = '''from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
errors = []

for rel in (
    "student-portal/src/services/internshipCoreApi.js",
    "miniapp/src/services/internshipApi.js",
    "frontend/src/modules/internship/api/internship.api.js",
):
    text = (ROOT / rel).read_text(encoding="utf-8")
    if "/files/upload" in text:
        errors.append(f"{rel}: references removed /files/upload endpoint")

models = (ROOT / "backend/app/models/internship.py").read_text(encoding="utf-8")
for token in (
    "complainant_contact_hash", "source_type", "source_id",
    "uk_risk_source", "uk_internship_final_score_record",
    "uk_internship_archive_record",
):
    if token not in models:
        errors.append(f"internship model missing invariant: {token}")

complaints = (ROOT / "backend/app/modules/internship/services/internship_complaint_service.py").read_text(encoding="utf-8")
for token in (
    "encrypt_sensitive", "decrypt_sensitive", "complainant_contact_hash",
    "投诉未精确关联实习记录", 'source_type="COMPLAINT"',
):
    if token not in complaints:
        errors.append(f"complaint hardening missing: {token}")

students = (ROOT / "backend/app/modules/internship/services/internship_student_service.py").read_text(encoding="utf-8")
if "在岗或考核中的学生禁止直接换岗/退岗" not in students:
    errors.append("direct active-position mutation is not blocked")

positions = (ROOT / "backend/app/modules/internship/services/internship_position_service.py").read_text(encoding="utf-8")
if "请先完成正式调岗/退岗" not in positions:
    errors.append("occupied positions can still be archived")

if errors:
    raise SystemExit("\\n".join(f"ERROR: {item}" for item in errors))
print("internship production contracts: OK")
'''
    write(rel, content)

    ci_rel = ".github/workflows/ci.yml"
    ci = read(ci_rel)
    marker = "      - name: 岗位实习专项测试（20分钟硬超时）\n        run: timeout 20m pytest tests/test_internship*.py -q -p no:warnings --durations=20\n"
    addition = marker + "      - name: 岗位实习静态生产合同\n        working-directory: ..\n        run: python scripts/check/check-internship-production-contracts.py\n"
    if "check-internship-production-contracts.py" not in ci:
        ci = replace_once(ci, marker, addition, label="CI internship contract gate")
    write(ci_rel, ci)


def add_tests() -> None:
    rel = "backend/tests/test_internship_production_hardening_static.py"
    content = '''from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_student_portal_uses_authoritative_file_upload_route():
    text = _read("student-portal/src/services/internshipCoreApi.js")
    assert "/files/upload" not in text
    assert "/files?bizType=INTERNSHIP_APPLICATION_EVIDENCE" in text
    assert "/files?bizType=INTERNSHIP_INSURANCE_POLICY" in text


def test_complaint_contact_is_encrypted_and_risk_source_is_exact():
    text = _read("backend/app/modules/internship/services/internship_complaint_service.py")
    assert "encrypt_sensitive" in text
    assert "decrypt_sensitive" in text
    assert "complainant_contact_hash" in text
    assert "投诉未精确关联实习记录" in text
    assert 'source_type="COMPLAINT"' in text
    assert "order_by(InternshipRecord.id.desc())" not in text[text.index("def to_risk"):text.index("def followup")]


def test_active_students_cannot_bypass_change_workflow():
    text = _read("backend/app/modules/internship/services/internship_student_service.py")
    assert "在岗或考核中的学生禁止直接换岗/退岗" in text
    change = _read("backend/app/modules/internship/services/internship_change_service.py")
    assert change.count("allow_active_change=True") >= 2


def test_leave_risks_are_bound_to_leave_id():
    legacy = _read("backend/app/modules/internship/services/internship_leave_service.py")
    versioned = _read("backend/app/modules/internship/services/internship_student_leave_context_service.py")
    assert 'source_type="LEAVE"' in legacy
    assert "RiskRecord.source_id == lv.id" in legacy
    assert "RiskRecord.source_id == row.id" in versioned


def test_core_database_invariants_are_declared():
    model = _read("backend/app/models/internship.py")
    assert "uk_risk_source" in model
    assert "uk_internship_final_score_record" in model
    assert "uk_internship_archive_record" in model
'''
    write(rel, content)


def syntax_check() -> None:
    for rel in CHANGED:
        if rel.endswith(".py"):
            ast.parse(read(rel), filename=rel)


def main() -> None:
    patch_student_portal_uploads()
    patch_models()
    patch_complaints()
    patch_position_archive_guard()
    patch_direct_assignment_guard()
    patch_leave_risk_binding()
    patch_score_lock()
    add_migration()
    add_contract_gate()
    add_tests()
    syntax_check()
    print("changed files:")
    for rel in CHANGED:
        print(f" - {rel}")
    if not CHANGED:
        raise SystemExit("no changes applied")


if __name__ == "__main__":
    main()
