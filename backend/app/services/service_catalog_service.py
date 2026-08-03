"""PLAT-08 服务目录、依赖与租户影响地图。

平台级数据，不经过 _tid()；写权限完全由 platform.py 路由层的
require_platform_super_admin 把关，本文件内部不再重复做租户/角色判断。

依赖图存 t_service_dependency(service_code -> depends_on_service_code)，
一条边表示"service_code 需要 depends_on_service_code 才能正常工作"。
加边前必须证明加入后图仍无环（PLAT08-T01），故障影响面沿着"谁依赖我"
的反向边做可达性遍历（PLAT08-T02）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.service_catalog import PlatformService, ServiceDependency, ServiceTenantUsage

# 首版覆盖：API、PC、门户、小程序、MySQL、Redis、Worker、COS、ClamAV、短信
DEFAULT_SERVICES: list[dict] = [
    {"serviceCode": "API_GATEWAY", "serviceName": "后端 API", "tier": "P0"},
    {"serviceCode": "PC_ADMIN", "serviceName": "PC 管理端", "tier": "P1"},
    {"serviceCode": "STUDENT_PORTAL", "serviceName": "学生门户", "tier": "P1"},
    {"serviceCode": "MINIAPP", "serviceName": "小程序", "tier": "P1"},
    {"serviceCode": "MYSQL", "serviceName": "MySQL 数据库", "tier": "P0"},
    {"serviceCode": "REDIS", "serviceName": "Redis 缓存", "tier": "P0"},
    {"serviceCode": "WORKER", "serviceName": "后台 Worker", "tier": "P1"},
    {"serviceCode": "COS", "serviceName": "对象存储 COS", "tier": "P1"},
    {"serviceCode": "CLAMAV", "serviceName": "ClamAV 病毒扫描", "tier": "P2"},
    {"serviceCode": "SMS_GATEWAY", "serviceName": "短信网关", "tier": "P2"},
]


def _session():
    return get_sessionmaker()()


def bootstrap_default_services() -> int:
    """幂等登记首版默认服务；已存在的 service_code 不覆盖，返回新增条数。"""
    created = 0
    with _session() as db:
        existing = {r for r in db.scalars(select(PlatformService.service_code))}
        for item in DEFAULT_SERVICES:
            if item["serviceCode"] in existing:
                continue
            db.add(PlatformService(
                service_code=item["serviceCode"], service_name=item["serviceName"],
                tier=item["tier"], status="ACTIVE"))
            created += 1
        db.commit()
    return created


def _service_dto(row: PlatformService) -> dict:
    return {
        "serviceId": str(row.id), "serviceCode": row.service_code, "serviceName": row.service_name,
        "tier": row.tier, "status": row.status,
        "ownerUserId": str(row.owner_user_id) if row.owner_user_id else None,
        "ownerName": row.owner_name, "responders": row.responders_json or [],
        "approvers": row.approvers_json or [], "runbookUrl": row.runbook_url,
        "monitoringUrl": row.monitoring_url, "sloTarget": row.slo_target,
        "description": row.description, "version": int(row.version or 0),
        "hasOwner": bool(row.owner_user_id or row.owner_name),
        "hasRunbook": bool(row.runbook_url),
        "releaseBlocked": row.tier == "P0" and not (
            (row.owner_user_id or row.owner_name) and row.runbook_url),
    }


def list_services() -> list[dict]:
    with _session() as db:
        rows = db.scalars(select(PlatformService).where(
            PlatformService.is_deleted.is_(False)).order_by(PlatformService.tier, PlatformService.service_code)).all()
        return [_service_dto(r) for r in rows]


def upsert_service(payload: dict, *, expected_version: int | None = None) -> dict:
    code = str(payload.get("serviceCode") or "").strip()
    if not code:
        raise AppException("VALIDATION_ERROR", "serviceCode 不能为空", http_status=422)
    name = str(payload.get("serviceName") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "serviceName 不能为空", http_status=422)
    tier = str(payload.get("tier") or "P2").upper()
    if tier not in ("P0", "P1", "P2", "P3"):
        raise AppException("VALIDATION_ERROR", "tier 必须是 P0/P1/P2/P3", http_status=422)

    with _session() as db:
        row = db.scalars(select(PlatformService).where(
            PlatformService.service_code == code, PlatformService.is_deleted.is_(False))).first()
        if row and expected_version is not None and int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "服务条目已被他人更新，请刷新后重试", http_status=409)
        if row is None:
            row = PlatformService(service_code=code, service_name=name, tier=tier)
            db.add(row)
        else:
            row.service_name = name
            row.tier = tier
            row.version = int(row.version or 0) + 1
        row.status = str(payload.get("status") or row.status or "ACTIVE")
        row.owner_user_id = payload.get("ownerUserId") or None
        row.owner_name = payload.get("ownerName") or None
        row.responders_json = payload.get("responders") or []
        row.approvers_json = payload.get("approvers") or []
        row.runbook_url = payload.get("runbookUrl") or None
        row.monitoring_url = payload.get("monitoringUrl") or None
        row.slo_target = payload.get("sloTarget") or None
        row.description = payload.get("description") or None
        db.commit()
        return _service_dto(row)


def _all_edges(db) -> list[tuple[str, str]]:
    return [(r.service_code, r.depends_on_service_code) for r in db.scalars(
        select(ServiceDependency)).all()]


def _reachable(edges: list[tuple[str, str]], start: str) -> set[str]:
    """从 start 出发，沿"依赖"方向（service -> depends_on）能到达的所有服务码。"""
    adj: dict[str, list[str]] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
    seen: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def list_dependencies(service_code: str | None = None) -> list[dict]:
    with _session() as db:
        q = select(ServiceDependency)
        if service_code:
            q = q.where(ServiceDependency.service_code == service_code)
        rows = db.scalars(q.order_by(ServiceDependency.service_code)).all()
        return [{
            "id": str(r.id), "serviceCode": r.service_code,
            "dependsOnServiceCode": r.depends_on_service_code,
            "dependencyType": r.dependency_type,
        } for r in rows]


def add_dependency(service_code: str, depends_on_service_code: str, *,
                   dependency_type: str = "HARD") -> dict:
    """加边前证明不会成环：depends_on_service_code 出发沿依赖方向不能到达 service_code
    （否则 service_code -> depends_on_service_code -> ... -> service_code 成环）。"""
    service_code = str(service_code or "").strip()
    depends_on_service_code = str(depends_on_service_code or "").strip()
    if not service_code or not depends_on_service_code:
        raise AppException("VALIDATION_ERROR", "serviceCode 与 dependsOnServiceCode 不能为空",
                           http_status=422)
    if service_code == depends_on_service_code:
        raise AppException("VALIDATION_ERROR", "服务不能依赖自身", http_status=422)

    with _session() as db:
        codes = {r for r in db.scalars(select(PlatformService.service_code))}
        if service_code not in codes or depends_on_service_code not in codes:
            raise AppException("DATA_NOT_FOUND", "服务不存在，请先登记到服务目录", http_status=404)

        edges = _all_edges(db)
        if service_code in _reachable(edges, depends_on_service_code):
            raise AppException(
                "DATA_CONFLICT",
                f"新增依赖会形成循环依赖：{depends_on_service_code} 已经（直接或间接）依赖 {service_code}",
                http_status=409)

        existing = db.scalars(select(ServiceDependency).where(
            ServiceDependency.service_code == service_code,
            ServiceDependency.depends_on_service_code == depends_on_service_code)).first()
        if existing:
            existing.dependency_type = dependency_type
            db.commit()
            row = existing
        else:
            row = ServiceDependency(service_code=service_code,
                                    depends_on_service_code=depends_on_service_code,
                                    dependency_type=dependency_type)
            db.add(row)
            db.commit()
        return {"id": str(row.id), "serviceCode": row.service_code,
               "dependsOnServiceCode": row.depends_on_service_code,
               "dependencyType": row.dependency_type}


def remove_dependency(dependency_id: int) -> None:
    with _session() as db:
        row = db.get(ServiceDependency, int(dependency_id))
        if not row:
            raise AppException("DATA_NOT_FOUND", "依赖边不存在", http_status=404)
        db.delete(row)
        db.commit()


def record_tenant_usage(service_code: str, tenant_id: int, *, usage_status: str = "ACTIVE") -> None:
    with _session() as db:
        row = db.scalars(select(ServiceTenantUsage).where(
            ServiceTenantUsage.service_code == service_code,
            ServiceTenantUsage.tenant_id == int(tenant_id))).first()
        if row:
            row.usage_status = usage_status
            row.last_used_at = datetime.utcnow()
        else:
            db.add(ServiceTenantUsage(service_code=service_code, tenant_id=int(tenant_id),
                                      usage_status=usage_status, last_used_at=datetime.utcnow()))
        db.commit()


def compute_service_impact(service_code: str) -> dict:
    """service_code 故障时：direct = 直接用它的租户；indirect = 用"依赖它的其它服务"的租户。"""
    service_code = str(service_code or "").strip()
    with _session() as db:
        if not db.scalars(select(PlatformService.id).where(
                PlatformService.service_code == service_code)).first():
            raise AppException("DATA_NOT_FOUND", "服务不存在", http_status=404)

        edges = _all_edges(db)
        # 反向图：谁依赖 service_code（直接或间接）
        rev: dict[str, list[str]] = {}
        for a, b in edges:
            rev.setdefault(b, []).append(a)
        seen: set[str] = set()
        stack = [service_code]
        while stack:
            cur = stack.pop()
            for dependent in rev.get(cur, []):
                if dependent not in seen:
                    seen.add(dependent)
                    stack.append(dependent)
        affected_services = sorted(seen)

        direct_rows = db.scalars(select(ServiceTenantUsage.tenant_id).where(
            ServiceTenantUsage.service_code == service_code,
            ServiceTenantUsage.usage_status == "ACTIVE")).all()
        direct_tenants = {str(t) for t in direct_rows}

        indirect_tenants: set[str] = set()
        if affected_services:
            indirect_rows = db.scalars(select(ServiceTenantUsage.tenant_id).where(
                ServiceTenantUsage.service_code.in_(affected_services),
                ServiceTenantUsage.usage_status == "ACTIVE")).all()
            indirect_tenants = {str(t) for t in indirect_rows} - direct_tenants

        return {
            "serviceCode": service_code,
            "directTenants": sorted(direct_tenants),
            "indirectTenants": sorted(indirect_tenants),
            "affectedServices": affected_services,
            "totalAffectedTenants": len(direct_tenants | indirect_tenants),
        }


def assert_release_allowed(service_code: str) -> None:
    """P0 服务必须有 owner 且有 runbook 才允许发布；给 PLAT-11 变更管理调用的门禁。"""
    with _session() as db:
        row = db.scalars(select(PlatformService).where(
            PlatformService.service_code == service_code,
            PlatformService.is_deleted.is_(False))).first()
        if not row:
            raise AppException("DATA_NOT_FOUND", "服务不存在", http_status=404)
        if row.tier != "P0":
            return
        if not (row.owner_user_id or row.owner_name) or not row.runbook_url:
            raise AppException(
                "VALIDATION_ERROR",
                f"P0 服务 {service_code} 缺少 owner 或 runbook，禁止发布", http_status=422,
                details={"hasOwner": bool(row.owner_user_id or row.owner_name),
                        "hasRunbook": bool(row.runbook_url)})


def governance_overview() -> dict:
    with _session() as db:
        services = db.scalars(select(PlatformService).where(
            PlatformService.is_deleted.is_(False))).all()
        edges = _all_edges(db)
        dependents_count: dict[str, int] = {}
        for _a, b in edges:
            dependents_count[b] = dependents_count.get(b, 0) + 1

        p0_services = [s for s in services if s.tier == "P0"]
        degraded = [s for s in services if s.status == "DEGRADED"]
        no_owner = [s for s in services if not (s.owner_user_id or s.owner_name)]
        single_point = [s for s in services if s.tier in ("P0", "P1")
                        and dependents_count.get(s.service_code, 0) >= 1]

        return {
            "totalServices": len(services),
            "p0Count": len(p0_services),
            "degradedCount": len(degraded),
            "degradedServices": [s.service_code for s in degraded],
            "noOwnerCount": len(no_owner),
            "noOwnerServices": [s.service_code for s in no_owner],
            "singlePointCount": len(single_point),
            "singlePointServices": [s.service_code for s in single_point],
            "sloRiskServices": [s.service_code for s in services
                               if s.tier in ("P0", "P1") and not s.slo_target],
            "recentIncidents": [],
            "recentIncidentsNote": "事件数据由 PLAT-09 提供，本卡（PLAT-08）尚未接入",
        }
