from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


# P0-1: mobile review is staff-only before the service-level dynamic permission check.
replace_once(
    "backend/app/api/v1/mobile_graduation_material_center.py",
    "from app.core.security import get_current_user\n",
    "from app.core.security import get_current_user, require_staff\n",
)
replace_once(
    "backend/app/api/v1/mobile_graduation_material_center.py",
    "    material_id: int, body: dict = Body(...), user=Depends(get_current_user),\n",
    "    material_id: int, body: dict = Body(...), user=Depends(require_staff),\n",
)

# P0-2: the earlier sensitive router must return the secure public-version contract.
replace_once(
    "backend/app/modules/graduation/routers/graduation_material_sensitive_router.py",
    "from app.modules.graduation.materials import record_service as material_records\n",
    "from app.modules.graduation.materials import query_service as material_queries\n"
    "from app.modules.graduation.materials import record_service as material_records\n",
)
replace_once(
    "backend/app/modules/graduation/routers/graduation_material_sensitive_router.py",
    "    return success(svc.get_proposal_detail(proposal_id))\n",
    "    return success(material_queries.proposal_detail(int(proposal_id), user))\n",
)
replace_once(
    "backend/app/modules/graduation/routers/graduation_material_sensitive_router.py",
    "    return success(svc.get_final_detail(final_id))\n",
    "    return success(material_queries.final_detail(int(final_id), user))\n",
)

# P0-3: one semantic main document per proposal/final submission on both student surfaces.
portal = "student-portal/src/views/graduation/GraduationWorkbenchView.vue"
replace_once(
    portal,
    '<label>附件（PDF / Word / ZIP，最多 10 个）<input type="file" accept=".pdf,.doc,.docx,.zip" multiple @change="pickFiles(\'proposal\', $event)" /></label>',
    '<label>开题主文档（PDF / Word / ZIP，仅 1 份）<input type="file" accept=".pdf,.doc,.docx,.zip" @change="pickFiles(\'proposal\', $event)" /></label>',
)
replace_once(
    portal,
    '<label>论文附件（PDF / Word / ZIP，最多 10 个）<input type="file" accept=".pdf,.doc,.docx,.zip" multiple @change="pickFiles(\'final\', $event)" /></label>',
    '<label>论文主文档（PDF / Word / ZIP，仅 1 份）<input type="file" accept=".pdf,.doc,.docx,.zip" @change="pickFiles(\'final\', $event)" /></label>',
)
old_pick = '''async function pickFiles(kind, event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  const remaining = 10 - attachments[kind].length
  if (remaining <= 0) {
    ui.notify('每个种类最多上传 10 个附件')
    event.target.value = ''
    return
  }
  const toUpload = files.slice(0, remaining)
  if (files.length > remaining) ui.notify(`最多 10 个附件，已截取前 ${remaining} 个`)
  busy.value = true
  try {
    const uploaded = await Promise.all(toUpload.map((file) => portalApi.uploadGraduationMaterial(file)))
    attachments[kind].push(...uploaded)
    ui.notify(`已上传 ${uploaded.length} 个附件`)
  } catch (e) { ui.notify(e?.message || '附件上传失败') } finally { busy.value = false; event.target.value = '' }
}
'''
new_pick = '''async function pickFiles(kind, event) {
  const file = Array.from(event.target.files || [])[0]
  if (!file) return
  busy.value = true
  try {
    const uploaded = await portalApi.uploadGraduationMaterial(file)
    attachments[kind].splice(0, attachments[kind].length, uploaded)
    ui.notify('主文档已上传；重新选择会替换本次待提交文件')
  } catch (e) { ui.notify(e?.message || '主文档上传失败') } finally { busy.value = false; event.target.value = '' }
}
'''
replace_once(portal, old_pick, new_pick)

mini = "miniapp/src/pages/student/graduation/index.vue"
replace_once(
    mini,
    "{{ uploading ? '上传中…' : '+ 添加附件' }}",
    "{{ uploading ? '上传中…' : (propAtts.length ? '更换开题主文档' : '+ 上传开题主文档') }}",
)
replace_once(
    mini,
    "{{ uploading ? '上传中…' : '+ 添加论文附件' }}",
    "{{ uploading ? '上传中…' : (finalAtts.length ? '更换论文主文档' : '+ 上传论文主文档') }}",
)
replace_once(
    mini,
    "        this[arr].push({ fileId: uploaded.fileId, fileName: uploaded.fileName || selected.name || '附件' })\n",
    "        this[arr].splice(0, this[arr].length, {\n"
    "          fileId: uploaded.fileId, fileName: uploaded.fileName || selected.name || '主文档'\n"
    "        })\n",
)

