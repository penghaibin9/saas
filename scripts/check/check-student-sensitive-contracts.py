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

# ── 规则 5：主档唯一写入口（阶段 B）────────────────────────────────────────
# StudentProfile 只能由 student_master_application_service 构造。四条建档链
# （手工/公共导入/统一身份导入/教务学籍导入）此前各建各的，导致组织不校验、
# 学号唯一规则与敏感字段口径各写一份。新增直接构造一律拦下。
# 负向后行排除 `class StudentProfile(...)` 的模型定义本身
RE_DIRECT_PROFILE_CREATE = re.compile(r"(?<!class )\bStudentProfile\s*\(")

# ── 规则 6：影子学生台账必须绑主档（阶段 D）────────────────────────────────
# 旧域的四张学生台账一旦不带 student_id 建行，就又多出一个"只存在于这个域里的学生"，
# 改学籍看不到、统计对不上、数据范围算不准。构造时必须同时给出 student_id。
RE_SHADOW_CREATE = re.compile(
    r"(?<!class )\b(CsServiceStudent|AcademicStudent|EmpStudent|OrientationStudent)\s*\(")
# 构造语句可能跨多行，向后看这么多行找 student_id=
SHADOW_LOOKAHEAD = 12
RE_BOUND_KW = re.compile(r"(?<![A-Za-z0-9_])student_id\s*=")

# ── 规则 7：学生身份不得再靠登录名等于学号（阶段 C/D）──────────────────────
# 正确入口是 student_account_link_service；直接写这条 JOIN 的地方，学号一更正就断链。
RE_LOGIN_NAME_JOIN = re.compile(r"User\.login_name\s*==\s*(?:StudentProfile\.student_no|str\(student_no\))")

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


def _code_lines(path: Path) -> tuple[list[str], list[str]] | None:
    """返回 (原始行, 去掉字符串/注释内容的行)。

    规则要匹配的是真实代码，不是文档里对错误写法的描述——本文件自己的说明和
    各服务顶部「不要再写 login_name == student_no」这类警示注释都不该被当成违规。
    用 tokenize 精确抹掉 STRING/COMMENT，避免正则去猜引号配对。
    """
    import io
    import tokenize

    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    lines = raw.splitlines()
    blanked = list(lines)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(raw).readline):
            if tok.type not in (tokenize.STRING, tokenize.COMMENT):
                continue
            (r1, c1), (r2, c2) = tok.start, tok.end
            for r in range(r1, r2 + 1):
                i = r - 1
                if i >= len(blanked):
                    break
                s = blanked[i]
                start = c1 if r == r1 else 0
                end = c2 if r == r2 else len(s)
                blanked[i] = s[:start] + " " * max(0, end - start) + s[end:]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return lines, lines  # 语法异常文件退回原始行，宁可多报不漏报
    return lines, blanked


def scan_backend(allow: set[str]) -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    rules = [
        ("密文直接脱敏（应改用 mask_*_encrypted）", RE_MASK_CIPHERTEXT),
        ("明文写入 _encrypted 列（应经 encrypt_field/encrypt_sensitive）", RE_PLAINTEXT_TO_ENCRYPTED),
        ("敏感值裸哈希（应改用 hash_sensitive 的 HMAC）", RE_BARE_HASH),
        ("直接构造 StudentProfile（须经 student_master_application_service）",
         RE_DIRECT_PROFILE_CREATE),
        ("学生身份靠 login_name==student_no 关联（须经 student_account_link_service）",
         RE_LOGIN_NAME_JOIN),
    ]
    for path in _iter_py(BACKEND):
        rel = _rel(path)
        got = _code_lines(path)
        if got is None:
            continue
        lines, code = got
        for no, line in enumerate(code, 1):
            stripped = lines[no - 1].strip()
            for label, rx in rules:
                if not rx.search(line):
                    continue
                if any(k.split("::", 1)[0] == rel and k.split("::", 1)[1] in lines[no - 1]
                       for k in allow):
                    continue
                hits.append((rel, no, label, stripped[:120]))
        hits.extend(_scan_shadow_creates(rel, lines, code, allow))
    return hits


def _call_span(lines: list[str], row: int, col: int) -> str:
    """从 `Model(` 的左括号开始截到配对的右括号为止。

    不能简单地"往后看 N 行"：紧跟其后的另一条语句里常有 cs_student_id=/student_id=，
    会把"这个构造没绑主档"误判成绑了。
    """
    depth, out = 0, []
    for r in range(row, min(row + SHADOW_LOOKAHEAD * 4, len(lines))):
        s = lines[r]
        start = col if r == row else 0
        for ch in s[start:]:
            out.append(ch)
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return "".join(out)
        out.append("\n")
    return "".join(out)


def _scan_shadow_creates(rel: str, lines: list[str], code: list[str], allow: set[str]):
    """影子台账构造未绑 student_id 的检查（构造参数常跨多行，逐行正则看不全）。"""
    out = []
    for no, line in enumerate(code, 1):
        stripped = lines[no - 1].strip()
        if not RE_SHADOW_CREATE.search(line):
            continue
        if any(k.split("::", 1)[0] == rel and k.split("::", 1)[1] in lines[no - 1] for k in allow):
            continue
        span = _call_span(lines, no - 1, RE_SHADOW_CREATE.search(line).end() - 1)
        # 构造参数里出现 student_id= 或整段快照展开（**snap）才算已绑定。
        # 必须带词边界：acad_student_id= / cs_student_id= / emp_student_id= 指向的是影子行自己，
        # 不是主档，用子串判断会把"没绑主档"误判成"已绑定"。
        if RE_BOUND_KW.search(span) or "**snap" in span or "**{k: v for k, v in snap" in span:
            continue
        out.append((rel, no, "影子学生台账未绑定 student_id（须经 shadow_student_service 解析主档）",
                    stripped[:120]))
    return out


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
