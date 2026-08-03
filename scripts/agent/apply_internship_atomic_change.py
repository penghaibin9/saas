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
    old = path.read_text(encoding="utf-8")
    if old != text:
        path.write_text(text, encoding="utf-8")
        CHANGED.append(rel)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, got {count}")
    return text.replace(old, new, 1)


def replace_function(text: str, name: str, block: str) -> str:
    match = re.search(rf"(?ms)^def {re.escape(name)}\(.*?(?=^def |\Z)", text)
    if not match:
        raise RuntimeError(f"function not found: {name}")
    return text[:match.start()] + block.rstrip() + "\n\n\n" + text[match.end():].lstrip("\n")


def patch_model_and_migration() -> None:
    rel = "backend/app/models/internship.py"
    text = read(rel)
    if "record_version_snapshot" not in text:
        text = replace_once(
            text,
            "    target_position_name: Mapped[str | None] = mapped_column(String(100))\n"
            "    status: Mapped[str] = mapped_column(String(20), nullable=False, default=\"PENDING\",\n",
            "    target_position_name: Mapped[str | None] = mapped_column(String(100))\n"
            "    record_version_snapshot: Mapped[int] = mapped_column(\n"
            "        Integer, nullable=False, default=0, comment=\"申请时实习主记录版本\")\n"
            "    status: Mapped[str] = mapped_column(String(20), nullable=False, default=\"PENDING\",\n",
            "change record version model",
        )
    write(rel, text)

    rel = "backend/alembic/versions/20260803_internship_prod_hardening.py"
    text = read(rel)
    if "record_version_snapshot" not in text:
        text = replace_once(
            text,
            "    op.create_index(\"ix_risk_source\", \"t_risk_record\", [\"tenant_id\", \"source_type\", \"source_id\"])\n\n"
            "    bind = op.get_bind()\n",
            "    op.create_index(\"ix_risk_source\", \"t_risk_record\", [\"tenant_id\", \"source_type\", \"source_id\"])\n\n"
            "    op.add_column(\"t_internship_change_request\", sa.Column(\n"
            "        \"record_version_snapshot\", sa.Integer(), nullable=True))\n\n"
            "    bind = op.get_bind()\n"
            "    bind.execute(sa.text(\n"
            "        \"UPDATE t_internship_change_request c \"\n"
            "        \"JOIN t_internship_record r ON r.id=c.internship_id AND r.tenant_id=c.tenant_id \"\n"
            "        \"SET c.record_version_snapshot=COALESCE(r.version, 0) \"\n"
            "        \"WHERE c.record_version_snapshot IS NULL\"\n"
            "    ))\n"
            "    op.alter_column(\"t_internship_change_request\", \"record_version_snapshot\",\n"
            "                    existing_type=sa.Integer(), nullable=False, server_default=\"0\")\n",
            "change snapshot migration",
        )
        text = replace_once(
            text,
            "def downgrade() -> None:\n",
            "def downgrade() -> None:\n"
            "    op.drop_column(\"t_internship_change_request\", \"record_version_snapshot\")\n",
            "change snapshot downgrade",
        )
    write(rel, text)


def patch_change_creation() -> None:
    for rel, record_name in (
        ("backend/app/modules/internship/services/internship_change_service.py", "rec"),
        ("backend/app/modules/internship/services/internship_student_change_context_service.py", "record"),
    ):
        text = read(rel)
        if "record_version_snapshot=" not in text:
            anchor = "            status=\"PENDING\")" if record_name == "rec" else "            status=\"PENDING\",\n        )"
            replacement = (
                f"            record_version_snapshot=int({record_name}.version or 0),\n"
                "            status=\"PENDING\")"
                if record_name == "rec" else
                f"            record_version_snapshot=int({record_name}.version or 0),\n"
                "            status=\"PENDING\",\n        )"
            )
            text = replace_once(text, anchor, replacement, f"{rel} snapshot creation")
        write(rel, text)