# P0-1/P1-6/P0-4: dynamic review permissions, locked final security checks, snapshot overwrite guard.
command = "backend/app/modules/graduation/materials/command_service.py"
replace_once(
    command,
    "from app.core.exceptions import AppException, not_found\n",
    "from app.core.exceptions import AppException, not_found\n"
    "from app.core.permissions import enforce_permission\n",
)
replace_once(
    command,
    "from app.services.file_access_service import require_file_access\n"
    "from app.services.file_scan_service import assert_file_ready_for_business\n",
    "from app.services.file_access_service import require_file_access\n"
    "from app.services.file_content_security import is_downloadable_status\n"
    "from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED\n"
    "from app.services.file_scan_service import assert_file_ready_for_business\n",
)
owner_block = '''_OWNER_ROLES = {
    "STUDENT": {"STUDENT"},
    "MENTOR": {"GD_MENTOR", "MENTOR", "TEACHER"},
    "REVIEWER": {"GD_REVIEWER", "REVIEWER"},
    "DEFENSE_SECRETARY": {"GD_DEFENSE_SECRETARY", "DEFENSE_SECRETARY"},
    "ADMIN": {
        "PLATFORM_SUPER_ADMIN", "SCHOOL_ADMIN", "GRADUATION_ADMIN", "GD_GRADE_ADMIN",
        "GD_COLLEGE_ADMIN", "COLLEGE_ADMIN", "GD_MAJOR_ADMIN",
    },
    "SYSTEM": {"SYSTEM"},
}
'''
review_block = owner_block + '''

_REVIEW_PERMISSION_BY_CODE = {
    "TOPIC_ATTACHMENT": "graduationDesign.topic.review",
    "TASKBOOK": "graduationDesign.taskbook.update",
    "PROPOSAL_REPORT": "graduationDesign.proposal.review",
    "PROPOSAL_DEFENSE": "graduationDesign.proposal.review",
    "MIDTERM_REPORT": "graduationDesign.midterm.review",
    "THESIS_DRAFT": "graduationDesign.final.review",
    "THESIS_FINAL": "graduationDesign.final.review",
    "DESIGN_WORK": "graduationDesign.final.review",
    "SOURCE_CODE": "graduationDesign.final.review",
    "WORK_DESCRIPTION": "graduationDesign.final.review",
    "PLAGIARISM_REPORT": "graduationDesign.plagiarism.result",
    "REVIEW_ATTACHMENT": "graduationDesign.review.submit",
    "DEFENSE_SIGNED_SHEET": "graduationDesign.defense.scoreConfirm",
}


def review_permission_code(material_code: str) -> str:
    code = _REVIEW_PERMISSION_BY_CODE.get(str(material_code or "").strip().upper())
    if not code:
        raise AppException("NO_PERMISSION", "该材料未配置审核动作权限，系统已拒绝操作", http_status=403)
    return code


def _enforce_review_permission(user: dict, material_code: str) -> str:
    if str((user or {}).get("userType") or "").strip().upper() == "STUDENT":
        raise AppException("NO_PERMISSION", "学生不能审核毕业设计材料", http_status=403)
    code = review_permission_code(material_code)
    enforce_permission(user or {}, code)
    return code
'''
replace_once(command, owner_block, review_block)

validate_block = '''def _validate_file(item: GraduationMaterialItem, file_obj: FileObject) -> None:
    ext = str(file_obj.ext or "").lower().lstrip(".")
    allowed = {str(value).lower().lstrip(".") for value in (item.allowed_ext_json or [])}
    if ext not in allowed:
        raise AppException("FILE_TYPE_NOT_ALLOWED", f"{item.material_name} 不允许 .{ext or '未知'} 文件")
    if int(file_obj.size_bytes or 0) > int(item.max_size_bytes or 0):
        raise AppException("FILE_TOO_LARGE", f"{item.material_name} 超过允许大小")
'''
locked_block = validate_block + '''

def _assert_locked_file_ready(item: GraduationMaterialItem, file_obj: FileObject, user: dict) -> None:
    """Re-check authorization and immutable security facts after SELECT ... FOR UPDATE."""
    _validate_file(item, file_obj)
    require_file_access(str(file_obj.id), user=user, action="bind")
    scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    if not is_downloadable_status(file_obj.status) or scan not in READY_SCAN_STATES:
        raise AppException("FILE_NOT_READY", "文件安全状态已变化，请重新上传或等待扫描完成", http_status=409)
    digest = str(file_obj.sha256 or "")
    if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
        raise AppException("FILE_HASH_MISSING", "文件缺少可信 SHA-256，禁止登记材料版本", http_status=409)
'''
replace_once(command, validate_block, locked_block)

# Every version writer re-checks the locked FileObject immediately before mutation.
for old in (
    "        _validate_file(item, file_obj)\n        version = _append_version(\n",
    "    _validate_file(item, file_obj)\n    version = _append_version(\n",
):
    text = read(command)
    hits = text.count(old)
    if not hits:
        continue
    write(command, text.replace(
        old,
        old.replace("_validate_file(item, file_obj)", "_assert_locked_file_ready(item, file_obj, user)"),
    ))

