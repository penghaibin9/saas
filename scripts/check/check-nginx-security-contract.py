#!/usr/bin/env python
"""生产 Nginx 安全合同门禁：所有部署方式必须达到同一条安全基线。

问题是什么
──────────
本项目有多套部署入口（Docker / systemd / 手工 HTTPS / 各端子站），每套 Nginx
配置各写了一部分安全措施：

- `nginx.mysql.conf`：有 CSP、有 API/登录限流，但 `listen 80`、没有 HSTS；
- `nginx.https.conf.example`：有 TLS + HSTS，但**没有 CSP、没有限流**；
- `school-lifecycle.systemd.conf.example`：同上；
- `nginx.portal.conf.example`：安全指令一条没有。

于是"这所学校安不安全"取决于当初用了哪份模板 —— 卖到几十所学校后无法维护。

本门禁做什么
────────────
把安全基线写成一份**唯一合同**，对每个"完整 server 配置"逐条校验。
只含 location 片段的配置（由主站 server 引入）不适用整站级要求。

用法：
    python scripts/check/check-nginx-security-contract.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

NGINX_DIR = Path(__file__).resolve().parents[2] / "deploy" / "nginx"


# ── 安全合同 ────────────────────────────────────────────────────────
# 每项：(人类可读名, 判定函数, 是否仅在 HTTPS 配置上要求)
def _has(pattern: str):
    return lambda text: re.search(pattern, text, re.I) is not None


CONTRACT = [
    ("Content-Security-Policy", _has(r"add_header\s+Content-Security-Policy"), False),
    ("X-Frame-Options", _has(r"add_header\s+X-Frame-Options"), False),
    ("X-Content-Type-Options", _has(r"add_header\s+X-Content-Type-Options"), False),
    ("Referrer-Policy", _has(r"add_header\s+Referrer-Policy"), False),
    ("请求体大小上限 client_max_body_size", _has(r"client_max_body_size"), False),
    ("登录接口限流 limit_req", _has(r"limit_req\s"), False),
    ("禁止直读 /uploads 与 /exports", _has(r"location[^\n]*(uploads|exports)"), False),
    ("HSTS（仅 HTTPS 配置要求）", _has(r"add_header\s+Strict-Transport-Security"), True),
]

# CSP 中禁止出现的指令：unsafe-eval 基本让 CSP 失去防 XSS 意义。
CSP_FORBIDDEN = ["'unsafe-eval'"]


def _resolve_includes(text: str, depth: int = 0) -> str:
    """把 include 的本地安全片段内联进来再判定。

    安全基线的唯一事实源是 security-http.conf / security-server.conf，
    各部署配置通过 include 引用；检查器必须顺着 include 看，否则会把
    "正确地复用了共享片段" 误判成 "什么都没配"。
    """
    if depth > 3:
        return text
    out = [text]
    for name in re.findall(r"^\s*include\s+[^;\n]*?([\w.-]+\.conf)\s*;", text, re.M):
        candidate = NGINX_DIR / name
        if candidate.is_file():
            out.append(_resolve_includes(
                candidate.read_text(encoding="utf-8", errors="replace"), depth + 1))
    return "\n".join(out)


def _is_full_server(text: str) -> bool:
    """完整 server 配置（含 listen），而非只有 location 的片段。"""
    return re.search(r"^\s*server\s*\{", text, re.M) is not None and \
        re.search(r"^\s*listen\s", text, re.M) is not None


def _is_https(text: str) -> bool:
    return re.search(r"listen\s+443|ssl_certificate\s", text, re.I) is not None


def _add_header_inheritance_violations(raw: str) -> list[str]:
    """找出会把安全头整层丢掉的 location 块。

    Nginx 的 add_header 不是叠加：一个 location 只要写了任意一条 add_header，
    就会丢弃从 server{}/http{} 继承来的**全部** add_header。所以给 index.html 或
    静态资源加个 Cache-Control，就会顺手把 CSP 从 HTML 文档上摘掉 ——
    偏偏 HTML 文档才是 CSP 最该生效的地方。这个坑不看 nginx -t，只能靠门禁。
    """
    lines = raw.splitlines()
    bad: list[str] = []
    i = 0
    while i < len(lines):
        if not re.match(r"^\s*location\b.*\{", lines[i]):
            i += 1
            continue
        depth, j, block = 0, i, []
        while j < len(lines):
            depth += lines[j].count("{") - lines[j].count("}")
            block.append(lines[j])
            j += 1
            if depth <= 0:
                break
        body = "\n".join(block)
        body_effective = "\n".join(
            l for l in block if not l.lstrip().startswith("#"))
        if "add_header" in body_effective and "security-headers.conf" not in body:
            bad.append(f"第 {i + 1} 行 location 自带 add_header 但未 include "
                       f"security-headers.conf（安全头会被整层丢弃）")
        i = j
    return bad


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not NGINX_DIR.is_dir():
        print(f"找不到 Nginx 配置目录：{NGINX_DIR}")
        return 2

    failures: list[str] = []
    checked = 0
    for path in sorted(NGINX_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix not in (".conf", ".example") and ".conf" not in path.name:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if path.name.startswith("security-"):
            continue  # 合同片段本身，不是部署配置
        text = _resolve_includes(raw)
        # 继承陷阱对片段同样适用（片段里的 location 一样会丢掉主站的安全头）
        trap = _add_header_inheritance_violations(raw)
        if not _is_full_server(raw):
            if trap:
                failures.append(f"{path.name}：add_header 继承陷阱")
                print(f"❌ {path.name}（片段）")
                for item in trap:
                    print(f"     - {item}")
            else:
                print(f"·  {path.name}：location 片段，整站级要求不适用")
            continue
        checked += 1
        https = _is_https(text)
        missing = [
            name for name, check, https_only in CONTRACT
            if (not https_only or https) and not check(text)
        ]
        # 只看真正生效的指令，注释里提到 'unsafe-eval' 三个字不算违规。
        effective = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#"))
        for token in CSP_FORBIDDEN:
            if token in effective:
                missing.append(f"CSP 含被禁指令 {token}")
        missing.extend(trap)
        if missing:
            failures.append(f"{path.name}：缺 " + "、".join(missing))
            print(f"❌ {path.name}")
            for item in missing:
                print(f"     - {item}")
        else:
            print(f"✅ {path.name}（{'HTTPS' if https else 'HTTP'}）")

    print()
    if failures:
        print(f"生产 Nginx 安全合同未达标（{len(failures)}/{checked} 份配置）。")
        print("同一套系统卖给不同学校，安全等级不得取决于当初用了哪份模板。")
        return 1
    print(f"✅ {checked} 份完整 server 配置全部满足生产安全合同")
    return 0


if __name__ == "__main__":
    sys.exit(main())
