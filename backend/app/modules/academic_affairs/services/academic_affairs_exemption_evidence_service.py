"""正式学分证据链（P0-D06，覆盖免修与成绩认定）。

免修终审和成绩认定终审都会直接生成一条正式的、计学分的及格成绩——材料就是这门学分的唯一
依据。两边原来都只校验"这些 fileId 属于本租户"，同样的两个洞因此长期敞着：

1. 归属不明：学生 B 只要知道学生 A 上传的 fileId，就能拿 A 的证书当自己的依据；
2. 时间差：提交时文件正常，审批期间被撤回、隔离或换成另一份内容，终审仍按旧 fileId 放行。

两个业务的证据要求完全一致，所以共用这一套守卫，不各写一份：

    EXEMPTION   免修材料
    RECOGNITION 成绩认定佐证

做法是复用既有文件中心能力，不另造一套附件安全：
- 归属与安全状态交给 ``file_business_binding_service.bind_file_to_business``——它会锁文件行、
  校验 AVAILABLE/CLEAN、拒绝把别人的临时文件或已绑定其它业务的文件接管过来；
- 绑定成功后把 bindingId/fileId/version/sha256/owner/boundAt 冻结成清单并存哈希；
- 终审前按清单逐项复验并重算哈希，任何一项对不上就判证据失效，拒绝生成正式成绩。

哈希只覆盖清单本身。文件内容是否被替换靠 sha256 逐项比对，不靠哈希"顺带"证明。
"""
from __future__ import annotations

import hashlib
import json

from app.core.exceptions import AppException
from app.services.db_service import _tid

_MODULE = "ACADEMIC_AFFAIRS"
_READY_FILE_STATUS = {"AVAILABLE", "STORED"}
_READY_SCAN_STATUS = {"CLEAN", "NOT_REQUIRED"}
# evidence_manifest_json 列宽 4000，留出余量后的清单上限。
_MANIFEST_MAX_CHARS = 3900

# 每种正式学分业务的绑定身份。新增业务在这里登记，不要复制整套校验逻辑。
_KINDS = {
    "EXEMPTION": {"bizType": "AA_EXEMPTION", "relation": "EXEMPTION_EVIDENCE", "label": "免修材料"},
    "RECOGNITION": {"bizType": "AA_RECOGNITION", "relation": "RECOGNITION_EVIDENCE",
                    "label": "成绩认定佐证"},
}


def _kind(kind: str) -> dict:
    spec = _KINDS.get(str(kind or "").strip().upper())
    if not spec:
        raise AppException("VALIDATION_ERROR", f"未登记的正式学分证据业务类型：{kind}")
    return spec