# Add exact permission enforcement to both review transaction paths.
text = read(command)
needle = '''        _, item = rule_item(db, int(student.batch_id), material.material_code, lock=True)
        if not item.review_required:
'''
if text.count(needle) != 1:
    raise SystemExit(f"{command}: review_material permission insertion mismatch")
text = text.replace(
    needle,
    '''        _, item = rule_item(db, int(student.batch_id), material.material_code, lock=True)
        _enforce_review_permission(user, material.material_code)
        if not item.review_required:
''',
    1,
)
needle2 = '''    _, item = rule_item(db, int(student.batch_id), material.material_code, lock=True)
    if not item.review_required:
'''
if text.count(needle2) != 1:
    raise SystemExit(f"{command}: review_material_in_session permission insertion mismatch")
text = text.replace(
    needle2,
    '''    _, item = rule_item(db, int(student.batch_id), material.material_code, lock=True)
    _enforce_review_permission(user, material.material_code)
    if not item.review_required:
''',
    1,
)
write(command, text)

# Atomic guard: a generated snapshot can refresh only another generated snapshot.
snapshot_guard_old = '''        current_binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == int(material.current_version_id or 0),
            FileBinding.module_code == MODULE_CODE, FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ).with_for_update()).first()
        if current_binding and (current_binding.scope_json or {}).get("sourceDataHash") == source_data_hash:
            return {
                "status": "UNCHANGED", "materialId": str(material.id),
                "fileVersionId": str(material.current_version_id),
            }
'''
snapshot_guard_new = '''        current_version = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.id == int(material.current_version_id or 0),
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
        ).with_for_update()).first()
        current_binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == int(material.current_version_id or 0),
            FileBinding.module_code == MODULE_CODE, FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ).with_for_update()).first()
        if current_version and str(current_version.source_channel or "").upper() != "SYSTEM_GENERATED":
            return {
                "status": "PRESERVED_UPLOAD", "materialId": str(material.id),
                "fileVersionId": str(material.current_version_id),
            }
        if current_binding and (current_binding.scope_json or {}).get("sourceDataHash") == source_data_hash:
            return {
                "status": "UNCHANGED", "materialId": str(material.id),
                "fileVersionId": str(material.current_version_id),
            }
'''
replace_once(command, snapshot_guard_old, snapshot_guard_new)

# Snapshot phase avoids generating orphan bytes and preserves human/legacy uploads across all codes.
snapshot = "backend/app/modules/graduation/materials/snapshot_service.py"
replace_once(snapshot, "from app.models.file import FileBinding\n", "from app.models.file import FileBinding, FileVersion\n")
old_state = '''def _current_source_hash(gd_student_id: int, material_code: str) -> str | None:
    with session() as db:
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(gd_student_id),
            GraduationStudentMaterial.material_code == material_code,
            GraduationStudentMaterial.is_deleted.is_(False),
        )).first()
        if not material or not material.current_version_id:
            return None
        binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == int(material.current_version_id),
            FileBinding.module_code == MODULE_CODE, FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        )).first()
        return str((binding.scope_json or {}).get("sourceDataHash") or "") or None if binding else None
'''
new_state = '''def _current_version_state(gd_student_id: int, material_code: str) -> dict | None:
    with session() as db:
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(gd_student_id),
            GraduationStudentMaterial.material_code == material_code,
            GraduationStudentMaterial.is_deleted.is_(False),
        )).first()
        if not material or not material.current_version_id:
            return None
        version = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.id == int(material.current_version_id),
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
        )).first()
        binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == int(material.current_version_id),
            FileBinding.module_code == MODULE_CODE, FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        )).first()
        return {
            "versionId": str(material.current_version_id),
            "sourceChannel": str(version.source_channel or "").upper() if version else "",
            "sourceDataHash": str((binding.scope_json or {}).get("sourceDataHash") or "") if binding else "",
        }
'''
replace_once(snapshot, old_state, new_state)
old_prepare = '''    result = {"created": [], "unchanged": [], "pendingReview": []}
    for spec in specs:
        source_hash = spec.source_hash(int(student["id"]))
        if _current_source_hash(int(student["id"]), spec.material_code) == source_hash:
            result["unchanged"].append(spec.material_code)
            continue
'''
new_prepare = '''    result = {"created": [], "unchanged": [], "preservedUploads": [], "pendingReview": []}
    for spec in specs:
        source_hash = spec.source_hash(int(student["id"]))
        current = _current_version_state(int(student["id"]), spec.material_code)
        if current and current["sourceChannel"] != "SYSTEM_GENERATED":
            result["preservedUploads"].append(spec.material_code)
            continue
        if current and current["sourceDataHash"] == source_hash:
            result["unchanged"].append(spec.material_code)
            continue
'''
replace_once(snapshot, old_prepare, new_prepare)
replace_once(
    snapshot,
    '        result["unchanged" if registered["status"] == "UNCHANGED" else "created"].append(spec.material_code)\n',
    '''        if registered["status"] == "PRESERVED_UPLOAD":
            result["preservedUploads"].append(spec.material_code)
        else:
            result["unchanged" if registered["status"] == "UNCHANGED" else "created"].append(spec.material_code)
''',
)