def patch_student_position_tx() -> None:
    rel = "backend/app/modules/internship/services/internship_student_service.py"
    text = read(rel)
    helper = '''def unassign_position_in_tx(db, record: InternshipRecord, expected_version=None,
                            reason: str = "", user=None, *, next_status: str | None = None):
    """Within the caller transaction, release the current position and clear destination fields."""
    from sqlalchemy import text
    from app.modules.internship.services.internship_version import extract_expected_version

    ver = extract_expected_version({"expectedVersion": expected_version})
    if int(record.version or 0) != ver:
        raise AppException("DATA_CONFLICT", "实习学生记录已被其他用户修改，请刷新后重试")
    _assert_write_scope(db, record, user)
    if not record.position_id:
        raise AppException("DATA_CONFLICT", "该学生未分配岗位")
    old_id = record.position_id
    locked = db.execute(text(
        "SELECT id FROM t_internship_position WHERE id = :pid AND tenant_id = :tid "
        "AND is_deleted = 0 FOR UPDATE"
    ), {"pid": old_id, "tid": _tid()}).first()
    if not locked:
        raise AppException("DATA_CONFLICT", "原岗位不存在或已删除，无法安全释放名额")
    db.execute(text(_RELEASE_SQL), {"pid": old_id, "tid": _tid()})
    record.position_id = None
    record.enterprise_id = None
    record.mentor_contact_id = None
    record.position_name = None
    record.enterprise_name = None
    record.enterprise_mentor_name = None
    record.destination_type = "NONE"
    if next_status:
        record.status = next_status
    record.version = ver + 1
    _trail(db, record.id, "UNASSIGN_POSITION", {
        "reason": reason, "fromPositionId": str(old_id),
        "recordVersion": int(record.version or 0), "nextStatus": next_status or record.status,
    })
    return record
'''
    if "def unassign_position_in_tx" not in text:
        marker = "def unassign_position(rec_id, reason: str = \"\", expected_version=None, user=None, *, allow_active_change=False) -> dict:\n"
        text = replace_once(text, marker, helper + "\n\n" + marker, "unassign tx helper")

    public = '''def unassign_position(rec_id, reason: str = "", expected_version=None, user=None,
                      *, allow_active_change=False) -> dict:
    with session() as db:
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == _as_id(rec_id),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False)).with_for_update())
        if not record:
            raise not_found("实习学生记录不存在或不在当前数据范围内")
        _assert_direct_position_change_allowed(
            record, allow_active_change=bool(allow_active_change))
        unassign_position_in_tx(
            db, record, expected_version, reason, user=user)
        db.commit()
        return _row_of(db, record)
'''
    text = replace_function(text, "unassign_position", public)
    write(rel, text)


