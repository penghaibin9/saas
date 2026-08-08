"""免修材料证据链回归（P0-D06）。

免修终审直接生成一条正式的、计学分的及格成绩，材料就是这门学分的唯一依据。要守住两点：

1. 归属：学生 B 拿到学生 A 上传的 fileId，不能当成自己的免修依据；
2. 时效：提交时合规的材料，在审批期间被撤下、隔离或换掉内容，终审必须察觉并拒绝发学分。

复用既有文件中心（bind_file_to_business）而不是另造一套附件安全，因此这里同时验证
"确实是走了那条链路"（真的建出 ACTIVE FileBinding），而不只是自己记了一串 id。
MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

from datetime import datetime

import pytest

TID = 1000000000000000001


def _ctx(user_id=1, user_type="ADMIN", student_no=None):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    actor = {
        "userId": str(user_id), "tenantId": str(TID), "realName": "测试",
        "currentRoleCode": "ACADEMIC_ADMIN", "activeContextId": "ctx", "userType": user_type,
    }
    if student_no:
        actor["studentNo"] = student_no
    set_current_user(actor)
    return actor


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _file(db, *, owner, name="证书.pdf", digest="a" * 64, scan="CLEAN", status="AVAILABLE"):
    """通用上传产出的临时私有文件：尚未绑定任何正式业务对象。"""
    from app.models.file import FileObject

    row = FileObject(
        tenant_id=TID, file_key=f"exempt/{name}-{digest[:8]}", file_name=name, ext="pdf",
        mime_type="application/pdf", size_bytes=1024, sha256=digest,
        biz_type="TEMP_PRIVATE", biz_id=None, visibility="PRIVATE",
        security_level="INTERNAL", status=status, storage_backend="local",
        storage_zone="ACTIVE" if status == "AVAILABLE" else "QUARANTINE",
        upload_source="USER", owner_user_id=int(owner), created_by=int(owner),
        scan_required=scan != "NOT_REQUIRED", scan_status=scan,
        available_at=datetime.utcnow() if status == "AVAILABLE" else None,
    )
    db.add(row)
    db.flush()
    return row


def _student(db, *, student_no="EV2401", name="免甲"):
    from app.models import StudentProfile

    row = StudentProfile(tenant_id=TID, student_no=student_no, real_name=name,
                         grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(row)
    db.flush()
    return row


def _exemption(db, student, *, course_id=1, term_code="2024-2025-1"):
    from app.models import AaExemption

    row = AaExemption(
        tenant_id=TID, student_id=student.id, student_no=student.student_no,
        student_name=student.real_name, course_id=course_id, course_name="线性代数",
        term_code=term_code, current_node="TEACHER_REVIEW", status="TEACHER_REVIEW",
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture()
def evidence(db_mode):
    from app.modules.academic_affairs.services import (
        academic_affairs_exemption_evidence_service as svc,
    )

    return svc


def test_freeze_manifest_creates_real_file_binding(evidence, db_mode):
    """必须真的走文件中心建出 ACTIVE 绑定，而不是自己记一串 fileId。"""
    from app.models.file import FileBinding

    actor = _ctx(user_id=100, user_type="STUDENT", student_no="EV2401")
    db = _session()
    student = _student(db)
    actor["studentId"] = str(student.id)
    file_obj = _file(db, owner=100)
    exemption = _exemption(db, student)

    result = evidence.freeze_manifest(db, exemption, [file_obj.id], actor=actor, student=student)
    db.commit()

    assert result["count"] == 1
    entry = result["entries"][0]
    assert entry["fileId"] == str(file_obj.id) and entry["sha256"] == "a" * 64

    binding = db.query(FileBinding).filter(
        FileBinding.tenant_id == TID, FileBinding.file_id == int(file_obj.id)).first()
    assert binding is not None
    assert binding.status == "ACTIVE" and binding.is_current
    assert binding.biz_type == "AA_EXEMPTION" and str(binding.biz_id) == str(exemption.id)
    # 文件本身被收敛为业务范围可见，不再是任人取用的临时私有文件
    db.refresh(file_obj)
    assert file_obj.biz_type == "AA_EXEMPTION" and file_obj.visibility == "BIZ_SCOPED"
    # 清单哈希可复算
    assert evidence.manifest_hash(result["entries"]) == result["manifestHash"]
    db.close()


def test_cannot_use_another_students_file_as_own_evidence(evidence, db_mode):
    """同租户里知道别人的 fileId 也不行——这正是只校验"文件属于本租户"时敞开的洞。"""
    from app.core.exceptions import AppException

    _ctx(user_id=100, user_type="STUDENT", student_no="EV2401")
    db = _session()
    victim = _student(db, student_no="EV1001", name="学生甲")
    victim_file = _file(db, owner=999, name="甲的证书.pdf", digest="b" * 64)
    db.commit()

    attacker = _student(db, student_no="EV2402", name="学生乙")
    actor = _ctx(user_id=100, user_type="STUDENT", student_no="EV2402")
    actor["studentId"] = str(attacker.id)
    exemption = _exemption(db, attacker)

    with pytest.raises(AppException):
        evidence.freeze_manifest(db, exemption, [victim_file.id], actor=actor, student=attacker)
    db.rollback()
    db.close()


def test_unscanned_or_quarantined_file_cannot_become_evidence(evidence, db_mode):
    """扫描未完成/被隔离的文件不能进入正式学分链路。"""
    from app.core.exceptions import AppException

    actor = _ctx(user_id=100, user_type="STUDENT", student_no="EV2401")
    db = _session()
    student = _student(db)
    actor["studentId"] = str(student.id)
    pending = _file(db, owner=100, name="扫描中.pdf", digest="c" * 64,
                    scan="PENDING", status="QUARANTINED")
    exemption = _exemption(db, student)

    with pytest.raises(AppException) as exc:
        evidence.freeze_manifest(db, exemption, [pending.id], actor=actor, student=student)
    assert exc.value.code == "FILE_NOT_READY"
    db.rollback()
    db.close()


def _frozen_case(db, evidence):
    actor = _ctx(user_id=100, user_type="STUDENT", student_no="EV2401")
    student = _student(db)
    actor["studentId"] = str(student.id)
    file_obj = _file(db, owner=100)
    exemption = _exemption(db, student)
    evidence.freeze_manifest(db, exemption, [file_obj.id], actor=actor, student=student)
    db.commit()
    return student, file_obj, exemption


def test_intact_evidence_passes_final_verification(evidence, db_mode):
    db = _session()
    _student_row, _file_obj, exemption = _frozen_case(db, evidence)
    result = evidence.require_valid_manifest(db, exemption)
    assert result["problems"] == [] and len(result["entries"]) == 1
    db.close()


def test_replaced_file_content_invalidates_evidence(evidence, db_mode):
    """审批期间文件内容被换掉（sha256 变了）→ 终审必须拒绝发学分。"""
    from app.core.exceptions import AppException

    db = _session()
    _student_row, file_obj, exemption = _frozen_case(db, evidence)
    file_obj.sha256 = "d" * 64
    db.commit()

    with pytest.raises(AppException) as exc:
        evidence.require_valid_manifest(db, exemption)
    assert exc.value.http_status == 409 and "EVIDENCE_INVALIDATED" in exc.value.message
    assert any("内容已被替换" in text for text in exc.value.details["problems"])
    db.close()


def test_quarantined_after_submission_invalidates_evidence(evidence, db_mode):
    """提交后被安全扫描判定为感染/隔离 → 证据失效。"""
    from app.core.exceptions import AppException

    db = _session()
    _student_row, file_obj, exemption = _frozen_case(db, evidence)
    file_obj.scan_status = "INFECTED"
    file_obj.status = "REJECTED"
    db.commit()

    with pytest.raises(AppException):
        evidence.require_valid_manifest(db, exemption)
    db.close()


def test_revoked_binding_invalidates_evidence(evidence, db_mode):
    """材料被撤回（绑定失效）→ 终审不能继续用它发学分。"""
    from app.core.exceptions import AppException

    from app.models.file import FileBinding

    db = _session()
    _student_row, file_obj, exemption = _frozen_case(db, evidence)
    binding = db.query(FileBinding).filter(
        FileBinding.tenant_id == TID, FileBinding.file_id == int(file_obj.id)).first()
    binding.status = "INVALIDATED"
    binding.is_current = False
    db.commit()

    with pytest.raises(AppException) as exc:
        evidence.require_valid_manifest(db, exemption)
    assert any("绑定已失效" in text for text in exc.value.details["problems"])
    db.close()


def test_deleted_file_invalidates_evidence(evidence, db_mode):
    from app.core.exceptions import AppException

    db = _session()
    _student_row, file_obj, exemption = _frozen_case(db, evidence)
    file_obj.is_deleted = True
    db.commit()

    with pytest.raises(AppException) as exc:
        evidence.require_valid_manifest(db, exemption)
    assert any("已被删除" in text for text in exc.value.details["problems"])
    db.close()


def test_tampered_manifest_is_detected_by_hash(evidence, db_mode):
    """有人直接改库里的清单但没同步哈希 → 必须被发现。"""
    import json

    from app.core.exceptions import AppException

    db = _session()
    _student_row, _file_obj, exemption = _frozen_case(db, evidence)
    entries = evidence.load_manifest(exemption)
    entries[0]["sha256"] = "e" * 64
    exemption.evidence_manifest_json = json.dumps(entries, ensure_ascii=False)
    db.commit()

    with pytest.raises(AppException) as exc:
        evidence.require_valid_manifest(db, exemption)
    assert any("哈希不一致" in text for text in exc.value.details["problems"])
    db.close()


def test_no_material_case_is_not_treated_as_verified(evidence, db_mode):
    """没交材料的申请，清单为空——按"无材料"处理，不假装已核验通过。"""
    db = _session()
    student = _student(db)
    exemption = _exemption(db, student)
    db.commit()
    result = evidence.verify_manifest(db, exemption)
    assert result["entries"] == [] and result["problems"] == []
    assert exemption.evidence_manifest_hash is None
    db.close()


def test_apply_and_final_review_are_wired_to_the_evidence_chain():
    """申请必须冻结清单、终审必须复验；缺任一环，证据链形同虚设。"""
    import inspect

    import app.models  # noqa: F401
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup

    apply_src = inspect.getsource(makeup.exemption_apply)
    review_src = inspect.getsource(makeup.exemption_review)
    assert "freeze_manifest" in apply_src
    assert "require_valid_manifest" in review_src
    # 复验必须早于正式成绩写入，否则先发了学分再说"证据无效"已经晚了
    assert review_src.index("require_valid_manifest") < review_src.index("AcademicGrade(")


def test_model_and_migration_declare_the_same_evidence_columns():
    from pathlib import Path

    from app.models import AaExemption

    assert {"evidence_manifest_json", "evidence_manifest_hash"} <= set(
        AaExemption.__mapper__.attrs.keys())
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260807_aa_exemption_evidence.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "20260807_aa_exempt_ev"' in migration
    assert 'down_revision = "20260807_aa_sched_head"' in migration
    assert "evidence_manifest_json" in migration and "evidence_manifest_hash" in migration