# P1-3: only archive-required materials may affect archive readiness.
query = "backend/app/modules/graduation/materials/query_service.py"
replace_once(
    query,
    '''        func.sum(case((fact.c.review_status == "PENDING", 1), else_=0)).label("pending_count"),
        func.sum(case((fact.c.review_status == "RETURNED", 1), else_=0)).label("returned_count"),
        func.sum(case((and_(required_archive, fact.c.review_status.in_(("APPROVED", "NOT_REQUIRED"))), 1), else_=0)).label("approved_count"),
        func.sum(case((and_(fact.c.current_version_id.is_not(None), unsafe), 1), else_=0)).label("scan_abnormal_count"),
        func.sum(case((fact.c.archive_status.in_(("FROZEN", "ARCHIVED")), 1), else_=0)).label("archived_count"),
''',
    '''        func.sum(case((and_(fact.c.archive_required.is_(True), fact.c.current_version_id.is_not(None),
                                  fact.c.review_status == "PENDING"), 1), else_=0)).label("pending_count"),
        func.sum(case((and_(fact.c.archive_required.is_(True), fact.c.current_version_id.is_not(None),
                                  fact.c.review_status == "RETURNED"), 1), else_=0)).label("returned_count"),
        func.sum(case((and_(required_archive, fact.c.review_status.in_(("APPROVED", "NOT_REQUIRED"))), 1), else_=0)).label("approved_count"),
        func.sum(case((and_(fact.c.archive_required.is_(True), fact.c.current_version_id.is_not(None), unsafe), 1), else_=0)).label("scan_abnormal_count"),
        func.sum(case((and_(fact.c.archive_required.is_(True),
                                  fact.c.archive_status.in_(("FROZEN", "ARCHIVED"))), 1), else_=0)).label("archived_count"),
''',
)

# P1-4: export labels come from each manifest's frozen rule revision, never the currently enabled rule.
export = "backend/app/modules/graduation/materials/export_service.py"
replace_once(
    export,
    "from app.models.file import ArchiveManifest, ArchiveManifestItem, FileObject\n",
    "from app.models.file import ArchiveManifest, ArchiveManifestItem, FileObject\n"
    "from app.models.graduation_material import GraduationMaterialItem, GraduationMaterialRule\n",
)
replace_once(export, "from .rule_service import active_rule, rule_items\n", "")
marker = '''def _write_xlsx(path: Path, rows: list[dict]) -> None:
'''
helper = '''def _frozen_rule_names(db, pairs: list[tuple[GraduationStudent, ArchiveManifest]]) -> dict[int, dict[str, str]]:
    cache: dict[tuple[int, str, int], dict[str, str]] = {}
    result: dict[int, dict[str, str]] = {}
    for student, manifest in pairs:
        raw = str(manifest.rule_version or "")
        rule_code, separator, version_text = raw.rpartition(":v")
        if not separator or not version_text.isdigit():
            raise AppException("DATA_CONFLICT", f"Manifest {manifest.id} 缺少可解析的冻结规则版本")
        key = (int(student.batch_id or 0), rule_code, int(version_text))
        if key not in cache:
            rule = db.scalars(select(GraduationMaterialRule).where(
                GraduationMaterialRule.tenant_id == _tid(),
                GraduationMaterialRule.batch_id == key[0],
                GraduationMaterialRule.rule_code == key[1],
                GraduationMaterialRule.rule_version == key[2],
                GraduationMaterialRule.is_deleted.is_(False),
            )).first()
            if not rule:
                raise AppException("DATA_CONFLICT", f"Manifest {manifest.id} 的冻结规则已缺失")
            cache[key] = {
                item.material_code: item.material_name
                for item in db.scalars(select(GraduationMaterialItem).where(
                    GraduationMaterialItem.tenant_id == _tid(),
                    GraduationMaterialItem.rule_id == int(rule.id),
                    GraduationMaterialItem.is_deleted.is_(False),
                )).all()
            }
        result[int(manifest.id)] = cache[key]
    return result


''' + marker
replace_once(export, marker, helper)
replace_once(
    export,
    '''            rule = active_rule(db, int(snapshot.get("batchId")))
            names = {item.material_code: item.material_name for item in rule_items(db, int(rule.id))}
            manifests = {int(manifest.id): (student, manifest) for student, manifest in pairs}
''',
    '''            names_by_manifest = _frozen_rule_names(db, pairs)
            manifests = {int(manifest.id): (student, manifest) for student, manifest in pairs}
''',
)
replace_once(
    export,
    '"materialCode": item.material_code, "materialName": names.get(item.material_code, item.material_code),\n',
    '"materialCode": item.material_code,\n'
    '                        "materialName": names_by_manifest[int(manifest.id)].get(item.material_code, item.material_code),\n',
)