def patch_change_service() -> None:
    rel = "backend/app/modules/internship/services/internship_change_service.py"
    text = read(rel)
    text = text.replace("from sqlalchemy import select", "from sqlalchemy import func, or_, select", 1)
    text = text.replace(
        "from app.models import InternshipAuditTrail, InternshipChangeRequest, InternshipRecord, StudentProfile",
        "from app.models import (InternshipAgreement, InternshipAuditTrail, InternshipChangeRequest,\n"
        "                        InternshipRecord, StudentProfile)",
        1,
    )
    if '"recordVersionSnapshot"' not in text:
        text = replace_once(
            text,
            '        "version": int(c.version or 0),\n        "createdAt": _iso(c.created_at) or "",\n',
            '        "version": int(c.version or 0),\n'
            '        "recordVersion": int(rec.version or 0) if rec else None,\n'
            '        "recordVersionSnapshot": int(c.record_version_snapshot or 0),\n'
            '        "createdAt": _iso(c.created_at) or "",\n',
            "change row versions",
        )

    list_block = '''def list_changes(page, page_size, status=None, keyword=None, batch_id=None, user=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped_records = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipChangeRequest, InternshipRecord, StudentProfile).join(
            InternshipRecord,
            InternshipRecord.id == InternshipChangeRequest.internship_id,
        ).join(
            StudentProfile,
            StudentProfile.id == InternshipChangeRequest.student_id,
        ).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False),
            InternshipChangeRequest.internship_id.in_(select(scoped_records.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            query = query.where(InternshipChangeRequest.status == status)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipChangeRequest.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size)
            .limit(size)
        ).all()
        return [_row(change, record, student) for change, record, student in rows], total
'''
    text = replace_function(text, "list_changes", list_block)

    review_tail = '''def _void_prior_compliance(db, record: InternshipRecord, change: InternshipChangeRequest,
                           user=None) -> None:
    """A destination change invalidates prior consent and active agreements in the same transaction."""
    from app.modules.internship.services.internship_consent_service import supersede_for_major_change

    supersede_for_major_change(db, record.id)
    agreements = db.scalars(select(InternshipAgreement).where(
        InternshipAgreement.tenant_id == _tid(),
        InternshipAgreement.internship_id == record.id,
        InternshipAgreement.status.in_((
            "DRAFT", "PENDING_STUDENT", "PENDING_ENTERPRISE", "PENDING_SCHOOL", "EFFECTIVE")),
        InternshipAgreement.is_deleted.is_(False),
    ).with_for_update()).all()
    for agreement in agreements:
        before = agreement.status
        agreement.status = "VOIDED"
        agreement.reject_reason = f"实习变更单 {change.id} 已通过，原协议失效并须重新办理"
        agreement.version = int(agreement.version or 0) + 1
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=agreement.id, target_type="AGREEMENT",
            action="VOID_BY_CHANGE", operator_name=_op_name(user),
            detail_json={"changeId": str(change.id), "beforeStatus": before},
            occurred_at=datetime.utcnow()))


def review_change(cid, action: str, comment: str = "", user=None, *, expected_version=None,
                  record_expected_version=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )

    action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    review_comment = str(comment or "").strip()
    if action == "REJECT" and len(review_comment) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    change_version = extract_expected_version({"expectedVersion": expected_version})

    with session() as db:
        change = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.id == _as_id(cid),
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False)).with_for_update())
        if not change:
            raise not_found("变更申请不存在")
        if change.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可处理")
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == change.internship_id,
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False)).with_for_update())
        if not record:
            raise not_found("实习主记录不存在")
        student = db.scalar(select(StudentProfile).where(
            StudentProfile.id == change.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False)))
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, record, student):
            raise no_permission("不在数据范围内")

        snapshot = int(change.record_version_snapshot or 0)
        expected_record = snapshot if record_expected_version is None else extract_expected_version(
            {"expectedVersion": record_expected_version})
        if expected_record != snapshot:
            raise AppException("DATA_CONFLICT", "页面实习记录版本与申请快照不一致，请刷新")
        if int(record.version or 0) != snapshot:
            raise AppException(
                "DATA_CONFLICT",
                "学生实习主记录在申请后已变化，请退回申请并由学生基于最新数据重新提交",
            )

        before = {
            "recordVersion": int(record.version or 0),
            "positionId": str(record.position_id or ""),
            "enterpriseId": str(record.enterprise_id or ""),
            "destinationType": record.destination_type,
            "status": record.status,
        }
        if action == "APPROVE":
            change_type = change.change_type
            if change_type in ("CHANGE_POSITION", "CHANGE_ENTERPRISE"):
                if not change.target_position_id:
                    label = "换单位" if change_type == "CHANGE_ENTERPRISE" else "换岗"
                    raise AppException("DATA_CONFLICT", f"{label}申请缺少目标岗位编号，不可通过")
                stu_svc.assign_position_in_tx(
                    db, record, change.target_position_id, snapshot, user=user)
            elif change_type == "WITHDRAW_POST":
                next_status = "READY" if record.eligibility_status == "QUALIFIED" else "PREPARING"
                stu_svc.unassign_position_in_tx(
                    db, record, snapshot, change.reason or "退岗审核通过",
                    user=user, next_status=next_status)
            elif change_type == "SELF_ARRANGED":
                enterprise_name = str(change.target_enterprise_name or "").strip()
                position_name = str(change.target_position_name or "").strip()
                if len(enterprise_name) < 2 or len(position_name) < 2:
                    raise AppException("DATA_CONFLICT", "转自主实习必须填写完整的目标单位和岗位")
                if record.position_id:
                    stu_svc.unassign_position_in_tx(
                        db, record, snapshot, change.reason or "转自主实习",
                        user=user)
                else:
                    record.version = snapshot + 1
                record.enterprise_id = None
                record.position_id = None
                record.mentor_contact_id = None
                record.enterprise_name = enterprise_name
                record.position_name = position_name
                record.enterprise_mentor_name = None
                record.destination_type = "SELF_ARRANGED"
                stu_svc._trail(db, record.id, "SET_SELF_ARRANGED_BY_CHANGE", {
                    "changeId": str(change.id), "recordVersion": int(record.version or 0),
                })
            else:
                raise AppException("VALIDATION_ERROR", "未知实习变更类型")
            _void_prior_compliance(db, record, change, user=user)

        status = "APPROVED" if action == "APPROVE" else "REJECTED"
        new_version = versioned_update(
            db, InternshipChangeRequest, entity_id=change.id, tenant_id=_tid(),
            expected_version=change_version, expected_status="PENDING",
            values={
                "status": status,
                "review_comment": review_comment or None,
                "reviewed_by_name": _op_name(user),
                "reviewed_at": datetime.utcnow(),
            },
        )
        _trail(db, change.id, action, {
            "comment": review_comment,
            "recordBefore": before,
            "recordAfter": {
                "recordVersion": int(record.version or 0),
                "positionId": str(record.position_id or ""),
                "enterpriseId": str(record.enterprise_id or ""),
                "destinationType": record.destination_type,
                "status": record.status,
            } if action == "APPROVE" else before,
            "atomic": True,
        }, operator=_op_name(user))
        db.commit()
        return {
            "id": str(change.id), "status": status,
            "statusLabel": STATUS_LABEL.get(status), "version": new_version,
            "recordVersion": int(record.version or 0),
        }
'''
    tail_match = re.search(r"(?ms)^def _exc_reason\(.*\Z", text)
    if not tail_match:
        if "def _void_prior_compliance" not in text:
            raise RuntimeError("change review tail anchor missing")
    else:
        text = text[:tail_match.start()] + review_tail.rstrip() + "\n"
    write(rel, text)


