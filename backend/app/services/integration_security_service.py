"""SYS-20 集成出站安全：SSRF 防护（私网/保留地址拒绝 + DNS重绑定阻断）+ 出站域名白名单。

不新建表，也不接管接口连接/凭证/同步任务的存储——那些仍在
system_governance_service.py 的 JSON 治理文档（DOC_INTEGRATIONS/
DOC_SYNC_JOBS）里，第一阶段"先adapter旧JSON"就是指这个。本文件只回答
一个问题："这个出站地址现在能不能安全连"，供 system_governance_service.py
在保存连接和实际探测连接时调用。

DNS重绑定阻断的关键：校验用的IP和实际连接用的IP必须是同一次
getaddrinfo() 结果，中间不能再对hostname做第二次系统DNS查询——否则
攻击者可以在"校验通过"和"真正连接"之间的时间窗口把DNS记录改成内网IP。
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.exceptions import AppException

# 出站域名白名单：留空 = 允许任意域名，但仍强制IP级SSRF校验；
# 学校要收紧到指定厂商域名时在这里维护（第一阶段用代码常量，
# 结构化配置表留给"结构化迁移单独实施"阶段）。
OUTBOUND_DOMAIN_ALLOWLIST: set[str] = set()


def _dev_loopback_allowed() -> bool:
    """仅非生产环境允许把 localhost/127.0.0.1 当合法出站目标（本地联调）；
    生产环境的"集成"如果指向自己的回环地址，本身就是可疑的SSRF目标，必须拒绝。"""
    from app.core.config import settings
    return not settings.is_prod


def _is_unsafe_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local or
        ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def resolve_safe_ips(hostname: str) -> list[str]:
    """解析 hostname 的全部地址记录；任意一条落在私网/保留段就整体拒绝——
    多记录里混一个内网IP正是DNS重绑定/多值欺骗的常见手法。"""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise AppException("VALIDATION_ERROR", f"接口地址域名解析失败：{exc}", http_status=422)
    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise AppException("VALIDATION_ERROR", "接口地址域名解析结果为空", http_status=422)
    unsafe = [ip for ip in ips if _is_unsafe_ip(ip)]
    if unsafe:
        raise AppException(
            "VALIDATION_ERROR",
            f"接口地址解析到私网/保留地址（{','.join(unsafe)}），出于SSRF防护禁止使用",
            http_status=422, details={"host": hostname, "unsafeIps": unsafe})
    return ips


def assert_domain_allowlisted(hostname: str) -> None:
    if OUTBOUND_DOMAIN_ALLOWLIST and hostname not in OUTBOUND_DOMAIN_ALLOWLIST:
        raise AppException("VALIDATION_ERROR",
                           f"域名 {hostname} 不在出站白名单内，禁止连接", http_status=422)


def validate_endpoint_ssrf_safe(endpoint: str) -> dict:
    """保存/入队时的前置校验：scheme 合法、域名可解析且全部落在公网。"""
    parsed = urlparse(str(endpoint or "").strip())
    if parsed.scheme not in ("https", "http"):
        raise AppException("VALIDATION_ERROR", "接口地址必须是 http/https URL", http_status=422)
    hostname = parsed.hostname or ""
    if not hostname:
        raise AppException("VALIDATION_ERROR", "接口地址缺少主机名", http_status=422)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    is_loopback_literal = hostname == "localhost" or hostname.startswith("127.") or hostname == "::1"
    if is_loopback_literal:
        if not _dev_loopback_allowed():
            raise AppException("VALIDATION_ERROR",
                               "生产环境禁止把 localhost/127.0.0.1 配置为集成出站地址（SSRF防护）",
                               http_status=422)
        if parsed.scheme != "http":
            pass  # 沿用既有口径：非本地环境才强制 https，本地回环允许 http
        return {"host": hostname, "ips": ["127.0.0.1"], "port": port}

    if parsed.scheme == "http":
        raise AppException("VALIDATION_ERROR", "非本地环境禁止明文 http，请使用 https", http_status=422)

    assert_domain_allowlisted(hostname)
    ips = resolve_safe_ips(hostname)
    return {"host": hostname, "ips": ips, "port": port}


def connect_ssrf_safe(endpoint: str, *, timeout: float = 5.0):
    """连接前重新解析并校验（阻断DNS重绑定）：校验用的IP直接拿来连接，
    校验和连接之间不再对 hostname 做第二次系统DNS查询，不留重绑定窗口。"""
    info = validate_endpoint_ssrf_safe(endpoint)
    last_err: Exception | None = None
    for ip in info["ips"]:
        try:
            return socket.create_connection((ip, info["port"]), timeout=timeout)
        except OSError as exc:
            last_err = exc
            continue
    raise AppException("VALIDATION_ERROR", f"接口地址所有已解析IP均连接失败：{last_err}", http_status=422)