# P1-2: explicit impact read + confirmed, in-transaction catalog migration before switching.
rule = "backend/app/modules/graduation/materials/rule_service.py"
old_activate = '''def activate_rule(rule_id: int, user: dict) -> dict:
    with session() as db:
        candidate = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(), GraduationMaterialRule.id == int(rule_id),
            GraduationMaterialRule.is_deleted.is_(False),
        ).with_for_update()).first()
        if not candidate:
            raise not_found("材料规则不存在")
        if candidate.status == "ENABLED" and candidate.enabled:
            return {"id": str(candidate.id), "status": candidate.status, "impactAnalysis": impact_analysis(db, candidate)}
        if candidate.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿规则可启用")
        impact = impact_analysis(db, candidate)
        current = list(db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.batch_id == int(candidate.batch_id),
            GraduationMaterialRule.status == "ENABLED", GraduationMaterialRule.enabled.is_(True),
            GraduationMaterialRule.is_deleted.is_(False),
        ).with_for_update()).all())
        for row in current:
            row.status = "DISABLED"
            row.enabled = False
        candidate.status = "ENABLED"
        candidate.enabled = True
        candidate.effective_at = datetime.utcnow()
        candidate.updated_by = _actor_id(user)
        db.commit()
        return {"id": str(candidate.id), "status": candidate.status, "ruleVersion": int(candidate.rule_version), "impactAnalysis": impact}
'''
new_activate = '''def get_impact(rule_id: int, user: dict | None = None) -> dict:
    del user
    with session() as db:
        candidate = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(), GraduationMaterialRule.id == int(rule_id),
            GraduationMaterialRule.is_deleted.is_(False),
        )).first()
        if not candidate:
            raise not_found("材料规则不存在")
        return impact_analysis(db, candidate)


def _migrate_catalog_to_candidate(db, candidate: GraduationMaterialRule, user: dict) -> dict:
    items = {row.material_code: row for row in rule_items(db, int(candidate.id), lock=True)}
    rows = list(db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(candidate.batch_id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).all())
    migrated = removed_empty = 0
    for material in rows:
        item = items.get(material.material_code)
        if not item:
            if material.current_version_id or material.archive_status in {"FROZEN", "ARCHIVED"}:
                raise AppException(
                    "MATERIAL_RULE_REMOVAL_CONFLICT",
                    f"材料 {material.material_code} 已有文件或归档证据，不能从新规则移除",
                )
            material.is_deleted = True
            material.updated_by = _actor_id(user)
            removed_empty += 1
            continue
        material.rule_id = int(candidate.id)
        material.rule_version = int(candidate.rule_version)
        material.material_name = item.material_name
        material.biz_stage = item.biz_stage
        material.owner_role = item.owner_role
        material.required_status = "REQUIRED" if item.required else "OPTIONAL"
        material.sensitivity_level = item.sensitivity_level
        material.updated_by = _actor_id(user)
        migrated += 1
    return {"migrated": migrated, "removedEmpty": removed_empty}


def activate_rule(rule_id: int, user: dict, *, confirm_catalog_repair: bool = False) -> dict:
    with session() as db:
        candidate = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(), GraduationMaterialRule.id == int(rule_id),
            GraduationMaterialRule.is_deleted.is_(False),
        ).with_for_update()).first()
        if not candidate:
            raise not_found("材料规则不存在")
        if candidate.status == "ENABLED" and candidate.enabled:
            return {"id": str(candidate.id), "status": candidate.status, "impactAnalysis": impact_analysis(db, candidate)}
        if candidate.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿规则可启用")
        impact = impact_analysis(db, candidate)
        if impact["requiresCatalogRepair"] and not confirm_catalog_repair:
            raise AppException(
                "MATERIAL_RULE_REPAIR_REQUIRED",
                "规则变更会影响现有学生材料目录；请先查看影响分析并显式确认目录迁移",
                http_status=409,
            )
        current = list(db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.batch_id == int(candidate.batch_id),
            GraduationMaterialRule.status == "ENABLED", GraduationMaterialRule.enabled.is_(True),
            GraduationMaterialRule.is_deleted.is_(False),
        ).with_for_update()).all())
        migration = {"migrated": 0, "removedEmpty": 0}
        if impact["requiresCatalogRepair"]:
            migration = _migrate_catalog_to_candidate(db, candidate, user)
        for row in current:
            row.status = "DISABLED"
            row.enabled = False
        candidate.status = "ENABLED"
        candidate.enabled = True
        candidate.effective_at = datetime.utcnow()
        candidate.updated_by = _actor_id(user)
        from .command_service import initialize_batch_materials_in_session

        initialized = initialize_batch_materials_in_session(db, int(candidate.batch_id), user)
        db.commit()
        return {
            "id": str(candidate.id), "status": candidate.status,
            "ruleVersion": int(candidate.rule_version), "impactAnalysis": impact,
            "catalogMigration": {**migration, **initialized},
        }
'''
replace_once(rule, old_activate, new_activate)