def add_static_tests() -> None:
    rel = "backend/tests/test_internship_atomic_change_static.py"
    path = ROOT / rel
    content = '''from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_change_approval_is_single_transaction_without_compensation():
    text = _read("backend/app/modules/internship/services/internship_change_service.py")
    block = text[text.index("def review_change"):]
    assert "_rollback_approved_change" not in text
    assert block.count("db.commit()") == 1
    assert "assign_position_in_tx" in block
    assert "unassign_position_in_tx" in block
    assert '"atomic": True' in block


def test_change_request_freezes_record_version():
    model = _read("backend/app/models/internship.py")
    assert "record_version_snapshot" in model
    legacy = _read("backend/app/modules/internship/services/internship_change_service.py")
    context = _read("backend/app/modules/internship/services/internship_student_change_context_service.py")
    assert "record_version_snapshot=int(rec.version or 0)" in legacy
    assert "record_version_snapshot=int(record.version or 0)" in context


def test_change_list_uses_database_pagination_and_scope():
    text = _read("backend/app/modules/internship/services/internship_change_service.py")
    block = text[text.index("def list_changes"):text.index("def get_change")]
    assert "apply_internship_record_scope" in block
    assert ".offset(" in block and ".limit(" in block
    assert "db.get(InternshipRecord" not in block
'''
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
        CHANGED.append(rel)


def main() -> None:
    patch_model_and_migration()
    patch_change_creation()
    patch_student_position_tx()
    patch_change_service()
    add_static_tests()
    for rel in CHANGED:
        if rel.endswith(".py"):
            ast.parse(read(rel), filename=rel)
    print("changed files:")
    for rel in CHANGED:
        print(f" - {rel}")
    if not CHANGED:
        print("atomic change patch already applied")


if __name__ == "__main__":
    main()
