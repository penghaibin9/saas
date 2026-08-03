from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


# One authoritative review-permission catalog shared by rules, commands and queries.
definitions = "backend/app/modules/graduation/materials/definitions.py"
replace_once(
    definitions,
    'SNAPSHOT_GENERATOR_VERSION = "graduation-material-closeout/1"\n\n\nDEFAULT_MATERIAL_DEFINITIONS',
    '''SNAPSHOT_GENERATOR_VERSION = "graduation-material-closeout/1"

REVIEW_PERMISSION_BY_CODE = {
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


DEFAULT_MATERIAL_DEFINITIONS''',
)

rule = "backend/app/modules/graduation/materials/rule_service.py"
replace_once(
    rule,
    "from .definitions import DEFAULT_MATERIAL_DEFINITIONS\n",
    "from .definitions import DEFAULT_MATERIAL_DEFINITIONS, REVIEW_PERMISSION_BY_CODE\n",
)
replace_once(
    rule,
    '''    if not extensions or max_size <= 0:
        raise AppException("VALIDATION_ERROR", f"材料 {code} 缺少允许扩展名或大小限制")
    return {
''',
    '''    if not extensions or max_size <= 0:
        raise AppException("VALIDATION_ERROR", f"材料 {code} 缺少允许扩展名或大小限制")
    review_required = bool(raw.get("reviewRequired", True))
    if review_required and code not in REVIEW_PERMISSION_BY_CODE:
        raise AppException(
            "VALIDATION_ERROR",
            f"材料 {code} 要求人工审核，但未登记受支持的原子审核权限",
        )
    return {
''',
)
replace_once(
    rule,
    '        "review_required": bool(raw.get("reviewRequired", True)),\n',
    '        "review_required": review_required,\n',
)

command = "backend/app/modules/graduation/materials/command_service.py"
replace_once(
    command,
    "from .definitions import MANIFEST_ARCHIVE_TYPE, MANIFEST_TARGET_TYPE, MODULE_CODE\n",
    "from .definitions import MANIFEST_ARCHIVE_TYPE, MANIFEST_TARGET_TYPE, MODULE_CODE, REVIEW_PERMISSION_BY_CODE\n",
)
local_map = '''
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


'''
replace_once(command, local_map, "")
replace_once(
    command,
    "    code = _REVIEW_PERMISSION_BY_CODE.get(str(material_code or \"\").strip().upper())\n",
    "    code = REVIEW_PERMISSION_BY_CODE.get(str(material_code or \"\").strip().upper())\n",
)
old_initializer = '''def initialize_student_materials_in_session(db, gd_student_id: int, user: dict | None = None) -> dict:
    """Idempotently materialize the enabled rule for one active student."""
    student = _student_for_update(db, int(gd_student_id))
    rule = active_rule(db, int(student.batch_id), lock=True)
    items = rule_items(db, int(rule.id), lock=True)
    existing = {row.material_code: row for row in db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(student.batch_id),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).all()}
    created = 0
    for item in items:
        if item.material_code in existing:
            continue
        db.add(_new_material(student, item, int(rule.id), int(rule.rule_version), _actor_id(user)))
        created += 1
    db.flush()
    return {
        "gdStudentId": str(student.id), "ruleId": str(rule.id),
        "ruleVersion": int(rule.rule_version), "created": created, "total": len(items),
    }
'''
new_initializer = '''def initialize_student_materials_in_session(db, gd_student_id: int, user: dict | None = None) -> dict:
    """Idempotently materialize the enabled rule without mutating archived evidence."""
    student = _student_for_update(db, int(gd_student_id))
    existing_rows = list(db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(student.batch_id),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).all())
    if str(student.stage or "").upper() == "ARCHIVED":
        rule_ids = {int(row.rule_id) for row in existing_rows if row.rule_id}
        rule_versions = {int(row.rule_version) for row in existing_rows if row.rule_version}
        if len(rule_ids) != 1 or len(rule_versions) != 1:
            raise AppException("MATERIAL_RULE_CONFLICT", "已归档学生材料缺少唯一冻结规则，禁止补写目录")
        return {
            "gdStudentId": str(student.id), "ruleId": str(next(iter(rule_ids))),
            "ruleVersion": next(iter(rule_versions)), "created": 0,
            "total": len(existing_rows), "preservedArchived": True,
        }
    rule = active_rule(db, int(student.batch_id), lock=True)
    items = rule_items(db, int(rule.id), lock=True)
    existing = {row.material_code: row for row in existing_rows}
    created = 0
    for item in items:
        if item.material_code in existing:
            continue
        db.add(_new_material(student, item, int(rule.id), int(rule.rule_version), _actor_id(user)))
        created += 1
    db.flush()
    return {
        "gdStudentId": str(student.id), "ruleId": str(rule.id),
        "ruleVersion": int(rule.rule_version), "created": created, "total": len(items),
        "preservedArchived": False,
    }
'''
replace_once(command, old_initializer, new_initializer)
# Both batch initialization and explicit repair must skip archived students at the selection boundary.
old_filter = '''        GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.id).with_for_update()).all())
'''
new_filter = '''        GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.record_status == "ACTIVE",
        func.coalesce(GraduationStudent.stage, "") != "ARCHIVED",
        GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.id).with_for_update()).all())
'''
text = read(command)
if text.count(old_filter) != 2:
    raise SystemExit(f"{command}: expected two active-student filters, got {text.count(old_filter)}")