# P1-5: use endpoint-specific atomic permissions; generic material review is dynamic in the service.
router = "backend/app/modules/graduation/routers/graduation_material_center.py"
replace_once(
    router,
    "from app.core.permissions import has_permission, require_permission\n",
    "from app.core.permissions import require_permission\n",
)
helpers = '''def _require_material_manager(user=Depends(get_current_user)):
    if not any(has_permission(user or {}, code) for code in (
        "graduationDesign.template.manage",
        "graduationDesign.archive.file",
    )):
        raise not_found("毕业设计材料不存在")
    return user


def _require_material_reviewer(user=Depends(get_current_user)):
    if not any(has_permission(user or {}, code) for code in (
        "graduationDesign.proposal.review",
        "graduationDesign.final.review",
        "graduationDesign.review.submit",
    )):
        raise not_found("毕业设计材料不存在")
    return user


'''
replace_once(router, helpers, "")
replace_once(
    router,
    'def create_material_rule(body: dict = Body(...), user=Depends(_require_material_manager)):\n',
    'def create_material_rule(body: dict = Body(...), user=Depends(require_permission("graduationDesign.student.manage"))):\n',
)
replace_once(
    router,
    '''@router.post("/material-center/rules/{rule_id}/activate", summary="启用毕业设计材料规则")
def activate_material_rule(rule_id: int, user=Depends(_require_material_manager)):
    result = rules.activate_rule(rule_id, user)
    return success(result, message="材料规则已启用")
''',
    '''@router.get("/material-center/rules/{rule_id}/impact", summary="查看规则切换对现有材料目录的影响")
def material_rule_impact(
    rule_id: int, user=Depends(require_permission("graduationDesign.student.manage")),
):
    return success(rules.get_impact(rule_id, user))


@router.post("/material-center/rules/{rule_id}/activate", summary="确认迁移目录并启用毕业设计材料规则")
def activate_material_rule(
    rule_id: int, body: dict = Body(default={}),
    user=Depends(require_permission("graduationDesign.student.manage")),
):
    result = rules.activate_rule(
        rule_id, user, confirm_catalog_repair=bool((body or {}).get("confirmCatalogRepair", False)),
    )
    return success(result, message="材料规则已启用")
''',
)
replacements = {
    "def backfill_materials(body: dict = Body(default={}), user=Depends(_require_material_manager)):":
        'def backfill_materials(body: dict = Body(default={}), user=Depends(require_permission("graduationDesign.student.manage"))):',
    "    user=Depends(_require_material_reviewer),":
        "    user=Depends(get_current_user),",
    "    template_id: int, body: dict = Body(default={}), user=Depends(_require_material_manager),":
        '    template_id: int, body: dict = Body(default={}), user=Depends(require_permission("graduationDesign.template.manage")),',
    "def update_template_status(policy_id: int, body: dict = Body(...), user=Depends(_require_material_manager)):":
        'def update_template_status(policy_id: int, body: dict = Body(...), user=Depends(require_permission("graduationDesign.template.manage"))):',
    "    gd_student_id: int, body: dict = Body(default={}), user=Depends(_require_material_manager),":
        '    gd_student_id: int, body: dict = Body(default={}), user=Depends(require_permission("graduationDesign.archive.file")),',
    "    gd_student_id: int, body: dict = Body(...), user=Depends(_require_material_manager),":
        '    gd_student_id: int, body: dict = Body(...), user=Depends(require_permission("graduationDesign.archive.file")),',
    "def create_archive_export(body: dict = Body(...), user=Depends(_require_material_manager)):":
        'def create_archive_export(body: dict = Body(...), user=Depends(require_permission("graduationDesign.archive.export"))):',
    "def retry_archive_export(job_id: int, user=Depends(_require_material_manager)):":
        'def retry_archive_export(job_id: int, user=Depends(require_permission("graduationDesign.archive.export"))):',
    "    job_id: int, body: dict = Body(...), user=Depends(_require_material_manager),":
        '    job_id: int, body: dict = Body(...), user=Depends(require_permission("graduationDesign.archive.export")),',
    "def archive_package(gd_student_id: int, user=Depends(_require_material_manager)):":
        'def archive_package(gd_student_id: int, user=Depends(require_permission("graduationDesign.archive.export"))):',
    "def batch_archive_package(batch_id: int, user=Depends(_require_material_manager)):":
        'def batch_archive_package(batch_id: int, user=Depends(require_permission("graduationDesign.archive.export"))):',
    "    user=Depends(_require_material_manager),":
        '    user=Depends(require_permission("graduationDesign.archive.file")),',
    "    batchId: int = Query(..., ge=1), user=Depends(_require_material_manager),":
        '    batchId: int = Query(..., ge=1), user=Depends(require_permission("graduationDesign.archive.file")),',
}
for old, new in replacements.items():
    text = read(router)
    if old not in text:
        raise SystemExit(f"{router}: missing permission replacement: {old}")
    write(router, text.replace(old, new, 1))

