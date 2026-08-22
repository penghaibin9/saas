"""就业材料「正式证据」判定的单一权威（V3 施工手册 TP-E05 / TP-E03）。

为什么需要这个模块
────────────────────────────────────────────────────────────
PR #183 为教师端小程序建立了正式证据口径：一份 `EmpMaterial` 只有在同时具备
ACTIVE + is_current 的 `EMPLOYMENT_MATERIAL` FileBinding、且其 FileObject
状态可用、安全扫描通过时，才算「正式证据」；仅有历史 `file_name` 文本的记录
是展示用的历史遗留，永远不能当核验凭据。

但这套判定当时只写在 `teacher_mobile_employment_service` 里，教师 **PC** 端的
材料列表/详情/学生详情仍然只返回 `file_name`，老师在 PC 上根本无法区分
「正式安全文件」和「历史文件名文本」，却可以照样点审核通过。

本模块把「什么算正式证据」抽成唯一权威，教师 PC 与教师小程序共用同一判定，
各自只做各自的 DTO 投影——不是再抄一份规则。判定规则变化时只改这里。
"""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select

from app.models.file import FileBinding, FileObject
from app.services.db_service import _tid

#: FileObject 可用状态（与 #183 教师端口径一致）。
READY_FILE_STATUS = frozenset({"AVAILABLE", "STORED"})
#: 安全扫描放行状态；PENDING/INFECTED 一律不算正式证据。
READY_SCAN_STATUS = frozenset({"CLEAN", "NOT_REQUIRED"})
#: 正式就业材料的业务绑定类型/模块。
FORMAL_BIZ_TYPE = "EMPLOYMENT_MATERIAL"
FORMAL_MODULE = "EMPLOYMENT"


def is_ready_file(file_obj: FileObject | None) -> bool:
    """文件本身是否处于可作为证据的状态（存在、可用、扫描通过、未删除）。"""
    return bool(
        file_obj
        and str(file_obj.status or "").upper() in READY_FILE_STATUS
        and str(file_obj.scan_status or "NOT_REQUIRED").upper() in READY_SCAN_STATUS
        and not file_obj.is_deleted
    )


def resolve_evidence(db, material_ids: Iterable[Any]) -> dict[int, dict]:
    """批量解析材料 ID → 正式证据事实。

    返回 ``{material_id: {"formal": bool, "binding": FileBinding|None,
    "file": FileObject|None}}``；只包含查得到绑定的材料，调用方对缺失键按
    「无正式证据」处理（fail-closed）。

    单次查询解析全部绑定与文件，不在调用方循环里逐条查库——材料列表页一页就有
    几十条，逐条查会把一次列表请求放大成 N+1。
    """
    ids: list[int] = []
    for raw in material_ids or ():
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not ids:
        return {}

    bindings: dict[int, FileBinding] = {}
    rows = db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(),
        FileBinding.biz_type == FORMAL_BIZ_TYPE,
        FileBinding.biz_id.in_([str(i) for i in ids]),
        FileBinding.module_code == FORMAL_MODULE,
        FileBinding.status == "ACTIVE",
        FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    ).order_by(FileBinding.id.desc())).all()
    for item in rows:
        raw = str(item.biz_id or "")
        # order_by id desc + 首次命中优先 = 取最新一条绑定，与 #183 教师端一致。
        if raw.isdigit() and int(raw) not in bindings:
            bindings[int(raw)] = item

    files: dict[int, FileObject] = {}
    file_ids = {int(b.file_id) for b in bindings.values() if b.file_id}
    if file_ids:
        files = {
            int(row.id): row
            for row in db.scalars(select(FileObject).where(
                FileObject.tenant_id == _tid(),
                FileObject.id.in_(file_ids),
                FileObject.is_deleted.is_(False),
            )).all()
        }

    out: dict[int, dict] = {}
    for mid, binding in bindings.items():
        file_obj = files.get(int(binding.file_id)) if binding.file_id else None
        out[mid] = {
            "formal": bool(binding and is_ready_file(file_obj)),
            "binding": binding,
            "file": file_obj,
        }
    return out


def evidence_fields(material, fact: dict | None) -> dict:
    """把证据事实投影成教师 PC 材料 DTO 的附加字段。

    - ``formalEvidence``：能否作为核验凭据。
    - ``legacyFileNameOnly``：只有历史 file_name 文本、没有正式绑定；界面必须
      标注为历史记录，不能显示成"安全可核验"。
    - ``file``：正式文件描述符（fileId/bindingId/scanStatus/version），供公共
      Document Viewer 消费；无正式证据时为 ``None``，Viewer 自然打不开——
      Viewer 只负责显示，不参与审核状态判定。
    """
    fact = fact or {}
    formal = bool(fact.get("formal"))
    binding = fact.get("binding")
    file_obj = fact.get("file")
    return {
        "formalEvidence": formal,
        "legacyFileNameOnly": bool(getattr(material, "file_name", None) and not formal),
        "file": ({
            "fileId": str(file_obj.id),
            "fileName": file_obj.file_name,
            "scanStatus": file_obj.scan_status,
            # FileBinding 的文件版本列是 version_no（CommonMixin 另有一个乐观锁
            # version，两者含义不同，不能混用）。
            "fileVersion": int(getattr(binding, "version_no", 0) or 0),
            "bindingId": str(binding.id),
            "bizType": FORMAL_BIZ_TYPE,
        } if formal and file_obj is not None and binding is not None else None),
    }