write(command, text.replace(old_filter, new_filter))

query = "backend/app/modules/graduation/materials/query_service.py"
replace_once(
    query,
    "from .definitions import MANIFEST_ARCHIVE_TYPE, MANIFEST_TARGET_TYPE, MODULE_CODE, STAGE_GROUPS\n",
    "from .definitions import (\n    MANIFEST_ARCHIVE_TYPE, MANIFEST_TARGET_TYPE, MODULE_CODE, REVIEW_PERMISSION_BY_CODE, STAGE_GROUPS,\n)\n",
)
old_facts_head = '''    base = base_students.with_only_columns(
        GraduationStudent.id.label("gd_student_id"),
        GraduationStudent.batch_id.label("batch_id"),
    ).subquery()
    rule = aliased(GraduationMaterialRule)
    rule_latest = aliased(GraduationMaterialRule)
    item = aliased(GraduationMaterialItem)
    material = aliased(GraduationStudentMaterial)
    version = aliased(FileVersion)
    file_obj = aliased(FileObject)
    latest_version = select(func.max(rule_latest.rule_version)).where(
        rule_latest.tenant_id == _tid(),
        rule_latest.batch_id == base.c.batch_id,
        rule_latest.status == "ENABLED",
        rule_latest.enabled.is_(True),
        rule_latest.is_deleted.is_(False),
    ).correlate(base).scalar_subquery()
    stmt = select(
'''
new_facts_head = '''    base = base_students.with_only_columns(
        GraduationStudent.id.label("gd_student_id"),
        GraduationStudent.batch_id.label("batch_id"),
        GraduationStudent.stage.label("student_stage"),
    ).subquery()
    rule = aliased(GraduationMaterialRule)
    active_rule_row = aliased(GraduationMaterialRule)
    archived_material = aliased(GraduationStudentMaterial)
    item = aliased(GraduationMaterialItem)
    material = aliased(GraduationStudentMaterial)
    version = aliased(FileVersion)
    file_obj = aliased(FileObject)
    active_rule_id = select(active_rule_row.id).where(
        active_rule_row.tenant_id == _tid(),
        active_rule_row.batch_id == base.c.batch_id,
        active_rule_row.status == "ENABLED",
        active_rule_row.enabled.is_(True),
        active_rule_row.is_deleted.is_(False),
    ).order_by(active_rule_row.rule_version.desc(), active_rule_row.id.desc()).limit(1).correlate(base).scalar_subquery()
    archived_rule_id = select(func.max(archived_material.rule_id)).where(
        archived_material.tenant_id == _tid(),
        archived_material.gd_student_id == base.c.gd_student_id,
        archived_material.archive_status.in_(("FROZEN", "ARCHIVED")),
        archived_material.is_deleted.is_(False),
    ).correlate(base).scalar_subquery()
    effective_rule_id = case(
        (func.upper(func.coalesce(base.c.student_stage, "")) == "ARCHIVED", archived_rule_id),
        else_=active_rule_id,
    )
    stmt = select(
'''
replace_once(query, old_facts_head, new_facts_head)
old_rule_join = '''    ).select_from(base).join(rule, and_(
        rule.tenant_id == _tid(),
        rule.batch_id == base.c.batch_id,
        rule.status == "ENABLED",
        rule.enabled.is_(True),
        rule.is_deleted.is_(False),
        rule.rule_version == latest_version,
    )).join(item, and_(
'''
new_rule_join = '''    ).select_from(base).join(rule, and_(
        rule.tenant_id == _tid(),
        rule.id == effective_rule_id,
        rule.is_deleted.is_(False),
    )).join(item, and_(
'''
replace_once(query, old_rule_join, new_rule_join)
replace_once(
    query,
    '''        material.gd_student_id == base.c.gd_student_id,
        material.material_code == item.material_code,
        material.is_deleted.is_(False),
''',
    '''        material.gd_student_id == base.c.gd_student_id,
        material.rule_id == rule.id,
        material.material_code == item.material_code,
        material.is_deleted.is_(False),
''',
)
old_actions = '''            if material.review_status == "PENDING" and any(has_permission(user or {}, code) for code in (
                "graduationDesign.proposal.review", "graduationDesign.final.review", "graduationDesign.review.submit",
            )):
                actions.append("review")
'''
new_actions = '''            review_permission = REVIEW_PERMISSION_BY_CODE.get(str(material.material_code or "").upper())
            if material.review_status == "PENDING" and review_permission and has_permission(user or {}, review_permission):
                actions.append("review")
'''
replace_once(query, old_actions, new_actions)
student_library_marker = '''def student_library(gd_student_id: int | None, user: dict, *, include_history: bool = True) -> dict:
'''
student_rule_helper = '''def _rule_for_student(db, student: GraduationStudent) -> GraduationMaterialRule:
    if str(student.stage or "").upper() == "ARCHIVED":
        rule_ids = set(db.scalars(select(GraduationStudentMaterial.rule_id).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.archive_status.in_(("FROZEN", "ARCHIVED")),
            GraduationStudentMaterial.rule_id.is_not(None),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).distinct()).all())
        if len(rule_ids) != 1:
            raise AppException("MATERIAL_RULE_CONFLICT", "已归档材料缺少唯一冻结规则")
        rule = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.id == int(next(iter(rule_ids))),
            GraduationMaterialRule.is_deleted.is_(False),
        )).first()
    else:
        rule = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.batch_id == int(student.batch_id or 0),
            GraduationMaterialRule.status == "ENABLED",
            GraduationMaterialRule.enabled.is_(True),
            GraduationMaterialRule.is_deleted.is_(False),
        ).order_by(GraduationMaterialRule.rule_version.desc(), GraduationMaterialRule.id.desc())).first()
    if not rule:
        raise AppException("MATERIAL_RULE_NOT_INITIALIZED", "学生材料规则不存在")
    return rule


''' + student_library_marker
replace_once(query, student_library_marker, student_rule_helper)
old_library_rule = '''        rule = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.batch_id == int(student.batch_id or 0),
            GraduationMaterialRule.status == "ENABLED",
            GraduationMaterialRule.enabled.is_(True),
            GraduationMaterialRule.is_deleted.is_(False),
        ).order_by(GraduationMaterialRule.rule_version.desc(), GraduationMaterialRule.id.desc())).first()
        if not rule:
            raise AppException("MATERIAL_RULE_NOT_INITIALIZED", "当前批次尚未初始化材料规则")
'''
replace_once(query, old_library_rule, "        rule = _rule_for_student(db, student)\n")