# Dynamic permission endpoint is explicitly allowlisted; the command service is the fail-closed authority.
perm = "backend/app/core/graduation_permissions.py"
replace_once(
    perm,
    '    "graduation_material_center.activate_material_rule": "graduationDesign.student.manage",\n',
    '    "graduation_material_center.activate_material_rule": "graduationDesign.student.manage",\n'
    '    "graduation_material_center.material_rule_impact": "graduationDesign.student.manage",\n',
)
replace_once(
    perm,
    '    "graduation_material_center.review_material_item": "graduationDesign.review.submit",\n',
    "",
)
marker = '''GRADUATION_ENDPOINT_PERMISSION_OVERRIDES = {
'''
dynamic = '''GRADUATION_DYNAMIC_PERMISSION_ENDPOINTS = {
    "graduation_material_center.review_material_item",
}


''' + marker
replace_once(perm, marker, dynamic)
old_gate = '''    code = graduation_permission_for_endpoint(endpoint)
    if not code:
'''
new_gate = '''    module_name = getattr(endpoint, "__module__", "").rsplit(".", 1)[-1]
    qualified_name = f"{module_name}.{endpoint_name}"
    if qualified_name in GRADUATION_DYNAMIC_PERMISSION_ENDPOINTS:
        request.state.permission_code = "graduationDesign.material.review.dynamic"
        return user

    code = graduation_permission_for_endpoint(endpoint)
    if not code:
'''
replace_once(perm, old_gate, new_gate)

# Frontend API exposes impact + explicit confirmation; no hidden activation.
api = "frontend/src/modules/graduation/api/graduation-material-center.api.js"
replace_once(
    api,
    '''  activateRule(ruleId) {
    return request(`/graduation/material-center/rules/${encodeURIComponent(ruleId)}/activate`, { method: 'POST' })
  },
''',
    '''  ruleImpact(ruleId) {
    return request(`/graduation/material-center/rules/${encodeURIComponent(ruleId)}/impact`)
  },
  activateRule(ruleId, { confirmCatalogRepair = false } = {}) {
    return request(`/graduation/material-center/rules/${encodeURIComponent(ruleId)}/activate`, {
      method: 'POST', data: { confirmCatalogRepair }
    })
  },
''',
)

