"""实施与预设中心真实编排服务。

规则：预设配置与真实师生数据分离；组织/角色先 dry-run 候选、人工确认，再同事务安装。
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import (College, Major, NotificationTemplate, Role, RoleWorkbenchConfig, SchoolClass, StudentProfile,
                        SystemBusinessRelationBatch, SystemBusinessRelationInstallItem,
                        SystemImplementationCheck, SystemImplementationProject,
                        SystemImplementationSection, SystemPresetInstallation, User,
                        WorkflowDefinition)
from app.services import audit_log

SECTION_DEFINITIONS = (
    ("school_opening", "学校开通", {"deliveryMode": "STANDARD_WEEK"}),
    ("role_permission", "角色与权限", {"templateMode": "RECOMMENDED", "separationOfDuties": True}),
    ("organization", "组织结构", {"levels": ["COLLEGE", "MAJOR", "GRADE", "CLASS"], "organizationModel": "COLLEGE_MAJOR_CLASS", "inferFromImport": True}),
    ("identity_import", "师生导入", {"duplicatePolicy": "REJECT", "initialPasswordPolicy": "RANDOM"}),
    ("business_relation", "业务关系", {"relationSource": "IMPORT_CONFIRM", "requireRealRelation": True}),
    ("workflow", "流程", {"approvalMode": "RECOMMENDED_DISABLED", "policyConfirmationRequired": True}),
    ("dictionary_numbering", "字典与编号", {"useNationalCodes": True, "numberingOwner": "INFORMATION_CENTER"}),
    ("security_audit", "安全与审计", {"firstLoginChangePassword": True, "exportWatermark": True, "sessionMinutes": 120}),
    ("menu_workbench", "菜单与工作台", {"followActiveRole": True, "homeStrategy": "ROLE_PRESET"}),
    ("message_notification", "消息与通知", {"inAppEnabled": True, "primaryChannel": "IN_APP", "overdueReminder": True}),
    ("go_live_check", "上线检查", {"blockerMustPass": True, "acceptanceRole": "SCHOOL_ADMIN"}),
    ("module_business", "模块业务", {"modules": [], "includeProfessionalStandards": True}),
)
SECTION_CODES = {x[0] for x in SECTION_DEFINITIONS}
PRESET_CATALOG = (
    {"code": "HIGHER_VOCATIONAL", "name": "高职标准版", "version": "2026.1",
     "schoolLevel": "HIGHER_VOCATIONAL", "deliveryDays": 7,
     "description": "完整覆盖迎新、学工、教务、实习、毕设和就业，专业教学标准入口默认开启。"},
    {"code": "SECONDARY_VOCATIONAL", "name": "中职标准版", "version": "2026.1",
     "schoolLevel": "SECONDARY_VOCATIONAL", "deliveryDays": 7,
     "description": "按中等职业学校组织与育人场景开局，毕设模块默认不启用。"},
    {"code": "PILOT_FAST", "name": "试点快速版", "version": "2026.1", "schoolLevel": "ANY",
     "deliveryDays": 2, "description": "先开学工、教务和实习核心闭环，验收后再按版本扩容。"},
    {"code": "DEMO", "name": "演示版", "version": "2026.1", "schoolLevel": "ANY",
     "deliveryDays": 1, "description": "全模块展示但限制容量，不把演示数据伪装成学校正式数据。"},
    {"code": "PRIVATE", "name": "私有化版", "version": "2026.1", "schoolLevel": "ANY",
     "deliveryDays": 7, "description": "增加部署、域名、备份、监控、接口和等保责任确认。"},
)

PROFILE_OVERRIDES = {
    "HIGHER_VOCATIONAL": {
        "school_opening": {"schoolLevel": "HIGHER_VOCATIONAL", "deliveryMode": "STANDARD_WEEK", "targetDays": 7},
        "module_business": {"modules": ["ORIENTATION", "STUDENT_AFFAIRS", "ACADEMIC_AFFAIRS", "INTERNSHIP", "GRADUATION", "EMPLOYMENT"], "includeProfessionalStandards": True},
    },
    "SECONDARY_VOCATIONAL": {
        "school_opening": {"schoolLevel": "SECONDARY_VOCATIONAL", "deliveryMode": "STANDARD_WEEK", "targetDays": 7},
        "module_business": {"modules": ["ORIENTATION", "STUDENT_AFFAIRS", "ACADEMIC_AFFAIRS", "INTERNSHIP", "EMPLOYMENT"], "includeProfessionalStandards": True},
    },
    "PILOT_FAST": {
        "school_opening": {"schoolLevel": "UNCONFIRMED", "deliveryMode": "PILOT_FAST", "targetDays": 2},
        "module_business": {"modules": ["STUDENT_AFFAIRS", "ACADEMIC_AFFAIRS", "INTERNSHIP"], "includeProfessionalStandards": True},
    },
    "DEMO": {
        "school_opening": {"schoolLevel": "UNCONFIRMED", "deliveryMode": "DEMO", "targetDays": 1},
        "identity_import": {"duplicatePolicy": "REJECT", "initialPasswordPolicy": "RANDOM", "formalDataAllowed": False},
        "module_business": {"modules": ["ORIENTATION", "STUDENT_AFFAIRS", "ACADEMIC_AFFAIRS", "INTERNSHIP", "GRADUATION", "EMPLOYMENT"], "includeProfessionalStandards": True},
    },
    "PRIVATE": {
        "school_opening": {"schoolLevel": "UNCONFIRMED", "deliveryMode": "PRIVATE", "targetDays": 7, "deploymentAcceptanceRequired": True},
        "security_audit": {"firstLoginChangePassword": True, "exportWatermark": True, "deploymentMode": "PRIVATE", "backupVerified": False},
        "module_business": {"modules": ["ORIENTATION", "STUDENT_AFFAIRS", "ACADEMIC_AFFAIRS", "INTERNSHIP", "GRADUATION", "EMPLOYMENT"], "includeProfessionalStandards": True},
    },
}

SECTION_QUESTIONS = {
    "school_opening": [
        {"key": "schoolLevel", "label": "学校层次", "type": "select", "required": True,
         "options": [["HIGHER_VOCATIONAL", "高职"], ["SECONDARY_VOCATIONAL", "中职"], ["UNCONFIRMED", "开户后确认"]]},
        {"key": "deliveryMode", "label": "实施节奏", "type": "select", "required": True,
         "options": [["STANDARD_WEEK", "标准一周"], ["PILOT_FAST", "两天试点"], ["DEMO", "演示"], ["PRIVATE", "私有化"]]},
        {"key": "targetDays", "label": "计划交付天数", "type": "number", "required": True, "min": 1, "max": 30},
    ],
    "role_permission": [
        {"key": "templateMode", "label": "角色模板策略", "type": "select", "required": True,
         "options": [["RECOMMENDED", "安装推荐角色"], ["MINIMUM", "最小角色集"]]},
        {"key": "separationOfDuties", "label": "管理员与审计员职责分离", "type": "boolean", "required": True},
    ],
    "organization": [
        {"key": "organizationModel", "label": "教学组织模型", "type": "select", "required": True,
         "options": [["COLLEGE_MAJOR_CLASS", "学校—学院—专业—班级"], ["DEPARTMENT_CLASS", "学校—部门—班级"]]},
        {"key": "inferFromImport", "label": "从师生文件推导组织候选", "type": "boolean", "required": True},
    ],
    "identity_import": [
        {"key": "duplicatePolicy", "label": "重复账号处理", "type": "select", "required": True,
         "options": [["REJECT", "阻断并回执"], ["SKIP", "跳过既有账号"]]},
        {"key": "initialPasswordPolicy", "label": "初始密码策略", "type": "select", "required": True,
         "options": [["RANDOM", "随机一次性密码"], ["ACTIVATION", "激活链接"]]},
    ],
    "business_relation": [
        {"key": "relationSource", "label": "业务关系来源", "type": "select", "required": True,
         "options": [["IMPORT_CONFIRM", "导入后人工确认"], ["EXTERNAL_SYNC", "教务系统同步"]]},
        {"key": "requireRealRelation", "label": "禁止用角色名虚构业务关系", "type": "boolean", "required": True},
    ],
    "workflow": [
        {"key": "approvalMode", "label": "流程开局策略", "type": "select", "required": True,
         "options": [["RECOMMENDED_DISABLED", "安装推荐模板、确认后启用"], ["SCHOOL_DEFINED", "学校自行配置"]]},
        {"key": "policyConfirmationRequired", "label": "学校政策确认后才能启用", "type": "boolean", "required": True},
    ],
    "dictionary_numbering": [
        {"key": "useNationalCodes", "label": "优先使用国家/行业标准代码", "type": "boolean", "required": True},
        {"key": "numberingOwner", "label": "校内编号规则责任部门", "type": "select", "required": True,
         "options": [["INFORMATION_CENTER", "信息中心"], ["ACADEMIC_AFFAIRS", "教务处"], ["SCHOOL_OFFICE", "学校办公室"]]},
    ],
    "security_audit": [
        {"key": "firstLoginChangePassword", "label": "首次登录必须改密", "type": "boolean", "required": True},
        {"key": "exportWatermark", "label": "敏感导出添加水印", "type": "boolean", "required": True},
        {"key": "sessionMinutes", "label": "会话有效分钟数", "type": "number", "required": True, "min": 15, "max": 1440},
    ],
    "menu_workbench": [
        {"key": "followActiveRole", "label": "角色切换时同步菜单和工作台", "type": "boolean", "required": True},
        {"key": "homeStrategy", "label": "首页策略", "type": "select", "required": True,
         "options": [["ROLE_PRESET", "按角色推荐"], ["SCHOOL_CUSTOM", "学校后期自定义"]]},
    ],
    "message_notification": [
        {"key": "primaryChannel", "label": "默认通知渠道", "type": "select", "required": True,
         "options": [["IN_APP", "站内消息"], ["SMS", "短信（需配置）"], ["WECHAT", "微信（需配置）"]]},
        {"key": "overdueReminder", "label": "启用超时催办", "type": "boolean", "required": True},
    ],
    "go_live_check": [
        {"key": "blockerMustPass", "label": "阻断项全部通过才能验收", "type": "boolean", "required": True},
        {"key": "acceptanceRole", "label": "最终验收角色", "type": "select", "required": True,
         "options": [["SCHOOL_ADMIN", "学校管理员"], ["LEADER", "校领导"]]},
    ],
    "module_business": [
        {"key": "modules", "label": "首期开通模块", "type": "multiselect", "required": True,
         "options": [["ORIENTATION", "迎新"], ["STUDENT_AFFAIRS", "学工"], ["ACADEMIC_AFFAIRS", "教务"], ["INTERNSHIP", "实习"], ["GRADUATION", "毕设"], ["EMPLOYMENT", "就业"]]},
        {"key": "includeProfessionalStandards", "label": "启用专业目录与专业教学标准入口", "type": "boolean", "required": True},
    ],
}


def _tid() -> int:
    value = current_tenant_id()
    if value is None:
        raise AppException("TENANT_NOT_FOUND", "当前请求没有学校租户上下文")
    return int(value)


def _actor(user: dict) -> int | None:
    try:
        return int(user.get("userId") or user.get("id"))
    except (TypeError, ValueError):
        return None


def _digest(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _contains_secret(value) -> bool:
    if isinstance(value, dict):
        return any(str(k).lower() in {"password", "idcard", "token", "secret", "access_token", "refresh_token"}
                   or _contains_secret(v) for k, v in value.items())
    return isinstance(value, list) and any(_contains_secret(x) for x in value)


def _project(db, project_id: int, tenant_id: int):
    row = db.scalars(select(SystemImplementationProject).where(
        SystemImplementationProject.id == project_id, SystemImplementationProject.tenant_id == tenant_id,
        SystemImplementationProject.is_deleted.is_(False))).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", "实施项目不存在")
    return row


def _sections(db, project_id: int, tenant_id: int):
    return db.scalars(select(SystemImplementationSection).where(
        SystemImplementationSection.project_id == project_id,
        SystemImplementationSection.tenant_id == tenant_id,
        SystemImplementationSection.is_deleted.is_(False)).order_by(SystemImplementationSection.id)).all()


def _row(project, sections, checks=None) -> dict:
    checks = checks or []
    return {"id": str(project.id), "projectNo": project.project_no, "projectName": project.project_name,
            "profileCode": project.profile_code, "status": project.status, "version": project.version,
            "changeSourceInstallationId": str(project.change_source_installation_id or ""),
            "targetDate": str(project.target_date or ""), "progress": round(len(sections) * 100 / len(SECTION_DEFINITIONS)),
            "sections": [{"code": x.section_code, "status": x.status, "source": x.source,
                          "config": x.config_json, "version": x.version} for x in sections],
            "checks": checks, "appliedAt": str(project.applied_at or "")[:19],
            "acceptedAt": str(project.accepted_at or "")[:19],
            "acceptanceDigest": project.acceptance_digest or "",
            "acceptanceSummary": project.acceptance_summary}


def preset_catalog() -> dict:
    return {"profiles": list(PRESET_CATALOG),
            "sections": [{"code": code, "name": name, "defaultConfig": defaults,
                          "questions": SECTION_QUESTIONS.get(code, [])}
                         for code, name, defaults in SECTION_DEFINITIONS],
            "standardPolicy": {"professionalStandards": True, "storeSourceMetadata": True,
                               "republishOriginal": False}}


def current_project() -> dict | None:
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = db.scalars(select(SystemImplementationProject).where(
            SystemImplementationProject.tenant_id == tenant_id,
            SystemImplementationProject.is_deleted.is_(False)).order_by(SystemImplementationProject.id.desc())).first()
        if not project: return None
        checks = db.scalars(select(SystemImplementationCheck).where(
            SystemImplementationCheck.tenant_id == tenant_id,
            SystemImplementationCheck.project_id == project.id,
            SystemImplementationCheck.is_deleted.is_(False))).all()
        check_rows = [{"code": x.check_code, "name": x.check_name, "result": x.result,
                       "severity": x.severity, "ownerRole": x.owner_role,
                       "confirmedBy": x.confirmed_by, "confirmedAt": str(x.confirmed_at or ""),
                       "comment": x.comment, "evidence": x.evidence_json} for x in checks]
        return _row(project, _sections(db, project.id, tenant_id), check_rows)
    finally:
        db.close()


def create_project(user: dict, body: dict) -> dict:
    tenant_id = _tid(); profile = str(body.get("profileCode") or "HIGHER_VOCATIONAL").upper()
    if profile not in {x["code"] for x in PRESET_CATALOG}:
        raise AppException("VALIDATION_ERROR", "预设方案不存在")
    name = str(body.get("projectName") or "学校首次实施").strip()
    if not 1 <= len(name) <= 100: raise AppException("VALIDATION_ERROR", "项目名称长度须为1—100字")
    target = None
    if body.get("targetDate"):
        try: target = date.fromisoformat(str(body["targetDate"]))
        except ValueError as exc: raise AppException("VALIDATION_ERROR", "目标日期格式必须为YYYY-MM-DD") from exc
    db = get_sessionmaker()()
    try:
        active = db.scalars(select(SystemImplementationProject).where(
            SystemImplementationProject.tenant_id == tenant_id,
            SystemImplementationProject.status.notin_(("ACCEPTED", "CANCELLED")),
            SystemImplementationProject.is_deleted.is_(False))).first()
        if active: raise AppException("DATA_CONFLICT", "本校已有进行中的实施项目")
        now = datetime.utcnow(); actor = _actor(user)
        project = SystemImplementationProject(tenant_id=tenant_id, project_no=f"IMP-{now:%Y%m%d%H%M%S%f}",
            project_name=name, profile_code=profile, status="CONFIGURING", owner_id=actor,
            target_date=target, created_by=actor, updated_by=actor)
        db.add(project); db.flush()
        for code, _name, defaults in SECTION_DEFINITIONS:
            config = {**defaults, **PROFILE_OVERRIDES.get(profile, {}).get(code, {})}
            if code == "school_opening": config["profileCode"] = profile
            db.add(SystemImplementationSection(tenant_id=tenant_id, project_id=project.id,
                section_code=code, config_json=config, source="RECOMMENDED", status="CONFIGURED",
                created_by=actor, updated_by=actor))
        db.commit()
        audit_log.record("IMPLEMENTATION_PROJECT_CREATED", f"implementation-project:{project.id}",
                         {"profileCode": profile})
        return current_project()
    except Exception:
        db.rollback(); raise
    finally: db.close()


def save_section(user: dict, project_id: int, code: str, body: dict) -> dict:
    code = code.lower()
    if code not in SECTION_CODES: raise AppException("VALIDATION_ERROR", "未知配置类别")
    config = body.get("config")
    if not isinstance(config, dict) or _contains_secret(config):
        raise AppException("VALIDATION_ERROR", "配置必须是对象，且不得包含凭证、令牌或证件字段")
    for question in SECTION_QUESTIONS.get(code, []):
        key, value = question["key"], config.get(question["key"])
        if question.get("required") and value in (None, "", []):
            raise AppException("VALIDATION_ERROR", f"{question['label']}为必填项")
        if question["type"] in {"select", "multiselect"}:
            allowed = {item[0] for item in question.get("options") or []}
            values = value if isinstance(value, list) else [value]
            if any(item not in allowed for item in values):
                raise AppException("VALIDATION_ERROR", f"{question['label']}包含无效选项")
        elif question["type"] == "boolean" and not isinstance(value, bool):
            raise AppException("VALIDATION_ERROR", f"{question['label']}必须选择是或否")
        elif question["type"] == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise AppException("VALIDATION_ERROR", f"{question['label']}必须是数字")
            if value < question.get("min", value) or value > question.get("max", value):
                raise AppException("VALIDATION_ERROR", f"{question['label']}超出允许范围")
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if project.status not in {"DRAFT", "CONFIGURING", "PREVIEW_READY"}:
            raise AppException("DATA_CONFLICT", "当前状态不能修改配置")
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新")
        section = next(x for x in _sections(db, project.id, tenant_id) if x.section_code == code)
        before = _digest(section.config_json); section.config_json = config; section.source = "USER"
        section.version += 1; section.updated_by = _actor(user)
        project.status = "CONFIGURING"; project.preview_json = None; project.preview_hash = None; project.version += 1
        db.commit(); audit_log.record("IMPLEMENTATION_SECTION_SAVED", f"implementation-project:{project.id}:{code}",
                                      {"beforeHash": before, "afterHash": _digest(config)})
        return current_project()
    except Exception:
        db.rollback(); raise
    finally: db.close()


def preview_project(user: dict, project_id: int) -> dict:
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if project.status not in {"DRAFT", "CONFIGURING", "PREVIEW_READY"}:
            raise AppException("DATA_CONFLICT", "当前状态不能预览")
        sections = _sections(db, project.id, tenant_id); missing = SECTION_CODES - {x.section_code for x in sections}
        preview = {"profileCode": project.profile_code, "presetVersion": "2026.1",
                   "missingSections": sorted(missing), "blocked": bool(missing),
                   "snapshot": {x.section_code: x.config_json for x in sections},
                   "note": "配置快照与真实师生数据分离；组织和角色须经匹配确认后安装。"}
        project.preview_json = preview; project.preview_hash = _digest(preview); project.status = "PREVIEW_READY"
        project.version += 1; project.updated_by = _actor(user); db.commit()
        audit_log.record("IMPLEMENTATION_PREVIEW_CREATED", f"implementation-project:{project.id}",
                         {"previewHash": project.preview_hash, "blocked": bool(missing)})
        return {"preview": preview, "previewHash": project.preview_hash, "project": current_project()}
    except Exception:
        db.rollback(); raise
    finally: db.close()


def apply_snapshot(user: dict, project_id: int, body: dict) -> dict:
    if str(body.get("confirmText") or "").strip() != "确认应用":
        raise AppException("VALIDATION_ERROR", "请输入“确认应用”")
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 2: raise AppException("VALIDATION_ERROR", "请填写应用原因")
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if project.status == "APPLIED":
            from app.services.runtime_preset_install_service import status as runtime_status
            return {"idempotent": True, "snapshotOnly": False, "runtime": runtime_status(project_id)}
        if project.status != "PREVIEW_READY" or not project.preview_json or project.preview_json.get("blocked"):
            raise AppException("DATA_CONFLICT", "预览未就绪或有阻断项")
        now = datetime.utcnow(); actor = _actor(user)
        active = db.scalars(select(SystemPresetInstallation).where(
            SystemPresetInstallation.tenant_id == tenant_id,
            SystemPresetInstallation.status == "APPLIED",
            SystemPresetInstallation.is_deleted.is_(False))).all()
        for old in active: old.status = "SUPERSEDED"; old.version += 1
        item = SystemPresetInstallation(tenant_id=tenant_id, installation_no=f"INS-{now:%Y%m%d%H%M%S}",
            project_id=project.id, parent_id=active[0].id if active else None,
            change_type="CHANGE" if active else "INITIAL", source_profile=project.profile_code,
            snapshot_json=project.preview_json, snapshot_hash=project.preview_hash,
            status="APPLIED", reason=reason, applied_at=now, created_by=actor, updated_by=actor)
        db.add(item)
        from app.services.runtime_preset_install_service import install_in_session
        runtime = install_in_session(db, user, project, _sections(db, project.id, tenant_id))
        project.status = "APPLIED"; project.applied_at = now; project.version += 1
        db.commit(); db.refresh(item)
        audit_log.record("IMPLEMENTATION_PRESET_APPLIED", f"implementation-project:{project.id}",
                         {"installationNo": item.installation_no, "reason": reason})
        return {"id": str(item.id), "installationNo": item.installation_no,
                "idempotent": False, "snapshotOnly": False, "runtime": runtime}
    except Exception:
        db.rollback(); raise
    finally: db.close()


def _norm(value: object) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")).strip()).lower()


def _cid(kind: str, name: str, parent: str = "", college: str = "") -> str:
    return f"{kind}:{hashlib.sha1(f'{kind}|{_norm(college)}|{_norm(parent)}|{_norm(name)}'.encode()).hexdigest()[:14]}"


def _org_code(prefix: str, name: str, parent: str = "") -> str:
    return f"{prefix}-{hashlib.sha1(f'{prefix}|{_norm(parent)}|{_norm(name)}'.encode()).hexdigest()[:10].upper()}"


def _role_suggestions(position: str, department: str) -> list[str]:
    text = f"{position} {department}"
    rules = (("辅导员|班主任", "COUNSELOR"), ("教务处|教务管理员", "ACADEMIC_ADMIN"),
             ("任课教师|专业课教师|公共课教师", "ACADEMIC_TEACHER"),
             ("学工处|学工管理员", "STUDENT_AFFAIRS_ADMIN"), ("心理", "PSYCHOLOGY_TEACHER"),
             ("资助", "FUNDING_TEACHER"), ("宿管|宿舍管理员", "DORM_MANAGER"),
             ("团委", "YOUTH_LEAGUE"), ("人事|组织人事", "ORG_PERSONNEL"),
             ("毕设导师|毕业设计导师", "GD_MENTOR"), ("实习指导|实习导师", "INTERN_MENTOR"),
             ("就业", "EMPLOYMENT_TEACHER"), ("学院负责人|学院教务员|院长", "COLLEGE_ADMIN"),
             ("校领导|院领导", "LEADER"))
    return [code for pattern, code in rules if re.search(pattern, text)]


def _mapping_section(db, project_id: int, tenant_id: int):
    # 智能匹配属于十二类预设中的“师生导入”，不额外制造第十三类配置。
    return db.scalars(select(SystemImplementationSection).where(
        SystemImplementationSection.tenant_id == tenant_id,
        SystemImplementationSection.project_id == project_id,
        SystemImplementationSection.section_code == "identity_import",
        SystemImplementationSection.is_deleted.is_(False))).first()


def discover_batch(user: dict, project_id: int, batch_no: str) -> dict:
    """从统一身份导入预检批次生成组织树和角色候选；只读现有主数据。"""
    from app.services.identity_import_file_service import get_batch

    tenant_id = _tid(); entry = get_batch(user, tenant_id, batch_no); payload = entry["payload"]
    db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if project.status not in {"DRAFT", "CONFIGURING", "PREVIEW_READY"}:
            raise AppException("DATA_CONFLICT", "当前状态不能生成匹配候选")
        colleges = db.scalars(select(College).where(College.tenant_id == tenant_id, College.is_deleted.is_(False))).all()
        majors = db.scalars(select(Major).where(Major.tenant_id == tenant_id, Major.is_deleted.is_(False))).all()
        classes = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id, SchoolClass.is_deleted.is_(False))).all()
        college_by_id = {x.id: x for x in colleges}; major_by_id = {x.id: x for x in majors}

        sources: dict[tuple, dict] = {}
        for row in payload.get("students") or []:
            college = str(row.get("collegeName") or "").strip(); major = str(row.get("majorName") or "").strip()
            school_class = str(row.get("className") or "").strip(); row_no = int(row.get("_rowNo") or 0)
            if college: sources.setdefault(("COLLEGE", _norm(college)), {"kind": "COLLEGE", "name": college, "rows": []})["rows"].append(row_no)
            if major: sources.setdefault(("MAJOR", _norm(college), _norm(major)), {"kind": "MAJOR", "name": major, "parent": college, "rows": []})["rows"].append(row_no)
            if school_class:
                item = sources.setdefault(("CLASS", _norm(college), _norm(major), _norm(school_class)),
                    {"kind": "CLASS", "name": school_class, "parent": major, "college": college, "rows": [], "grades": []})
                item["rows"].append(row_no)
                if row.get("grade") and str(row["grade"]) not in item["grades"]: item["grades"].append(str(row["grade"]))
        for row in payload.get("teachers") or []:
            department = str(row.get("departmentName") or "").strip()
            if department:
                item = sources.setdefault(("COLLEGE", _norm(department)),
                    {"kind": "COLLEGE", "name": department, "rows": [], "sourceKind": "DEPARTMENT"})
                item["rows"].append(int(row.get("_rowNo") or 0))

        candidates = []; blockers = []
        for source in sources.values():
            kind, name, parent, college = source["kind"], source["name"], source.get("parent", ""), source.get("college", "")
            if kind == "COLLEGE": matches = [x for x in colleges if _norm(x.college_name) == _norm(name)]
            elif kind == "MAJOR":
                matches = [x for x in majors if _norm(x.major_name) == _norm(name) and
                           (not parent or _norm(college_by_id.get(x.college_id).college_name if college_by_id.get(x.college_id) else "") == _norm(parent))]
            else:
                matches = [x for x in classes if _norm(x.class_name) == _norm(name) and
                           (not parent or _norm(major_by_id.get(x.major_id).major_name if major_by_id.get(x.major_id) else "") == _norm(parent))]
            missing_parent = kind in {"MAJOR", "CLASS"} and not parent and len(matches) != 1
            if len(matches) == 1: recommendation = {"action": "MATCH", "targetId": str(matches[0].id), "confidence": 1.0}
            elif not matches and not missing_parent: recommendation = {"action": "CREATE", "targetId": "", "confidence": 1.0}
            else:
                recommendation = {"action": "REVIEW", "targetId": "", "confidence": 0.0}
                blockers.append({"candidateId": _cid(kind, name, parent, college),
                                 "code": "MISSING_PARENT" if missing_parent else "AMBIGUOUS_NAME",
                                 "message": "缺少上级组织" if missing_parent else "存在多个同名组织，必须人工选择"})
            candidates.append({"candidateId": _cid(kind, name, parent, college), "entityType": kind,
                "name": name, "parentName": parent, "collegeName": college,
                "grade": (source.get("grades") or [""])[0], "sourceRows": sorted(set(source["rows"])),
                "sourceKind": source.get("sourceKind", "STUDENT_IMPORT"),
                "matches": [{"id": str(x.id), "name": getattr(x, "college_name", None) or getattr(x, "major_name", None) or getattr(x, "class_name", None)} for x in matches],
                "recommendation": recommendation})

        roles = []
        for teacher in payload.get("teachers") or []:
            current = str(teacher.get("roleCodes") or "").strip()
            suggestions = [] if current else _role_suggestions(str(teacher.get("positionName") or ""),
                                                               str(teacher.get("departmentName") or ""))
            roles.append({"loginName": teacher.get("loginName"), "name": teacher.get("name"),
                          "positionName": teacher.get("positionName") or "", "currentRoleCodes": current,
                          "suggestedRoleCodes": suggestions, "requiresConfirmation": not bool(current)})
            if not current and not suggestions:
                blockers.append({"candidateId": f"ROLE:{teacher.get('loginName')}", "code": "ROLE_NOT_INFERRED",
                                 "message": "教师未填写角色，岗位名称也无法匹配预设角色"})
        config = {"batchNo": entry["batchNo"], "fileName": entry["fileName"], "fileSha256": entry["fileSha256"],
                  "status": "DISCOVERED", "candidates": candidates, "roleSuggestions": roles,
                  "organizationDecisions": [], "roleDecisions": [], "conflicts": blockers,
                  "summary": {"students": len(payload.get("students") or []), "teachers": len(payload.get("teachers") or []),
                              "organizations": len(candidates), "blockers": len(blockers)}}
        section = _mapping_section(db, project.id, tenant_id); actor = _actor(user)
        section_config = dict(section.config_json or {})
        section_config["mapping"] = config
        section.config_json = section_config; section.source = "INFERRED"; section.status = "CONFIGURED"
        section.version += 1; section.updated_by = actor
        project.status = "CONFIGURING"; project.preview_json = None; project.preview_hash = None; project.version += 1
        db.commit(); audit_log.record("IMPLEMENTATION_MAPPING_DISCOVERED", f"implementation-project:{project.id}",
                                      {"batchNo": entry["batchNo"], "fileSha256": entry["fileSha256"], "summary": config["summary"]})
        return {**config, "projectVersion": project.version, "sectionVersion": section.version}
    except Exception:
        db.rollback(); raise
    finally: db.close()


def confirm_mapping(user: dict, project_id: int, body: dict) -> dict:
    from app.services.saas_role_templates import role_codes_from_row

    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新候选")
        section = _mapping_section(db, project.id, tenant_id)
        if not section: raise AppException("DATA_NOT_FOUND", "请先生成匹配候选")
        section_config = dict(section.config_json or {})
        config = dict(section_config.get("mapping") or {})
        if not config.get("candidates"):
            raise AppException("DATA_NOT_FOUND", "请先生成匹配候选")
        candidates = {x["candidateId"]: x for x in config["candidates"]}
        decisions = {}
        for item in body.get("organizationDecisions") or []:
            cid, action = str(item.get("candidateId") or ""), str(item.get("action") or "").upper()
            if cid not in candidates or action not in {"MATCH", "CREATE", "IGNORE"}:
                raise AppException("VALIDATION_ERROR", "存在未知组织候选或动作")
            candidate = candidates[cid]
            if action == "MATCH":
                target_id = str(item.get("targetId") or "")
                allowed = {str(match["id"]) for match in candidate.get("matches") or []}
                if not target_id:
                    raise AppException("VALIDATION_ERROR", "匹配既有组织必须选择目标")
                if target_id not in allowed:
                    raise AppException("VALIDATION_ERROR", "所选组织不在本候选的可匹配范围内")
            if action == "CREATE" and candidate["entityType"] in {"MAJOR", "CLASS"} \
                    and not str(candidate.get("parentName") or "").strip():
                raise AppException("VALIDATION_ERROR", f"{candidate['name']} 缺少上级组织，不能直接创建")
            decisions[cid] = {"candidateId": cid, "action": action, "targetId": str(item.get("targetId") or "")}
        if body.get("acceptRecommendations"):
            for cid, candidate in candidates.items():
                rec = candidate["recommendation"]
                if cid not in decisions and rec["action"] in {"MATCH", "CREATE"}:
                    decisions[cid] = {"candidateId": cid, "action": rec["action"], "targetId": rec.get("targetId", "")}
        undecided = sorted(set(candidates) - set(decisions))
        if undecided: raise AppException("VALIDATION_ERROR", "仍有组织候选未确认", {"candidateIds": undecided})

        supplied = {str(x.get("loginName") or ""): x.get("roleCodes") for x in body.get("roleDecisions") or []}
        role_decisions = []
        for item in config["roleSuggestions"]:
            raw = supplied.get(str(item["loginName"]), item["currentRoleCodes"] or item["suggestedRoleCodes"])
            try: codes = role_codes_from_row({"roleCodes": raw})
            except AppException as exc: raise AppException("VALIDATION_ERROR", f"教师 {item['loginName']} 角色未确认：{exc.message}") from exc
            role_decisions.append({"loginName": item["loginName"], "roleCodes": codes})
        config.update({"organizationDecisions": list(decisions.values()), "roleDecisions": role_decisions,
                       "conflicts": [], "status": "CONFIRMED"})
        section_config["mapping"] = config
        section.config_json = section_config; section.source = "CONFIRMED"; section.version += 1; project.version += 1
        section.updated_by = project.updated_by = _actor(user); db.commit()
        audit_log.record("IMPLEMENTATION_MAPPING_CONFIRMED", f"implementation-project:{project.id}",
                         {"batchNo": config["batchNo"], "organizations": len(decisions), "teachers": len(role_decisions)})
        return {**config, "projectVersion": project.version, "sectionVersion": section.version}
    except Exception:
        db.rollback(); raise
    finally: db.close()


def apply_mapping(user: dict, project_id: int, body: dict) -> dict:
    from app.services.identity_import_file_service import get_batch, refresh_batch_report
    from app.services.identity_import_service import preview_identity_import
    from app.services.saas_role_service import ensure_builtin_roles

    if str(body.get("confirmText") or "").strip() != "确认安装组织与角色":
        raise AppException("VALIDATION_ERROR", "请输入“确认安装组织与角色”")
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 2: raise AppException("VALIDATION_ERROR", "请填写安装原因")
    tenant_id = _tid(); db = get_sessionmaker()(); entry = None; config = None
    try:
        project = _project(db, project_id, tenant_id)
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新")
        section = _mapping_section(db, project.id, tenant_id)
        section_config = dict(section.config_json or {}) if section else {}
        config = dict(section_config.get("mapping") or {})
        if config.get("status") == "APPLIED":
            entry = get_batch(user, tenant_id, config["batchNo"])
            role_updates = {x["loginName"]: x["roleCodes"] for x in config.get("roleDecisions") or []}
            for teacher in entry["payload"].get("teachers") or []:
                if teacher.get("loginName") in role_updates:
                    teacher["roleCodes"] = role_updates[teacher["loginName"]]
            report = preview_identity_import(user, entry["payload"], pre_errors=entry.get("preErrors") or [])
            refreshed = refresh_batch_report(user, tenant_id, entry["batchNo"], report)
            return {"idempotent": True, "batchNo": entry["batchNo"],
                    "mapping": config.get("appliedSummary") or {}, "refreshedPreview": refreshed}
        if config.get("status") != "CONFIRMED": raise AppException("DATA_CONFLICT", "匹配决定尚未全部确认")
        entry = get_batch(user, tenant_id, config["batchNo"])
        if entry["fileSha256"] != config["fileSha256"]:
            raise AppException("IDEMPOTENCY_CONFLICT", "导入文件指纹与候选版本不一致")
        candidates = {x["candidateId"]: x for x in config["candidates"]}; actor = _actor(user)
        created = {"colleges": 0, "majors": 0, "classes": 0}
        resolved_colleges = {}; resolved_majors = {}
        role_report = ensure_builtin_roles(db, tenant_id)
        from app.services.org_master_service import apply_org_node_in_session

        for decision in config["organizationDecisions"]:
            candidate = candidates[decision["candidateId"]]
            if candidate["entityType"] != "COLLEGE" or decision["action"] == "IGNORE": continue
            if decision["action"] == "MATCH":
                target = db.scalars(select(College).where(College.id == int(decision["targetId"]),
                    College.tenant_id == tenant_id, College.is_deleted.is_(False))).first()
                if not target: raise AppException("DATA_CONFLICT", "所选学院/部门已不存在")
            else:
                matches = db.scalars(select(College).where(College.tenant_id == tenant_id,
                    College.college_name == candidate["name"], College.is_deleted.is_(False))).all()
                if len(matches) > 1: raise AppException("DATA_CONFLICT", f"学院/部门同名冲突：{candidate['name']}")
                if matches:
                    target = matches[0]
                else:
                    result = apply_org_node_in_session(
                        db, node_type="COLLEGE", name=candidate["name"],
                        code=_org_code("ORG", candidate["name"]),
                        tenant_id=tenant_id, commit=False,
                        extras={"created_by": actor, "updated_by": actor},
                    )
                    target = result["row"]
                    created["colleges"] += 1
            resolved_colleges[_norm(candidate["name"])] = target.id

        for decision in config["organizationDecisions"]:
            candidate = candidates[decision["candidateId"]]
            if candidate["entityType"] != "MAJOR" or decision["action"] == "IGNORE": continue
            if decision["action"] == "MATCH":
                target = db.scalars(select(Major).where(Major.id == int(decision["targetId"]),
                    Major.tenant_id == tenant_id, Major.is_deleted.is_(False))).first()
                if not target: raise AppException("DATA_CONFLICT", "所选专业已不存在")
            else:
                parent_id = resolved_colleges.get(_norm(candidate["parentName"]))
                if not parent_id:
                    parent = db.scalars(select(College).where(College.tenant_id == tenant_id,
                        College.college_name == candidate["parentName"], College.is_deleted.is_(False))).first()
                    parent_id = parent.id if parent else None
                if not parent_id: raise AppException("DATA_CONFLICT", f"专业缺少学院：{candidate['name']}")
                matches = db.scalars(select(Major).where(Major.tenant_id == tenant_id, Major.college_id == parent_id,
                    Major.major_name == candidate["name"], Major.is_deleted.is_(False))).all()
                if len(matches) > 1: raise AppException("DATA_CONFLICT", f"同学院专业重名：{candidate['name']}")
                if matches:
                    target = matches[0]
                else:
                    result = apply_org_node_in_session(
                        db, node_type="MAJOR", name=candidate["name"], parent_id=parent_id,
                        code=_org_code("MAJ", candidate["name"], candidate["parentName"]),
                        tenant_id=tenant_id, commit=False,
                        extras={"created_by": actor, "updated_by": actor},
                    )
                    target = result["row"]
                    created["majors"] += 1
            resolved_majors[(_norm(candidate.get("collegeName")), _norm(candidate["name"]))] = target.id

        for decision in config["organizationDecisions"]:
            candidate = candidates[decision["candidateId"]]
            if candidate["entityType"] != "CLASS" or decision["action"] == "IGNORE": continue
            if decision["action"] == "MATCH":
                target = db.scalars(select(SchoolClass).where(SchoolClass.id == int(decision["targetId"]),
                    SchoolClass.tenant_id == tenant_id, SchoolClass.is_deleted.is_(False))).first()
                if not target: raise AppException("DATA_CONFLICT", "所选班级已不存在")
            else:
                parent_id = resolved_majors.get((_norm(candidate.get("collegeName")), _norm(candidate["parentName"])))
                if not parent_id:
                    parents = db.scalars(select(Major).where(Major.tenant_id == tenant_id,
                        Major.major_name == candidate["parentName"], Major.is_deleted.is_(False))).all()
                    if len(parents) != 1: raise AppException("DATA_CONFLICT", f"班级所属专业不唯一：{candidate['name']}")
                    parent_id = parents[0].id
                matches = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id,
                    SchoolClass.major_id == parent_id, SchoolClass.class_name == candidate["name"],
                    SchoolClass.is_deleted.is_(False))).all()
                if len(matches) > 1: raise AppException("DATA_CONFLICT", f"同专业班级重名：{candidate['name']}")
                if matches:
                    target = matches[0]
                else:
                    result = apply_org_node_in_session(
                        db, node_type="CLASS", name=candidate["name"], parent_id=parent_id,
                        code=_org_code("CLS", candidate["name"], candidate["parentName"]),
                        tenant_id=tenant_id, commit=False,
                        extras={
                            "grade": candidate.get("grade") or None,
                            "class_status": "NORMAL",
                            "created_by": actor, "updated_by": actor,
                        },
                    )
                    target = result["row"]
                    created["classes"] += 1

        config["status"] = "APPLIED"; config["appliedSummary"] = {"created": created, "roles": role_report}
        section_config["mapping"] = config
        section.config_json = section_config; section.status = "APPLIED"; section.version += 1; project.version += 1
        section.updated_by = project.updated_by = actor; db.commit()
    except Exception:
        db.rollback(); raise
    finally: db.close()

    role_updates = {x["loginName"]: x["roleCodes"] for x in config["roleDecisions"]}
    for teacher in entry["payload"].get("teachers") or []:
        if teacher.get("loginName") in role_updates: teacher["roleCodes"] = role_updates[teacher["loginName"]]
    report = preview_identity_import(user, entry["payload"], pre_errors=entry.get("preErrors") or [])
    refreshed = refresh_batch_report(user, tenant_id, entry["batchNo"], report)
    audit_log.record("IMPLEMENTATION_MAPPING_APPLIED", f"implementation-project:{project_id}",
                     {"batchNo": entry["batchNo"], "fileSha256": entry["fileSha256"],
                      "created": config["appliedSummary"]["created"], "remainingErrors": refreshed["invalid"],
                      "reason": reason})
    return {"idempotent": False, "batchNo": entry["batchNo"], "mapping": config["appliedSummary"],
            "refreshedPreview": refreshed}


def installations() -> list[dict]:
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        rows = db.scalars(select(SystemPresetInstallation).where(SystemPresetInstallation.tenant_id == tenant_id,
            SystemPresetInstallation.is_deleted.is_(False)).order_by(SystemPresetInstallation.id.desc())).all()
        return [{"id": str(x.id), "installationNo": x.installation_no, "profileCode": x.source_profile,
                 "sourceVersion": x.source_version, "status": x.status, "appliedAt": str(x.applied_at)[:19],
                 "snapshotHash": x.snapshot_hash} for x in rows]
    finally: db.close()


def create_change_project(user: dict, installation_id: int, body: dict) -> dict:
    """Create a new configurable project by inheriting an installed snapshot.

    A change is deliberately a new project/version.  The previous installation
    remains immutable and is only superseded when the new snapshot is applied.
    """
    tenant_id = _tid(); actor = _actor(user); db = get_sessionmaker()()
    try:
        installation = db.scalars(select(SystemPresetInstallation).where(
            SystemPresetInstallation.id == installation_id,
            SystemPresetInstallation.tenant_id == tenant_id,
            SystemPresetInstallation.is_deleted.is_(False))).first()
        if not installation:
            raise AppException("DATA_NOT_FOUND", "安装版本不存在")
        active = db.scalars(select(SystemImplementationProject).where(
            SystemImplementationProject.tenant_id == tenant_id,
            SystemImplementationProject.status.notin_(("ACCEPTED", "CANCELLED")),
            SystemImplementationProject.is_deleted.is_(False))).first()
        if active:
            raise AppException("DATA_CONFLICT", "本校已有进行中的实施项目")
        name = str(body.get("projectName") or f"{installation.source_profile} 变更项目").strip()
        if not 1 <= len(name) <= 100:
            raise AppException("VALIDATION_ERROR", "项目名称长度须为1—100字")
        now = datetime.utcnow()
        project = SystemImplementationProject(
            tenant_id=tenant_id, project_no=f"IMP-{now:%Y%m%d%H%M%S%f}",
            project_name=name, profile_code=installation.source_profile,
            status="CONFIGURING", owner_id=actor,
            change_source_installation_id=installation.id,
            target_date=None, created_by=actor, updated_by=actor)
        db.add(project); db.flush()
        inherited = (installation.snapshot_json or {}).get("snapshot", {})
        for code, _section_name, defaults in SECTION_DEFINITIONS:
            config = dict(defaults)
            config.update(PROFILE_OVERRIDES.get(project.profile_code, {}).get(code, {}))
            if code == "school_opening": config["profileCode"] = project.profile_code
            if isinstance(inherited.get(code), dict):
                config.update(inherited[code])
            db.add(SystemImplementationSection(
                tenant_id=tenant_id, project_id=project.id, section_code=code,
                config_json=config, source="INHERITED", status="CONFIGURED",
                created_by=actor, updated_by=actor))
        db.commit()
        audit_log.record("IMPLEMENTATION_CHANGE_PROJECT_CREATED",
                         f"implementation-project:{project.id}",
                         {"parentInstallationId": installation_id,
                          "sourceVersion": installation.source_version})
        return current_project()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def analyze_change(user: dict, project_id: int) -> dict:
    """Compare a change project with its immutable installed parent snapshot.

    The result is deliberately a count/hash based report: it never exposes
    student or teacher records, but gives the school a concrete release gate.
    """
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        source_id = project.change_source_installation_id
        if not source_id:
            raise AppException("DATA_CONFLICT", "当前项目不是从已安装版本发起的变更")
        source = db.scalars(select(SystemPresetInstallation).where(
            SystemPresetInstallation.id == source_id,
            SystemPresetInstallation.tenant_id == tenant_id,
            SystemPresetInstallation.is_deleted.is_(False))).first()
        if not source:
            raise AppException("DATA_NOT_FOUND", "变更来源安装版本不存在")
        before = (source.snapshot_json or {}).get("snapshot", {})
        after = {x.section_code: (x.config_json or {}) for x in _sections(db, project.id, tenant_id)}
        changed = [code for code in sorted(SECTION_CODES)
                   if _digest(before.get(code, {})) != _digest(after.get(code, {}))]
        def active_count(model) -> int:
            return int(db.scalar(select(func.count(model.id)).where(
                model.tenant_id == tenant_id, model.is_deleted.is_(False))) or 0)
        table_counts = {
            "roles": int(db.scalar(select(func.count(Role.id)).where(Role.tenant_id == tenant_id, Role.is_deleted.is_(False))) or 0),
            "organizations": int(sum(active_count(model) for model in (College, Major, SchoolClass))),
            "workflows": int(db.scalar(select(func.count(WorkflowDefinition.id)).where(WorkflowDefinition.tenant_id == tenant_id, WorkflowDefinition.is_deleted.is_(False))) or 0),
            "workbenches": int(db.scalar(select(func.count(RoleWorkbenchConfig.id)).where(RoleWorkbenchConfig.tenant_id == tenant_id, RoleWorkbenchConfig.is_deleted.is_(False))) or 0),
            "notifications": int(db.scalar(select(func.count(NotificationTemplate.id)).where(NotificationTemplate.tenant_id == tenant_id, NotificationTemplate.is_deleted.is_(False))) or 0),
        }
        high_risk = {"role_permission", "organization", "security_audit", "workflow", "business_relation"}
        analysis = {
            "sourceInstallationId": str(source.id),
            "sourceInstallationNo": source.installation_no,
            "sourceSnapshotHash": source.snapshot_hash,
            "changedSections": changed,
            "unchangedSections": sorted(SECTION_CODES - set(changed)),
            "riskLevel": "HIGH" if high_risk.intersection(changed) else ("MEDIUM" if changed else "NONE"),
            "requiresAcceptance": bool(changed),
            "affectedTableCounts": table_counts,
            "sensitiveDataIncluded": False,
        }
        existing = dict(project.preview_json or {})
        existing["changeAnalysis"] = analysis
        project.preview_json = existing; project.version += 1; project.updated_by = _actor(user)
        db.commit()
        audit_log.record("IMPLEMENTATION_CHANGE_ANALYZED", f"implementation-project:{project.id}", {
            "sourceInstallationNo": source.installation_no,
            "changedSections": changed,
            "riskLevel": analysis["riskLevel"],
            "affectedTableCounts": table_counts,
        })
        return {**analysis, "projectVersion": project.version}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def run_checks(user: dict, project_id: int) -> dict:
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if project.status not in {"APPLIED", "VERIFYING", "READY_FOR_ACCEPTANCE"}:
            raise AppException("DATA_CONFLICT", "请先应用预设快照")
        def count(model): return int(db.scalar(select(func.count(model.id)).where(
            model.tenant_id == tenant_id, model.is_deleted.is_(False))) or 0)
        sections = _sections(db, project.id, tenant_id)
        section_codes = {x.section_code for x in sections}
        configs = {x.section_code: (x.config_json or {}) for x in sections}
        opening = configs.get("school_opening", {})
        role_cfg = configs.get("role_permission", {})
        relation_cfg = configs.get("business_relation", {})
        numbering = configs.get("dictionary_numbering", {})
        security = configs.get("security_audit", {})
        modules = configs.get("module_business", {})
        pending_workflows = int(db.scalar(select(func.count(WorkflowDefinition.id)).where(
            WorkflowDefinition.tenant_id == tenant_id, WorkflowDefinition.installed_project_id == project.id,
            WorkflowDefinition.status == "PENDING_CONFIRMATION", WorkflowDefinition.is_deleted.is_(False))) or 0)
        relation_batches = int(db.scalar(select(func.count(SystemBusinessRelationBatch.id)).where(
            SystemBusinessRelationBatch.tenant_id == tenant_id,
            SystemBusinessRelationBatch.project_id == project.id,
            SystemBusinessRelationBatch.status == "APPLIED",
            SystemBusinessRelationBatch.is_deleted.is_(False))) or 0)
        relation_items = int(db.scalar(select(func.count(SystemBusinessRelationInstallItem.id)).where(
            SystemBusinessRelationInstallItem.tenant_id == tenant_id,
            SystemBusinessRelationInstallItem.project_id == project.id,
            SystemBusinessRelationInstallItem.status == "APPLIED",
            SystemBusinessRelationInstallItem.is_deleted.is_(False))) or 0)
        real = {
            "school_opening": (bool(opening.get("schoolLevel") and opening.get("deliveryMode") and opening.get("targetDays")),
                               {"schoolLevel": opening.get("schoolLevel"), "deliveryMode": opening.get("deliveryMode"), "targetDays": opening.get("targetDays")}),
            "role_permission": (count(Role) > 0 and isinstance(role_cfg.get("separationOfDuties"), bool),
                                 {"roles": count(Role), "separationOfDuties": role_cfg.get("separationOfDuties")}),
            "organization": (count(College) > 0 and count(Major) > 0 and count(SchoolClass) > 0,
                              {"colleges": count(College), "majors": count(Major), "classes": count(SchoolClass)}),
            "identity_import": (count(User) > 0 and count(StudentProfile) > 0,
                                 {"accounts": count(User), "students": count(StudentProfile)}),
            "business_relation": (not relation_cfg.get("requireRealRelation") or relation_batches > 0,
                                   {"appliedBatches": relation_batches, "appliedItems": relation_items,
                                    "requireRealRelation": relation_cfg.get("requireRealRelation")}),
            "workflow": (count(WorkflowDefinition) > 0 and pending_workflows == 0,
                         {"installed": count(WorkflowDefinition), "pendingPolicyConfirmation": pending_workflows}),
            "dictionary_numbering": (bool(numbering.get("useNationalCodes")) and bool(numbering.get("numberingOwner")),
                                      {"useNationalCodes": numbering.get("useNationalCodes"), "numberingOwner": numbering.get("numberingOwner")}),
            "security_audit": (all(security.get(k) is not None for k in ("firstLoginChangePassword", "exportWatermark", "sessionMinutes")),
                               {"firstLoginChangePassword": security.get("firstLoginChangePassword"), "exportWatermark": security.get("exportWatermark"), "sessionMinutes": security.get("sessionMinutes")}),
            "menu_workbench": (count(RoleWorkbenchConfig) > 0, {"roleWorkbenches": count(RoleWorkbenchConfig)}),
            "message_notification": (count(NotificationTemplate) > 0, {"templates": count(NotificationTemplate)}),
            "module_business": (bool(modules.get("modules")) and modules.get("includeProfessionalStandards") is True,
                                {"modules": modules.get("modules") or [], "includeProfessionalStandards": modules.get("includeProfessionalStandards")}),
        }
        checks = []; actor = _actor(user)
        manual_codes = {"school_opening", "dictionary_numbering", "security_audit", "module_business"}
        for code, name, _defaults in SECTION_DEFINITIONS:
            if code == "go_live_check":
                passed = bool(checks) and all(item["result"] == "PASS" for item in checks)
                evidence = {"precedingChecks": len(checks), "precedingFailures": sum(item["result"] != "PASS" for item in checks)}
            else:
                passed, evidence = real.get(code, (code in section_codes, {"configured": code in section_codes}))
            severity = "WARNING" if code in manual_codes else "BLOCKER"
            check = db.scalars(select(SystemImplementationCheck).where(SystemImplementationCheck.tenant_id == tenant_id,
                SystemImplementationCheck.project_id == project.id, SystemImplementationCheck.check_code == code,
                SystemImplementationCheck.is_deleted.is_(False))).first()
            effective_passed = passed or (severity != "BLOCKER" and check is not None and check.confirmed_by is not None)
            if not check:
                check = SystemImplementationCheck(tenant_id=tenant_id, project_id=project.id, check_code=code,
                    category_code=code, check_name=name, result="PASS" if effective_passed else "FAIL", severity=severity,
                    evidence_json=evidence, owner_role="SCHOOL_ADMIN", created_by=actor, updated_by=actor); db.add(check)
            else: check.result = "PASS" if effective_passed else "FAIL"; check.severity = severity; check.evidence_json = evidence; check.version += 1
            checks.append({"code": code, "name": name, "result": "PASS" if effective_passed else "FAIL",
                           "severity": severity, "ownerRole": "SCHOOL_ADMIN", "confirmedBy": check.confirmed_by,
                           "evidence": evidence})
        ready = all(x["result"] == "PASS" for x in checks); project.status = "READY_FOR_ACCEPTANCE" if ready else "VERIFYING"
        project.version += 1; db.commit(); audit_log.record("IMPLEMENTATION_READINESS_CHECK_RUN",
            f"implementation-project:{project.id}", {"passed": sum(x["result"] == "PASS" for x in checks), "total": len(checks)})
        return {"ready": ready, "checks": checks, "projectStatus": project.status}
    except Exception:
        db.rollback(); raise
    finally: db.close()


def accept_project(user: dict, project_id: int, body: dict) -> dict:
    if str(body.get("confirmText") or "").strip() != "确认验收": raise AppException("VALIDATION_ERROR", "请输入“确认验收”")
    comment = str(body.get("comment") or "").strip()
    if len(comment) < 2: raise AppException("VALIDATION_ERROR", "请填写验收意见")
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if project.status != "READY_FOR_ACCEPTANCE": raise AppException("DATA_CONFLICT", "仍有阻断项")
        accepted_at = datetime.utcnow(); accepted_by = _actor(user)
        sections = _sections(db, project.id, tenant_id)
        checks = db.scalars(select(SystemImplementationCheck).where(
            SystemImplementationCheck.tenant_id == tenant_id,
            SystemImplementationCheck.project_id == project.id,
            SystemImplementationCheck.is_deleted.is_(False)).order_by(SystemImplementationCheck.check_code)).all()
        summary = {
            "projectId": str(project.id), "projectNo": project.project_no,
            "profileCode": project.profile_code, "projectVersion": project.version,
            "acceptedAt": accepted_at.isoformat(), "acceptedBy": accepted_by,
            "comment": comment, "previewHash": project.preview_hash,
            "sections": [{"code": x.section_code, "version": x.version, "configHash": _digest(x.config_json or {})} for x in sections],
            "checks": [{"code": x.check_code, "result": x.result, "severity": x.severity,
                        "ownerRole": x.owner_role, "confirmedBy": x.confirmed_by,
                        "confirmedAt": str(x.confirmed_at or ""), "comment": x.comment,
                        "evidence": x.evidence_json} for x in checks],
        }
        digest = _digest(summary)
        project.status = "ACCEPTED"; project.accepted_at = accepted_at; project.accepted_by = accepted_by
        project.acceptance_comment = comment; project.acceptance_summary = summary; project.acceptance_digest = digest
        project.version += 1; db.commit()
        audit_log.record("IMPLEMENTATION_ACCEPTED", f"implementation-project:{project.id}", {"comment": comment})
        audit_log.record("IMPLEMENTATION_ACCEPTANCE_SUMMARY_FROZEN", f"implementation-project:{project.id}",
                         {"digest": digest, "checkCount": len(checks), "sectionCount": len(sections)})
        return current_project()
    except Exception:
        db.rollback(); raise
    finally: db.close()


def confirm_check(user: dict, project_id: int, check_code: str, body: dict) -> dict:
    """Record a responsible-person confirmation for a WARNING check."""
    if str(body.get("confirmText") or "").strip() != "确认责任":
        raise AppException("VALIDATION_ERROR", "请输入“确认责任”")
    comment = str(body.get("comment") or "").strip()
    if len(comment) < 2:
        raise AppException("VALIDATION_ERROR", "请填写责任确认说明")
    tenant_id = _tid(); db = get_sessionmaker()()
    try:
        project = _project(db, project_id, tenant_id)
        if project.status == "ACCEPTED":
            raise AppException("DATA_CONFLICT", "验收摘要已封板，不能修改责任确认")
        if body.get("projectVersion") is not None and int(body["projectVersion"]) != project.version:
            raise AppException("DATA_CONFLICT", "项目版本已变化，请刷新后再确认")
        check = db.scalars(select(SystemImplementationCheck).where(
            SystemImplementationCheck.tenant_id == tenant_id,
            SystemImplementationCheck.project_id == project_id,
            SystemImplementationCheck.check_code == check_code,
            SystemImplementationCheck.is_deleted.is_(False))).first()
        if not check:
            raise AppException("DATA_NOT_FOUND", "上线检查项不存在")
        if check.severity == "BLOCKER":
            raise AppException("DATA_CONFLICT", "阻断项不能通过人工确认绕过")
        actor = _actor(user); check.confirmed_by = actor; check.confirmed_at = datetime.utcnow()
        check.comment = comment; check.result = "PASS"; check.version += 1
        evidence = dict(check.evidence_json or {}); evidence["manualConfirmation"] = {
            "confirmedBy": actor, "confirmedAt": str(check.confirmed_at), "comment": comment}
        check.evidence_json = evidence; project.version += 1; project.updated_by = actor
        db.commit()
        audit_log.record("IMPLEMENTATION_CHECK_CONFIRMED", f"implementation-check:{check.id}",
                         {"projectId": project_id, "checkCode": check_code, "comment": comment})
        return {"code": check.check_code, "result": check.result, "severity": check.severity,
                "ownerRole": check.owner_role, "confirmedBy": check.confirmed_by,
                "confirmedAt": str(check.confirmed_at), "comment": check.comment,
                "projectVersion": project.version}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