# Regression tests for the newly discovered archived-rule and permission-map invariants.
test = ROOT / "backend/tests/test_graduation_material_archived_rule_resolution.py"
test.write_text('''from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_review_permission_catalog_has_one_authoritative_definition():
    definitions = src("backend/app/modules/graduation/materials/definitions.py")
    command = src("backend/app/modules/graduation/materials/command_service.py")
    query = src("backend/app/modules/graduation/materials/query_service.py")
    assert "REVIEW_PERMISSION_BY_CODE = {" in definitions
    assert "_REVIEW_PERMISSION_BY_CODE = {" not in command
    assert "REVIEW_PERMISSION_BY_CODE.get" in command
    assert "REVIEW_PERMISSION_BY_CODE.get" in query


def test_review_required_custom_codes_fail_rule_validation():
    rule = src("backend/app/modules/graduation/materials/rule_service.py")
    assert "review_required and code not in REVIEW_PERMISSION_BY_CODE" in rule
    assert "未登记受支持的原子审核权限" in rule


def test_archived_students_are_never_initialized_or_repaired_against_new_rule():
    command = src("backend/app/modules/graduation/materials/command_service.py")
    initializer = command[command.index("def initialize_student_materials_in_session"):command.index("def initialize_student_materials(")]
    assert 'student.stage or "").upper() == "ARCHIVED"' in initializer
    assert '"preservedArchived": True' in initializer
    assert initializer.index('"preservedArchived": True') < initializer.index("rule = active_rule")
    assert command.count('func.coalesce(GraduationStudent.stage, "") != "ARCHIVED"') == 2


def test_archived_summary_and_library_use_frozen_rule_not_current_enabled_rule():
    query = src("backend/app/modules/graduation/materials/query_service.py")
    facts = query[query.index("def _facts"):query.index("def _student_aggregate")]
    library = query[query.index("def _rule_for_student"):query.index("def record_versions")]
    assert "archived_rule_id" in facts
    assert "effective_rule_id = case" in facts
    assert "material.rule_id == rule.id" in facts
    assert 'student.stage or "").upper() == "ARCHIVED"' in library
    assert 'archive_status.in_(("FROZEN", "ARCHIVED"))' in library
    assert "len(rule_ids) != 1" in library


def test_review_action_visibility_uses_the_same_exact_material_permission():
    query = src("backend/app/modules/graduation/materials/query_service.py")
    assert "review_permission = REVIEW_PERMISSION_BY_CODE.get" in query
    assert "has_permission(user or {}, review_permission)" in query
    assert '"graduationDesign.proposal.review", "graduationDesign.final.review"' not in query
''', encoding="utf-8")

for target in (definitions, rule, command, query):
    compile(read(target), target, "exec")
print("graduation archived-rule closeout patch applied")