# Regression tests: include real FastAPI route requests, not only source-text assertions.
test_path = ROOT / "backend/tests/test_graduation_material_closeout_regressions.py"
test_path.write_text(r'''from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _student() -> dict:
    return {
        "userId": "9001",
        "tenantId": "1000000000000000001",
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
        "studentNo": "S9001",
        "permissions": ["*"],
        "modules": ["graduation"],
        "moduleCodes": ["graduation"],
    }


def _admin() -> dict:
    return {
        "userId": "1",
        "tenantId": "1000000000000000001",
        "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "permissions": ["*"],
    }


def test_student_mobile_review_is_real_403_and_handler_never_runs(monkeypatch):
    from app.api.v1 import mobile_graduation_material_center as mobile
    from app.core.security import get_current_user

    called = {"value": False}

    def forbidden_handler(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("student request reached material review command")

    monkeypatch.setattr(mobile.commands, "review_material", forbidden_handler)
    app = FastAPI()
    app.include_router(mobile.router)
    app.dependency_overrides[get_current_user] = _student
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/mobile/graduation/material-center/materials/1/review",
            json={"action": "APPROVE", "fileVersionId": 2, "expectedVersion": 3},
        )
    assert response.status_code == 403
    assert called["value"] is False


def test_sensitive_detail_routes_return_secure_version_contract(monkeypatch):
    from app.core.security import get_current_user
    from app.modules.graduation.routers import graduation_material_sensitive_router as sensitive

    contract = {
        "currentSafeVersions": [{"versionId": "22"}],
        "reviewReady": True,
        "migrationRequired": False,
        "materialVersion": 3,
        "fileVersionId": "22",
    }
    monkeypatch.setattr(sensitive, "_record_student", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sensitive.material_queries, "proposal_detail", lambda *_args, **_kwargs: dict(contract))
    monkeypatch.setattr(sensitive.material_queries, "final_detail", lambda *_args, **_kwargs: dict(contract))
    app = FastAPI()
    app.include_router(sensitive.router)
    app.dependency_overrides[get_current_user] = _admin
    with TestClient(app) as client:
        for path in ("/graduation/proposals/7?batchId=1", "/graduation/finals/8?batchId=1"):
            payload = client.get(path).json()["data"]
            assert set(contract).issubset(payload)
            assert payload["reviewReady"] is True


def test_review_permission_map_is_exact_and_students_fail_closed(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.graduation.materials import command_service as command

    assert command.review_permission_code("PROPOSAL_REPORT") == "graduationDesign.proposal.review"
    assert command.review_permission_code("THESIS_FINAL") == "graduationDesign.final.review"
    assert command.review_permission_code("REVIEW_ATTACHMENT") == "graduationDesign.review.submit"
    assert command.review_permission_code("DEFENSE_SIGNED_SHEET") == "graduationDesign.defense.scoreConfirm"
    monkeypatch.setattr(command, "enforce_permission", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("student must be rejected before permission execution")
    ))
    try:
        command._enforce_review_permission(_student(), "PROPOSAL_REPORT")
    except AppException as exc:
        assert exc.http_status == 403
    else:
        raise AssertionError("student review permission was not rejected")


def test_single_main_document_contract_on_student_surfaces():
    portal = source("student-portal/src/views/graduation/GraduationWorkbenchView.vue")
    mini = source("miniapp/src/pages/student/graduation/index.vue")
    record = source("backend/app/modules/graduation/materials/record_service.py")
    assert "最多 10 个附件" not in portal
    assert 'type="file" accept=".pdf,.doc,.docx,.zip" multiple' not in portal
    assert "attachments[kind].splice(0, attachments[kind].length, uploaded)" in portal
    assert "this[arr].splice(0, this[arr].length" in mini
    assert "兼容提交一次仅接收一个主文档" in record


def test_generated_snapshots_never_replace_human_current_versions():
    command = source("backend/app/modules/graduation/materials/command_service.py")
    snapshot = source("backend/app/modules/graduation/materials/snapshot_service.py")
    assert 'current_version.source_channel or "").upper() != "SYSTEM_GENERATED"' in command
    assert '"status": "PRESERVED_UPLOAD"' in command
    assert '"preservedUploads": []' in snapshot
    assert 'current["sourceChannel"] != "SYSTEM_GENERATED"' in snapshot


def test_rule_switch_is_two_step_and_catalog_migrates_before_enable():
    rule = source("backend/app/modules/graduation/materials/rule_service.py")
    router = source("backend/app/modules/graduation/routers/graduation_material_center.py")
    assert "MATERIAL_RULE_REPAIR_REQUIRED" in rule
    assert "confirm_catalog_repair" in rule
    assert "_migrate_catalog_to_candidate" in rule
    assert "MATERIAL_RULE_REMOVAL_CONFLICT" in rule
    assert "/material-center/rules/{rule_id}/impact" in router
    assert "confirmCatalogRepair" in router


def test_archive_summary_ignores_non_archive_materials():
    query = source("backend/app/modules/graduation/materials/query_service.py")
    for status in ('review_status == "PENDING"', 'review_status == "RETURNED"', "scan_abnormal_count"):
        section = query[query.index("def _student_aggregate"):query.index("def _summary")]
        assert "archive_required.is_(True)" in section
        assert status in section


def test_export_uses_each_manifest_frozen_rule_revision():
    export = source("backend/app/modules/graduation/materials/export_service.py")
    assert "def _frozen_rule_names" in export
    assert 'manifest.rule_version' in export
    assert "names_by_manifest[int(manifest.id)]" in export
    assert "active_rule(" not in export


def test_atomic_permissions_replace_material_manager_or_gate():
    router = source("backend/app/modules/graduation/routers/graduation_material_center.py")
    permissions = source("backend/app/core/graduation_permissions.py")
    assert "_require_material_manager" not in router
    assert "_require_material_reviewer" not in router
    assert 'require_permission("graduationDesign.archive.export")' in router
    assert 'require_permission("graduationDesign.template.manage")' in router
    assert "GRADUATION_DYNAMIC_PERMISSION_ENDPOINTS" in permissions


def test_version_writers_revalidate_locked_security_facts():
    command = source("backend/app/modules/graduation/materials/command_service.py")
    assert "def _assert_locked_file_ready" in command
    assert "is_downloadable_status(file_obj.status)" in command
    assert "scan not in READY_SCAN_STATES" in command
    assert "FILE_HASH_MISSING" in command
    assert command.count("_assert_locked_file_ready(item, file_obj, user)") >= 4
''', encoding="utf-8")

print("graduation material closeout patch applied")