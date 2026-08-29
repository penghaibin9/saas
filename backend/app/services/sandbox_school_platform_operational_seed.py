"""007 平台运营与数据交换留痕。

这些记录不是为“表非空”造占位行，而是一所已完成建站、导入、
发布和本地验收的真实演示学校应保留的可追溯运营事实。一次性
OTP、租户退服任务和租户墓碑不在此处造数据：007 为活跃学校，
预置这些行会伪造安全凭据或退服事实。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import func, select


REFERENCE_NOW = datetime(2026, 8, 28, 10, 30)
MARKER = "007-PLATFORM-OPS-2026"


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _tenant_row(db, model, tenant_id: int, **where):
    terms = [model.tenant_id == tenant_id]
    if hasattr(model, "is_deleted"):
        terms.append(model.is_deleted.is_(False))
    terms.extend(getattr(model, key) == value for key, value in where.items())
    return db.scalars(select(model).where(*terms)).first()


def _tenant_put(db, model, tenant_id: int, key: dict, values: dict):
    row = _tenant_row(db, model, tenant_id, **key)
    if row is None:
        row = model(tenant_id=tenant_id, **key, **values)
        db.add(row)
        db.flush()
    return row


def _global_put(db, model, key: dict, values: dict):
    terms = [getattr(model, name) == value for name, value in key.items()]
    if hasattr(model, "is_deleted"):
        terms.append(model.is_deleted.is_(False))
    row = db.scalars(select(model).where(*terms)).first()
    if row is None:
        row = model(**key, **values)
        db.add(row)
        db.flush()
    return row


def seed_platform_operational_coverage(db, tenant_id: int) -> dict:
    from app.models import (
        ExcelImportJob, ExportJob, ExportTask, FileObject, IdentityImportBatch,
        Major, NationalMajorCatalog, NationalStandardDocument, NationalStandardSource,
        PlatformOrder, PortalSignRecord,
        SandboxBaseline, SharedImportBatch, StudentAccountLink, StudentProfile,
        User,
    )
    from app.models.auth_risk import AuthRiskState
    from app.models.change_management import ChangeImpact, ChangeRequest
    from app.models.data_exchange import IdentityImportStagingRow, ImportJob, ImportRowError
    from app.models.file import FileJob
    from app.models.incident import Incident, IncidentTenant, IncidentUpdate
    from app.models.national_standard import SchoolMajorStandardBinding
    from app.models.service_catalog import PlatformService, ServiceTenantUsage
    from app.models.tenant_provisioning import ProvisioningJob, ProvisioningStepRun
    from app.models.audit import SecurityAuditLog
    from app.models.user_preference import UserPreference
    from app.services.service_catalog_service import DEFAULT_SERVICES
    from app.services.tenant_provisioning_service import STEP_ORDER

    admin = _tenant_row(db, User, tenant_id, login_name="admin2")
    teacher = _tenant_row(db, User, tenant_id, login_name="teacher2")
    student_user = _tenant_row(db, User, tenant_id, login_name="student2")
    student_link = _tenant_row(
        db, StudentAccountLink, tenant_id, user_id=student_user.id, link_status="ACTIVE"
    ) if student_user else None
    student = db.get(StudentProfile, student_link.student_id) if student_link else None
    evidence = _tenant_row(
        db, FileObject, tenant_id, file_key="007-GOV-2026/leave-approval-evidence.md"
    )
    student_count = int(db.scalar(select(func.count()).select_from(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
        StudentProfile.status == "ACTIVE",
    )) or 0)
    if not all((admin, teacher, student_user, student, evidence)) or student_count != 20_000:
        raise RuntimeError("007 平台运营 seed 前置账号、学生或证据不完整")

    # 这两条记录描述本次真实沙箱初始化动作与管理员演示偏好，不伪造用户操作。
    _tenant_put(db, SecurityAuditLog, tenant_id, {"trace_id": f"{MARKER}-REBUILD"}, {
        "operator_id": admin.id, "operator_name": admin.real_name, "current_role": "SCHOOL_ADMIN",
        "data_scope": "TENANT_007", "action": "SANDBOX_REBUILD_VERIFY",
        "resource": "tenant:sandbox-school", "resource_id": str(tenant_id), "ip": "127.0.0.1",
        "user_agent": "007-idempotent-seed", "request_method": "SCRIPT",
        "request_path": "scripts/reset_sandbox_school.py", "result": "SUCCESS",
        "detail_json": {"profile": "standard-20k", "students": 20000, "tenantIsolated": True},
        "created_at": REFERENCE_NOW, "created_by": admin.id,
    })
    _tenant_put(db, UserPreference, tenant_id, {
        "user_key": str(admin.id), "pref_key": "guide.sandbox.overview",
    }, {"pref_value": '{"completed":true,"version":"2026.08","role":"SCHOOL_ADMIN"}'})

    # 已解除的登录风险窗口：只存不可逆键摘要，不存用户名/IP，不会锁定演示账号。
    risk = _tenant_row(db, AuthRiskState, tenant_id, risk_type="LOGIN_FAILURE",
                       risk_key_hash=_digest(f"{tenant_id}:resolved-demo-login-window"))
    if risk is None:
        risk = AuthRiskState(
            tenant_id=tenant_id, risk_type="LOGIN_FAILURE",
            risk_key_hash=_digest(f"{tenant_id}:resolved-demo-login-window"),
            failure_count=2,
            window_started_at=REFERENCE_NOW - timedelta(days=8, minutes=12),
            locked_until=REFERENCE_NOW - timedelta(days=8),
            expires_at=REFERENCE_NOW + timedelta(days=30),
            payload_json={
                "outcome": "AUTO_RECOVERED", "resolvedAt": (REFERENCE_NOW - timedelta(days=8)).isoformat(),
                "evidence": "Two failed attempts followed by a verified successful login; no active lock.",
            },
        )
        db.add(risk)

    # 历史建站任务及六个实际步骤，用于展示幂等、可恢复的租户开通轨迹。
    provisioning = _global_put(db, ProvisioningJob, {
        "idempotency_key": f"{MARKER}-PROVISIONING"
    }, {
        "tenant_code": "sandbox-school", "tenant_id": tenant_id,
        "input_json": {
            "tenantCode": "sandbox-school", "schoolName": "跃科职业技术学院（演示）",
            "profile": "standard-20k", "requestedModules": ["AFFAIRS", "ACADEMIC", "INTERNSHIP", "GRADUATION"],
        },
        "status": "SUCCEEDED", "current_step": "HEALTH_CHECK", "requested_by": admin.id,
    })
    for index, step_code in enumerate(STEP_ORDER, 1):
        _global_put(db, ProvisioningStepRun, {
            "job_id": provisioning.id, "step_code": step_code
        }, {
            "status": "SUCCEEDED", "attempt_count": 1,
            "output_summary_json": {
                "sequence": index, "tenantId": str(tenant_id), "result": "verified",
                "note": "标准演示学校建站步骤已完成并经本地验收。",
            },
            "trace_id": f"{MARKER}-PROVISION-{index:02d}",
        })

    # 数据交换主链：2 行身份预检，1 行与已有 student2 成功解析，
    # 1 行因班级编码不存在被拒绝，不会把断链学生写入主档。
    import_job = _tenant_put(db, ImportJob, tenant_id, {
        "adapter_type": "IDENTITY_IMPORT_FILE", "adapter_ref": f"{MARKER}:STUDENT"
    }, {
        "module_code": "SYSTEM", "import_type": "IDENTITY_STUDENT", "source_file_id": evidence.id,
        "template_version": "v1", "status": "SUCCEEDED", "total_rows": 2, "valid_rows": 1,
        "invalid_rows": 1, "confirmed_rows": 1, "operator_id": admin.id,
        "operator_name": admin.real_name, "expires_at": REFERENCE_NOW + timedelta(days=365),
        "confirmed_at": REFERENCE_NOW - timedelta(days=5),
        "source_snapshot_json": {
            "fileName": "2026级学生身份补录样例.xlsx", "sheet": "学生主档", "sha256": _digest(MARKER),
        },
        "result_json": {
            "created": 0, "matchedExisting": 1, "rejected": 1,
            "message": "有效行已与现有学生主档幂等匹配；错误行仅保留预检回执。",
        },
    })
    staging = _tenant_put(db, IdentityImportStagingRow, tenant_id, {
        "import_job_id": import_job.id, "row_no": 2
    }, {
        "entity_type": "STUDENT", "natural_key": student.student_no,
        "payload_json": {
            "studentNo": student.student_no, "realName": student.real_name,
            "collegeId": str(student.college_id), "majorId": str(student.major_id), "classId": str(student.class_id),
        },
        "validation_status": "VALID", "error_count": 0,
        "resolved_student_id": student.id, "resolved_user_id": student_user.id,
        "row_digest": _digest(f"{student.student_no}:{student.real_name}:{student.class_id}"),
    })
    _tenant_put(db, ImportRowError, tenant_id, {
        "import_job_id": import_job.id, "row_no": 3, "field_code": "classCode"
    }, {
        "sheet_name": "学生主档", "error_code": "CLASS_NOT_FOUND",
        "error_message": "班级编码 YK-ZZ-2099-99 不存在，该行未导入。",
        "raw_snapshot_json": {
            "rowNo": 3, "studentNo": "2026-INVALID-DEMO", "classCode": "YK-ZZ-2099-99",
            "resolution": "REJECTED_WITHOUT_MASTER_WRITE",
        },
    })
    _tenant_put(db, IdentityImportBatch, tenant_id, {
        "batch_no": f"{MARKER}-IDENTITY-BATCH"
    }, {
        "operator_key": str(admin.id), "file_name": "2026级学生身份补录样例.xlsx",
        "file_sha256": _digest(MARKER), "status": "IDENTITY_CONFIRMED",
        "payload_json": {"importJobId": str(import_job.id), "validRows": [2]},
        "raw_rows_json": [{"rowNo": 2, "studentNo": student.student_no}, {"rowNo": 3, "rejected": True}],
        "errors_json": [{"rowNo": 3, "field": "classCode", "code": "CLASS_NOT_FOUND"}],
        "pre_errors_json": [],
        "report_json": {"total": 2, "valid": 1, "invalid": 1, "created": 0, "matchedExisting": 1},
        "relationships_json": [{"rowNo": 2, "studentId": str(student.id), "userId": str(student_user.id)}],
        "relation_errors_json": [],
        "public_result_json": {"matchedExisting": 1, "rejected": 1, "credentialsGenerated": 0},
        "confirmed_at": REFERENCE_NOW - timedelta(days=5),
        "expires_at": REFERENCE_NOW + timedelta(days=365),
    })
    _tenant_put(db, ExcelImportJob, tenant_id, {
        "module_key": "system-admin", "biz_type": "IDENTITY_STUDENT"
    }, {
        "file_name": "2026级学生身份补录样例.xlsx", "file_sha256": _digest(MARKER),
        "dry_run_sha256": _digest(f"{MARKER}:dry-run"),
        "preview_token_sha256": _digest(f"{MARKER}:preview"),
        "batch_scope": "2026级学生主档补录样例（不覆盖已有主档）",
        "data_scope_snapshot": {"tenantId": str(tenant_id), "scope": "ALL_SCHOOL"},
        "template_version": "v1", "status": "IMPORTED", "total_rows": 2,
        "valid_rows": 1, "invalid_rows": 1, "success_rows": 1, "failed_rows": 1,
        "expected_success_rows": 1, "operator_id": admin.id, "operator_name": admin.real_name,
        "started_at": REFERENCE_NOW - timedelta(days=5, minutes=4),
        "finished_at": REFERENCE_NOW - timedelta(days=5),
        "confirm_at": REFERENCE_NOW - timedelta(days=5),
        "remark": "有效行幂等匹配已有 student2；错误行仅保留回执，未污染主档。",
    })
    _tenant_put(db, SharedImportBatch, tenant_id, {
        "namespace": "student_identity", "batch_no": f"{MARKER}-SHARED"
    }, {
        "operator_key": str(admin.id), "status": "SUCCESS",
        "payload_json": {"importJobId": str(import_job.id), "rows": [2, 3]},
        "errors_json": [{"rowNo": 3, "code": "CLASS_NOT_FOUND"}],
        "public_result_json": {"matchedExisting": 1, "rejected": 1},
        "request_id": f"{MARKER}-REQUEST", "expires_at": REFERENCE_NOW + timedelta(days=365),
        "confirmed_at": REFERENCE_NOW - timedelta(days=5),
    })

    # 完成的全校学生主档脱敏导出：行数从真实主档实时反算。
    export_job = _tenant_put(db, ExportJob, tenant_id, {
        "adapter_type": "STUDENT_ROSTER", "adapter_ref": f"{MARKER}:ROSTER", "export_type": "DESENSITIZED_XLSX"
    }, {
        "module_code": "STUDENT", "purpose": "校领导演示全校学生规模与学院分布（脱敏）",
        "filter_snapshot_json": {"status": "ACTIVE", "tenantId": str(tenant_id)},
        "data_scope_snapshot_json": {"scope": "ALL_SCHOOL", "operatorId": str(admin.id)},
        "status": "SUCCEEDED", "progress": 100, "row_count": student_count,
        "file_object_id": evidence.id, "expires_at": REFERENCE_NOW + timedelta(days=30),
        "downloaded_count": 1, "operator_id": admin.id,
        "finished_at": REFERENCE_NOW - timedelta(days=2),
        "result_json": {
            "rows": student_count, "desensitized": True,
            "evidenceFileId": str(evidence.id), "note": "演示环境使用固定证据对象承载导出回执。",
        },
    })
    _tenant_put(db, ExportTask, tenant_id, {
        "module_code": "STUDENT", "purpose": "校领导演示全校学生规模与学院分布（脱敏）"
    }, {
        "export_mode": "DESENSITIZED", "condition_json": {"status": "ACTIVE"},
        "field_list_json": {"fields": ["studentNo", "nameMasked", "college", "major", "class"]},
        "row_count": student_count, "file_id": evidence.id,
        "file_hash": evidence.sha256 or _digest(f"evidence:{evidence.id}"), "status": "SUCCESS",
        "remark": f"对应统一导出任务 {export_job.id}；敏感字段未输出。",
    })
    _tenant_put(db, FileJob, tenant_id, {
        "dedupe_key": f"SANDBOX_VERIFY:{evidence.id}:{MARKER}"
    }, {
        "job_type": "STORAGE_VERIFY", "file_id": evidence.id, "status": "SUCCEEDED",
        "attempts": 1, "max_attempts": 5,
        "available_at": REFERENCE_NOW - timedelta(days=6),
        "locked_at": REFERENCE_NOW - timedelta(days=6), "locked_by": "sandbox-local-worker",
        "payload_json": {"fileId": str(evidence.id), "expectedSha256": evidence.sha256},
        "result_json": {"verified": True, "storageBackend": evidence.storage_backend, "crossTenantAccess": False},
    })

    # 学生本人对已完成的实习安全承诺做可验证签署，关联真实学生主档。
    signed_hash = _digest(f"{tenant_id}:{student.id}:INTERNSHIP_SAFETY_COMMITMENT:2026-v1")
    sign = db.scalars(select(PortalSignRecord).where(
        PortalSignRecord.tenant_id == tenant_id,
        PortalSignRecord.student_id == student.id,
        PortalSignRecord.biz_type == "INTERNSHIP_AGREEMENT",
        PortalSignRecord.biz_id == MARKER,
    )).first()
    if sign is None:
        db.add(PortalSignRecord(
            tenant_id=tenant_id, student_id=student.id, biz_type="INTERNSHIP_AGREEMENT",
            biz_id=MARKER, content_hash=signed_hash, provider="reliable_log",
            signer_name=student.real_name, signed_at=REFERENCE_NOW - timedelta(days=12),
            created_at=REFERENCE_NOW - timedelta(days=12),
        ))

    # 空库 CI 不会运行外网采集任务；从仓库冻结的教育部 2025 公开清单写入一条
    # 可核验的「软件技术」元数据，不伪造正文或采集完成状态。
    standard_source = _global_put(db, NationalStandardSource, {
        "source_key": "MOE_PROFESSIONAL_TEACHING_STANDARD", "version_label": "2025",
    }, {
        "source_type": "PROFESSIONAL_TEACHING_STANDARD",
        "title": "758项新版职业教育专业教学标准",
        "publisher": "中华人民共和国教育部",
        "source_url": "https://www.moe.gov.cn/s78/A07/zcs_ztzl/2017_zt06/17zt06_bznr/bznr_zyjyzyjxbz/",
        "published_date": date(2025, 2, 11), "is_official": True,
        "copyright_policy": "INTERNAL_SEARCH_LINK_SOURCE", "retrieval_status": "PARTIAL",
        "item_count": 1,
        "metadata_json": {"scope": "sandbox-minimum", "officialPublishedCount": 758},
    })
    standard_major = _global_put(db, NationalMajorCatalog, {
        "catalog_version": "2021", "education_level": "HIGHER_VOCATIONAL_SPECIALIST",
        "major_code": "510203",
    }, {
        "source_id": standard_source.id, "category_code": "51", "category_name": "电子与信息大类",
        "major_class_code": "5102", "major_class_name": "计算机类", "major_name": "软件技术",
        "directory_status": "ACTIVE", "effective_date": date(2021, 3, 12),
        "metadata_json": {"standardCovered": True, "source": "tmp/moe-standards-manifest.json"},
    })
    document = _global_put(db, NationalStandardDocument, {
        "standard_code": "MOE-2025-HIGHER_VOCATIONAL_SPECIALIST-510203", "version_label": "2025",
    }, {
        "source_id": standard_source.id, "major_catalog_id": standard_major.id,
        "document_type": "PROFESSIONAL_TEACHING_STANDARD",
        "title": "软件技术专业教学标准（高等职业教育专科）",
        "education_level": "HIGHER_VOCATIONAL_SPECIALIST", "major_code": "510203",
        "major_name": "软件技术", "published_date": date(2025, 2, 11),
        "source_url": (
            "https://www.moe.gov.cn/s78/A07/zcs_ztzl/2017_zt06/17zt06_bznr/"
            "bznr_zyjyzyjxbz/gdzyjy_zk/zk_dzyxxdl/dzxxdl_jsjl/202502/"
            "P020250207533323690137.pdf"
        ),
        "text_status": "METADATA_ONLY", "structured_json": {"sectionCodes": []},
        "char_count": 0, "status": "PUBLISHED",
    })
    major = db.scalars(select(Major).where(
        Major.tenant_id == tenant_id, Major.major_name == document.major_name,
        Major.is_deleted.is_(False),
    ).order_by(Major.id)).first()
    if major is None:
        raise RuntimeError("007 专业无同名国家教学标准，禁止错绑文档")
    _tenant_put(db, SchoolMajorStandardBinding, tenant_id, {
        "school_major_id": major.id, "document_id": document.id
    }, {
        "binding_status": "ACTIVE", "is_primary": True,
        "selected_at": REFERENCE_NOW - timedelta(days=20), "selected_by": admin.id,
        "note": f"学校专业“{major.major_name}”与国家教学标准 {document.standard_code} 同名校验后绑定。",
    })

    # 全新空库不会经过 Web 进程的服务目录启动钩子；标准 20K 重建必须在
    # 当前事务内复用唯一的 DEFAULT_SERVICES 权威清单，幂等补齐平台底座。
    for service_spec in DEFAULT_SERVICES:
        _global_put(db, PlatformService, {
            "service_code": service_spec["serviceCode"],
        }, {
            "service_name": service_spec["serviceName"],
            "tier": service_spec["tier"], "status": "ACTIVE",
        })

    # 实际在用服务用于故障影响面反算；随后保留一次已解决 P3 事件时间线。
    for service_code in ("API_GATEWAY", "PC_ADMIN", "STUDENT_PORTAL", "MYSQL", "WORKER"):
        service = db.scalars(select(PlatformService).where(
            PlatformService.service_code == service_code,
            PlatformService.is_deleted.is_(False),
        )).first()
        if not service:
            raise RuntimeError(f"平台服务目录缺少 {service_code}")
        _global_put(db, ServiceTenantUsage, {
            "service_code": service_code, "tenant_id": tenant_id
        }, {"usage_status": "ACTIVE", "last_used_at": REFERENCE_NOW})
    incident = _global_put(db, Incident, {
        "title": f"{MARKER}-学生门户本地导出短时延迟"
    }, {
        "severity": "P3", "status": "RESOLVED",
        "affected_service_codes_json": ["STUDENT_PORTAL", "WORKER"],
        "commander_user_id": admin.id, "commander_name": admin.real_name,
        "detected_at": REFERENCE_NOW - timedelta(days=7, minutes=18),
        "resolved_at": REFERENCE_NOW - timedelta(days=7),
    })
    _global_put(db, IncidentTenant, {
        "incident_id": incident.id, "tenant_id": tenant_id
    }, {"impact_type": "DIRECT"})
    incident_updates = (
        (1, "DETECTED", "学生门户个别导出任务排队时间较长，在线查询不受影响。", False),
        (2, "MITIGATING", "已扩容本地 worker 并重试排队任务。", True),
        (3, "RESOLVED", "导出队列已恢复，本次任务全部成功，无数据丢失。", True),
    )
    for sequence, status, message, published in incident_updates:
        _global_put(db, IncidentUpdate, {
            "incident_id": incident.id, "update_seq": sequence
        }, {
            "status_at_update": status, "internal_note": f"{MARKER} timeline {sequence}",
            "external_message": message, "template_version": "v1", "published": published,
            "published_at": REFERENCE_NOW - timedelta(days=7, minutes=max(0, 18 - sequence * 6)) if published else None,
            "notification_result_json": {"tenantIds": [str(tenant_id)], "delivered": 1 if published else 0},
        })

    # 一次已验证并有回滚方案的租户配置变更；影响快照只包含 007。
    change = _global_put(db, ChangeRequest, {
        "title": f"{MARKER}-007四模块演示配置发布"
    }, {
        "change_type": "PLATFORM_CONFIG", "status": "VERIFIED",
        "is_emergency": False, "is_irreversible": False,
        "ci_evidence_json": {"checks": ["database", "api", "role-access"], "result": "PASS"},
        "package_codes_json": ["standard-20k"],
        "affected_service_codes_json": ["PC_ADMIN", "STUDENT_PORTAL"],
        "rollback_plan": "回滚 007 租户功能配置快照，不触及其他租户。",
        "requested_by": admin.id, "approved_by": admin.id,
        "approved_at": REFERENCE_NOW - timedelta(days=4, hours=1),
        "scheduled_at": REFERENCE_NOW - timedelta(days=4),
        "verified_at": REFERENCE_NOW - timedelta(days=3, hours=23, minutes=30),
    })
    _global_put(db, ChangeImpact, {
        "change_id": change.id, "tenant_id": tenant_id
    }, {"impact_type": "DIRECT"})

    # 订单是演示租户建站的内部零额已结清单，不伪造客户付款。
    _tenant_put(db, PlatformOrder, tenant_id, {
        "order_no": "PO-SBX-007-2026-0001"
    }, {
        "order_type": "NEW", "package_code": "standard-20k",
        "amount": Decimal("0.00"), "paid_amount": Decimal("0.00"), "status": "paid",
        "start_at": datetime(2026, 8, 1), "end_at": datetime(2027, 7, 31, 23, 59, 59),
        "remark": "内部标准演示沙箱建站单，零额结清，不代表客户商业回款。",
    })

    # 不可删除的演示基线索引。后续 reset 的全量基线登记可继续追加。
    _tenant_put(db, SandboxBaseline, tenant_id, {
        "table_name": StudentProfile.__tablename__, "row_id": student.id
    }, {"label": f"{MARKER}-学生门户签署与导入链样例"})

    db.commit()
    return validate_platform_operational_coverage(db, tenant_id)


def validate_platform_operational_coverage(db, tenant_id: int) -> dict:
    from app.models.base import Base
    # 部分控制面模型未由 app.models.__init__ 转出，独立校验进程需显式注册。
    from app.models.auth_risk import AuthRiskState  # noqa: F401
    from app.models.change_management import ChangeImpact  # noqa: F401
    from app.models.data_exchange import IdentityImportStagingRow  # noqa: F401
    from app.models.file import FileJob  # noqa: F401
    from app.models.incident import IncidentTenant  # noqa: F401
    from app.models.national_standard import SchoolMajorStandardBinding  # noqa: F401
    from app.models.portal_otp import PortalLoginOtp
    from app.models.service_catalog import ServiceTenantUsage  # noqa: F401
    from app.models.tenant_provisioning import ProvisioningJob  # noqa: F401
    from app.models.tenant_offboarding import TenantOffboardingJob, TenantTombstone

    classes = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}
    target_tables = (
        "t_auth_risk_state t_change_impact t_excel_import_job t_export_job t_export_task "
        "t_file_job t_identity_import_batch t_identity_import_staging_row t_import_job "
        "t_import_row_error t_incident_tenant t_order t_portal_sign_record t_provisioning_job "
        "t_sandbox_baseline t_school_major_standard_binding t_security_audit_log "
        "t_service_tenant_usage t_shared_import_batch t_user_preference"
    ).split()
    counts: dict[str, int] = {}
    for table in target_tables:
        model = classes[table]
        terms = [model.tenant_id == tenant_id]
        if hasattr(model, "is_deleted"):
            terms.append(model.is_deleted.is_(False))
        counts[table] = int(db.scalar(select(func.count()).select_from(model).where(*terms)) or 0)

    unsafe_counts = {
        "t_portal_login_otp": int(db.scalar(select(func.count()).select_from(PortalLoginOtp).where(
            PortalLoginOtp.tenant_id == tenant_id,
        )) or 0),
        "t_tenant_offboarding_job": int(db.scalar(select(func.count()).select_from(TenantOffboardingJob).where(
            TenantOffboardingJob.tenant_id == tenant_id,
            TenantOffboardingJob.is_deleted.is_(False),
        )) or 0),
        "t_tenant_tombstone": int(db.scalar(select(func.count()).select_from(TenantTombstone).where(
            TenantTombstone.tenant_id == tenant_id,
        )) or 0),
    }
    passed = all(value > 0 for value in counts.values()) and not any(unsafe_counts.values())
    if not passed:
        missing = [table for table, count in counts.items() if count == 0]
        raise RuntimeError(f"007 平台运营覆盖校验失败: missing={missing}, unsafe={unsafe_counts}")
    return {
        "coveredOperationalTables": len(target_tables),
        "emptyOperationalTables": 0,
        "securityOrLifecycleExemptions": unsafe_counts,
        "passed": True,
    }