def manifest_hash(entries) -> str:
    """对清单做稳定序列化后取 sha256；键排序保证同样内容永远同样哈希。"""
    payload = json.dumps(entries or [], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _entry(binding, file_obj) -> dict:
    return {
        "bindingId": str(binding.id),
        "fileId": str(file_obj.id),
        "fileVersion": int(file_obj.version or 0),
        "sha256": str(file_obj.sha256 or ""),
        "ownerUserId": str(file_obj.owner_user_id or ""),
        "fileName": str(file_obj.file_name or ""),
        "boundAt": binding.created_at.isoformat() if getattr(binding, "created_at", None) else "",
    }


def freeze_manifest(db, record, file_ids, *, actor: dict, student, kind: str = "EXEMPTION",
                    scope: dict | None = None) -> dict:
    """在申请事务内把材料绑定到这条申请，并冻结证据清单。

    必须在 record 已 flush 拿到 id 之后调用：绑定的正式对象是这条申请本身，没有 id
    就没有可绑定的权威对象，只能退回"凭 fileId 说话"的老路。
    """
    from app.models.file import FileObject
    from app.services.file_business_binding_service import bind_file_to_business

    spec = _kind(kind)
    entries = []
    for file_id in file_ids or []:
        binding = bind_file_to_business(
            db,
            file_id=file_id,
            biz_type=spec["bizType"],
            biz_id=record.id,
            actor=actor,
            subject_type="STUDENT",
            subject_id=student.id,
            relation_type=spec["relation"],
            module_code=_MODULE,
            student_id=int(student.id),
            college_id=getattr(student, "college_id", None),
            class_id=getattr(student, "class_id", None),
            scope=dict(scope or {}),
        )
        db.flush()
        file_obj = db.get(FileObject, int(file_id))
        entries.append(_entry(binding, file_obj))

    entries.sort(key=lambda item: (item["fileId"], item["bindingId"]))
    digest = manifest_hash(entries)
    payload = json.dumps(entries, ensure_ascii=False)
    # 清单列是 String(4000)：超长会在 flush 时撞 MySQL 1406 变成 500。这里提前给出业务错误，
    # 让学生知道"材料太多"，而不是收到一个看不懂的服务端错误。
    if len(payload) > _MANIFEST_MAX_CHARS:
        raise AppException(
            "VALIDATION_ERROR",
            f"{spec['label']}份数过多，无法完整登记证据清单，请精简后重新提交",
            details={"files": len(entries), "manifestChars": len(payload)},
        )
    record.evidence_manifest_json = payload
    record.evidence_manifest_hash = digest
    return {"entries": entries, "manifestHash": digest, "count": len(entries)}


def load_manifest(record) -> list:
    raw = getattr(record, "evidence_manifest_json", None)
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def verify_manifest(db, record, *, kind: str = "EXEMPTION") -> dict:
    """终审前复验证据链，返回 {'entries': [...], 'manifestHash': ..., 'problems': [...]}。

    逐项比对而不是只比总哈希：哈希只能告诉你"变了"，比对能告诉你"哪一份、变成了什么"，
    审批人和后续追溯都需要后者。
    """
    from app.models.file import FileBinding, FileObject

    spec = _kind(kind)
    frozen = load_manifest(record)
    problems = []
    if not frozen:
        return {"entries": [], "manifestHash": record.evidence_manifest_hash, "problems": []}

    stored_hash = str(record.evidence_manifest_hash or "")
    if stored_hash and stored_hash != manifest_hash(frozen):
        problems.append("证据清单与其哈希不一致，清单可能已被篡改")

    for item in frozen:
        label = item.get("fileName") or f"文件{item.get('fileId')}"
        binding = db.query(FileBinding).filter(
            FileBinding.id == int(item["bindingId"]),
            FileBinding.tenant_id == _tid(),
            FileBinding.is_deleted.is_(False),
        ).first()
        if not binding:
            problems.append(f"{label}：材料绑定记录已不存在")
            continue
        if str(binding.status or "").upper() != "ACTIVE" or not binding.is_current:
            problems.append(f"{label}：材料绑定已失效（{binding.status}）")
            continue
        if str(binding.biz_type or "").upper() != spec["bizType"] or str(binding.biz_id) != str(record.id):
            problems.append(f"{label}：材料已改绑到其它业务对象")
            continue
        if int(binding.file_id) != int(item["fileId"]):
            problems.append(f"{label}：材料绑定指向的文件与冻结时不一致")
            continue

        file_obj = db.query(FileObject).filter(
            FileObject.id == int(item["fileId"]),
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        ).first()
        if not file_obj:
            problems.append(f"{label}：材料文件已被删除")
            continue
        if str(file_obj.status or "").upper() not in _READY_FILE_STATUS:
            problems.append(f"{label}：材料文件当前不可用（{file_obj.status}）")
            continue
        if str(file_obj.scan_status or "NOT_REQUIRED").upper() not in _READY_SCAN_STATUS:
            problems.append(f"{label}：材料文件安全扫描状态异常（{file_obj.scan_status}）")
            continue
        if str(item.get("sha256") or "") and str(file_obj.sha256 or "") != str(item["sha256"]):
            problems.append(f"{label}：材料内容已被替换（sha256 与申请时不一致）")
            continue
        if str(item.get("ownerUserId") or "") and str(file_obj.owner_user_id or "") != str(item["ownerUserId"]):
            problems.append(f"{label}：材料归属人已变更")

    return {
        "entries": frozen,
        "manifestHash": record.evidence_manifest_hash,
        "problems": problems,
    }


def require_valid_manifest(db, record, *, kind: str = "EXEMPTION") -> dict:
    spec = _kind(kind)
    result = verify_manifest(db, record, kind=kind)
    if result["problems"]:
        found = result["problems"]
        raise AppException(
            "DATA_CONFLICT",
            f"EVIDENCE_INVALIDATED：{spec['label']}在审批期间已失效，不能据此生成正式成绩："
            + "；".join(found[:5]) + ("…" if len(found) > 5 else ""),
            details={"problems": found[:50], "recordId": str(record.id), "kind": kind},
            http_status=409,
        )
    return result
