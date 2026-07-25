#!/usr/bin/env python3
"""学生敏感字段与主档写入静态合同检查（学生主档统一整改 阶段 A）。

拦四类已确认会造成真实事故的写法：
  1) 把密文列直接交给脱敏函数 —— 页面显示的是「被遮住的 Fernet 密文」而不是手机号/证件号；
  2) `*_encrypted` 列直接接请求变量 —— 明文写进密文列；
  3) 敏感字段用裸 hashlib 摘要 —— 手机号/证件号空间有限，无密钥摘要可被穷举反查；
  4) 前端学生路由/菜单引用后端不存在的权限码 —— STUDENT 已纳入守卫，会对所有人 fail-closed。

用法：
  python scripts/check/check-student-sensitive-contracts.py          # 检查，违规则退出码 1
  python scripts/check/check-student-sensitive-contracts.py --list   # 只列出命中，不影响退出码
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend" / "app"
FRONTEND = ROOT / "frontend" / "src"
ALLOWLIST = Path(__file__).with_name("student-sensitive-allowlist.json")

# ── 规则 1：密文列直接脱敏 ────────────────────────────────────────────────
# 正确写法是 mask_phone_encrypted() / mask_id_card_encrypted()（core.field_crypto 内先解密再脱敏）。
RE_MASK_CIPHERTEXT = re.compile(r"\b_?mask_(?:phone|id_card)\s*\(\s*[^)]*_encrypted\b")

# ── 规则 2：密文列接请求变量（明文入库） ──────────────────────────────────
# 命中 `xxx_encrypted=body.get(...)` / `= r.get("phone")` / `= payload.phone` 等直取写法；
# encrypt_field(...) / encrypt_sensitive(...) 包裹的不算。
RE_PLAINTEXT_TO_ENCRYPTED = re.compile(
    r"\b\w*_encrypted\s*=\s*(?!encrypt_|None\b|\"\"|''|_)"
    r"(?:body|payload|row|r|data|form|req|request|kwargs)\b[.\[]"
)

# ── 规则 3：敏感值裸摘要 ──────────────────────────────────────────────────
RE_BARE_HASH = re.compile(
    r"hashlib\.(?:sha256|md5|sha1)\s*\([^)]*"
    r"(?:phone|id_card|idCard|identity|student_no)\b", re.IGNORECASE)

SKIP_DIR_PARTS = {"__pycache__", "node_modules", "dist", ".git", "alembic"}


def _iter_py(base: Path):
    for p in sorted(base.rglob("*.py")):
        if SKIP_DIR_PARTS & set(p.parts):
            continue
        yield p


def _load_allowlist() -> set[str]:
    """允许列表条目：`相对路径:行内容关键片段`，必须写明 reason 与 removeByPhase。"""
    if not ALLOWLIST.exists():
        return set()
    raw = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    keys = set()
    for item in raw.get("allow", []):
        if not item.get("reason") or not item.get("removeByPhase"):
            print(f"[配置错误] 允许列表条目缺 reason/removeByPhase：{item}")
            sys.exit(2)
        keys.add(f"{item['path']}::{item['anchor']}")
    return keys


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def scan_backend(allow: set[str]) -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    rules = [
        ("密文直接脱敏（应改用 mask_*_encrypted）", RE_MASK_CIPHERTEXT),
        ("明文写入 _encrypted 列（应经 encrypt_field/encrypt_sensitive）", RE_PLAINTEXT_TO_ENCRYPTED),
        ("敏感值裸哈希（应改用 hash_sensitive 的 HMAC）", RE_BARE_HASH),
    ]
    for path in _iter_py(BACKEND):
        rel = _rel(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for no, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for label, rx in rules:
                if not rx.search(line):
                    continue
                if any(k.split("::", 1)[0] == rel and k.split("::", 1)[1] in line for k in allow):
                    continue
                hits.append((rel, no, label, stripped[:120]))
    return hits


# ── 规则 4：前端学生权限码必须在后端真实存在 ──────────────────────────────
RE_PERM_KEY = re.compile(r"permissionKey:\s*'([^']+)'")
RE_PERM_ANY = re.compile(r"permissionAny:\s*\[([^\]]*)\]")
RE_STR = re.compile(r"'([^']+)'")


def _backend_student_permission_codes() -> set[str]:
    """后端真实出现过的 student.* 权限码（require_permission / has_permission / 角色模板）。"""
    codes: set[str] = set()
    rx = re.compile(r"[\"']((?:student|studentAffairs\.student)\.[a-zA-Z0-9_.]+)[\"']")
    for path in _iter_py(BACKEND):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        codes.update(rx.findall(text))
    return codes


def scan_frontend_permissions() -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    backend_codes = _backend_student_permission_codes()
    if not backend_codes:
        return hits  # 后端不可读时不误报
    targets = [FRONTEND / "modules" / "student" / "student.routes.js"]
    for path in targets:
        if not path.exists():
            continue
        rel = _rel(path)
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            found = list(RE_PERM_KEY.findall(line))
            for grp in RE_PERM_ANY.findall(line):
                found.extend(RE_STR.findall(grp))
            for code in found:
                if not code.startswith(("student.", "studentAffairs.student")):
                    continue
                if code not in backend_codes:
                    hits.append((rel, no, "前端引用了后端不存在的学生权限码（守卫会 fail-closed）", code))
    return hits


def main() -> int:
    list_only = "--list" in sys.argv
    allow = _load_allowlist()
    hits = scan_backend(allow) + scan_frontend_permissions()
    if not hits:
        print("学生敏感字段/权限码合同检查：通过")
        return 0
    print(f"学生敏感字段/权限码合同检查：命中 {len(hits)} 处\n")
    for rel, no, label, snippet in hits:
        print(f"  {rel}:{no}\n    规则：{label}\n    代码：{snippet}\n")
    if list_only:
        return 0
    print("如为迁移期必须保留，请在 scripts/check/student-sensitive-allowlist.json "
          "登记 path/anchor/reason/removeByPhase。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
