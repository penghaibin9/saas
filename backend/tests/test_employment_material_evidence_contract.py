"""就业材料正式证据合同（V3 施工手册 TP-E03 / TP-E05）。

背景：PR #183 为教师端小程序建立了「正式证据」口径（APPROVED 材料 + ACTIVE/
is_current 的 EMPLOYMENT_MATERIAL FileBinding + 可用且扫描通过的 FileObject），
但当时只写在 teacher_mobile_employment_service 内部；教师 **PC** 端的材料列表/
详情/学生详情仍只返回 file_name，老师在 PC 上无法区分「正式安全文件」与
「历史文件名文本」，却照样能点审核通过。

本轮把判定抽成单一权威 employment_material_evidence_service，PC 与小程序共用。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_evidence_authority_defines_single_formal_rule():
    src = _src("backend/app/modules/employment/services/employment_material_evidence_service.py")
    assert 'FORMAL_BIZ_TYPE = "EMPLOYMENT_MATERIAL"' in src
    assert 'READY_SCAN_STATUS = frozenset({"CLEAN", "NOT_REQUIRED"})' in src
    assert "def is_ready_file(" in src
    assert "def resolve_evidence(" in src
    assert "def evidence_fields(" in src


def test_teacher_mini_delegates_to_shared_authority_not_its_own_copy():
    """#183 原本在小程序服务里自带一份绑定/扫描判定；现在必须复用共享权威，
    否则 PC 与小程序可能对同一份材料给出不同的"是否正式证据"结论。"""
    src = _src("backend/app/services/teacher_mobile_employment_service.py")
    assert "evidence_authority.resolve_evidence(" in src
    assert "return evidence_authority.is_ready_file(file_obj)" in src
    assert "_READY_FILE_STATUS = evidence_authority.READY_FILE_STATUS" in src
    # 小程序自己那份绑定查询必须消失，不能两处各查各的
    assert "FileBinding.biz_id.in_(" not in src
    # 但 #183 已锁定的对外契约字符串仍须保留
    assert '_FORMAL_BIZ_TYPE = "EMPLOYMENT_MATERIAL"' in src
    assert "legacyFileNameOnly" in src
    assert "@register_file_resolver(_FORMAL_BIZ_TYPE)" in src


def test_pc_material_dto_exposes_formal_evidence():
    """TP-E05：PC 材料 DTO 必须带 formalEvidence/legacyFileNameOnly/file，
    老师才能区分正式证据与历史文本。"""
    src = _src("backend/app/modules/employment/services/employment_service.py")
    assert "def _mat_row(m: EmpMaterial, stu=None, evidence: dict | None = None)" in src
    assert "row.update(ev.evidence_fields(m, evidence))" in src
    assert "def _mat_rows(" in src


def test_pc_material_reads_resolve_evidence_in_batch_not_per_row():
    """列表页一页几十条，逐条查绑定会把一次列表请求放大成 N+1。"""
    base = _src("backend/app/modules/employment/services/employment_service.py")
    runtime = _src("backend/app/modules/employment/services/employment_runtime_service.py")
    assert "facts = ev.resolve_evidence(db, [m.id for m in rows])" in base
    assert "facts = ev.resolve_evidence(db, [m.id for m in materials])" in base
    assert "return base._mat_rows(db, rows, students), total" in runtime


def test_pc_material_detail_carries_file_descriptor_for_viewer():
    """TP-E03：材料详情要给出 fileId/bindingId/scanStatus/fileVersion，
    公共 Viewer 才有正式原文可看；无正式绑定时 file=None（fail-closed）。"""
    runtime = _src("backend/app/modules/employment/services/employment_runtime_service.py")
    assert 'facts = base_ev.resolve_evidence(db, [material.id])' in runtime
    assert '"material": base._mat_row(material, emp, facts.get(int(material.id))),' in runtime
    authority = _src("backend/app/modules/employment/services/employment_material_evidence_service.py")
    for field in ('"fileId"', '"bindingId"', '"scanStatus"', '"fileVersion"'):
        assert field in authority, field


def test_evidence_uses_version_no_not_optimistic_lock_version():
    """FileBinding 有两个 version 语义：version_no 是文件版本，CommonMixin 的
    version 是乐观锁，混用会把锁版本当文件版本显示给老师。"""
    src = _src("backend/app/modules/employment/services/employment_material_evidence_service.py")
    assert 'getattr(binding, "version_no", 0)' in src


def test_no_duplicate_material_approval_implementation():
    """PR #183 把 PC 材料审核权威搬到 employment_runtime_material_service 后，
    employment_runtime_service 里那份逐字重复的实现失去了调用方却还留着。
    留着重复实现的风险是真实的：谁把它接回去就会绕过 #183 明示的兼容契约
    （材料通过同时置 verify_status=VERIFIED），两条路径漂移=端间事实分叉。
    现在它必须委派给唯一权威，而不是自己再写一遍状态机。"""
    runtime = _src("backend/app/modules/employment/services/employment_runtime_service.py")
    block = runtime[runtime.index("def approve_material("):]
    block = block[:block.index("\ndef ", 1)] if "\ndef " in block[1:] else block
    assert "employment_runtime_material_service.approve_material(mid, comment, user=user)" in block
    # 重复的状态机赋值必须消失
    assert 'emp.verify_status = "VERIFIED"' not in block
    assert 'material.status = "APPROVED"' not in block
