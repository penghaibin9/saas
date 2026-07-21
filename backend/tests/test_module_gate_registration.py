"""P2-5 加固：模块门禁键必须已注册 + require_staff 白名单 + 多实例 Redis 守卫。

背景（真实 fail-open）：platform_service.effective_features 只返回 FEATURE_KEYS 内的键，
feature_enabled 再 `.get(key, True)`——任何未注册键都恒放行，require_module 形同虚设。
此前 module.graduationDesign.enabled 未注册即中招。本测试静态扫描全部 require_module 调用点，
任何新增的未注册键都会在此红灯，杜绝重蹈覆辙。纯单元，不依赖 DB / 客户端。
"""
from __future__ import annotations

import ast
import pathlib

APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"


def _collect_require_module_keys() -> list[tuple[str, str, int]]:
    """遍历 app/ 下所有 .py，收集 require_module("字面量") 的键。
    返回 [(key, 相对文件, 行号)]，只取字面量参数（动态拼接的键无法静态核验，另行人工把关）。"""
    found: list[tuple[str, str, int]] = []
    for path in APP_DIR.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "require_module"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                rel = str(path.relative_to(APP_DIR.parent))
                found.append((node.args[0].value, rel, node.lineno))
    return found


def test_all_require_module_keys_are_registered():
    """所有 require_module 的键都必须在 FEATURE_KEYS 注册，否则 feature_enabled 恒放行（门禁失效）。"""
    from app.services.platform_defaults import FEATURE_KEYS

    keys = _collect_require_module_keys()
    assert keys, "未扫描到任何 require_module 调用点，测试自身失效，请检查扫描逻辑"
    unregistered = [(k, f, ln) for (k, f, ln) in keys if k not in FEATURE_KEYS]
    assert not unregistered, (
        "以下 require_module 键未在 platform_defaults.FEATURE_KEYS 注册，"
        "effective_features 不会返回该键，feature_enabled 将恒放行（门禁失效）：\n"
        + "\n".join(f"  - {k!r}  @ {f}:{ln}" for (k, f, ln) in unregistered))


def test_feature_enabled_semantics_documented_as_fail_open():
    """守住语义：未注册键在 effective_features 中不存在（这正是上一个测试必须存在的原因）。"""
    from app.services.platform_defaults import FEATURE_KEYS

    # 已在用的四个业务模块键均已注册
    for k in ("graduation", "internship", "studentAffairs", "campusService"):
        assert k in FEATURE_KEYS, f"在用模块键 {k!r} 缺失注册"
    # 历史误用的未注册键不得再出现在任何 require_module 调用点
    live_keys = {k for (k, _f, _ln) in _collect_require_module_keys()}
    assert "module.graduationDesign.enabled" not in live_keys, (
        "毕设门禁又用回了未注册键 module.graduationDesign.enabled（fail-open），应改用 'graduation'")


# ── P2-1：require_staff 白名单 ──

def test_require_staff_whitelist_allows_all_staff_types():
    from app.core.security import STAFF_USER_TYPES, require_staff

    for ut in ("TEACHER", "ADMIN", "STAFF", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"):
        assert require_staff({"userType": ut}) == {"userType": ut}
        assert ut in STAFF_USER_TYPES
    # 大小写/空白规整后仍放行
    assert require_staff({"userType": " teacher "})["userType"] == " teacher "


def test_require_staff_rejects_students_guardians_and_unknowns():
    from app.core.exceptions import AppException
    from app.core.security import require_staff

    for bad in ("STUDENT", "GUARDIAN", "", None, "SOMETHING_ELSE", "OUTSIDER"):
        try:
            require_staff({"userType": bad})
        except AppException:
            continue
        raise AssertionError(f"userType={bad!r} 不应通过 require_staff（白名单应拒绝）")


# ── P1-1：多实例 Redis 守卫 ──

def test_assert_scale_safe_matrix(monkeypatch):
    from app.core import security
    from app.core.config import settings

    def run(is_prod, multi, redis_url):
        monkeypatch.setattr(type(settings), "is_prod", property(lambda self: is_prod))
        monkeypatch.setattr(settings, "MULTI_INSTANCE", multi)
        monkeypatch.setattr(settings, "REDIS_URL", redis_url)
        security.assert_scale_safe()

    # 唯一必须炸的组合：生产 + 多实例 + 无 Redis
    raised = False
    try:
        run(True, True, "")
    except RuntimeError:
        raised = True
    assert raised, "生产环境多实例且无 Redis 必须拒绝启动"

    # 其余组合均放行（单进程 / 有 Redis / 非生产）
    run(True, True, "redis://127.0.0.1:6379/0")  # 有 Redis
    run(True, False, "")                          # 单进程
    run(False, True, "")                          # 非生产
