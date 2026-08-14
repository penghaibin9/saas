"""旧学生实习入口止血守卫（V93-02 / 总册 §7）。

背景（git 事实，非推测）：`mobile.py` 的 `internship_mobile` 路由建于 2026-07-05，即本仓库
开工第三天；`/context/*` canonical 路由建于 2026-07-26。两者都是本项目自己写的，第二版
上线后第一版从未退休，于是同一份业务同时挂着两个写入口。

已核实旧入口**当前不构成越权漏洞**：expectedVersion 校验在 service 层生效，与走哪个路由无关；
「回退到当前实习记录」的 resolver 是 fail-closed 的（多条进行中直接 NEED_SELECT 拒绝）。
所以这不是必须立刻拔掉的安全问题，而是必须停止扩散的架构债——真正的删除要连着 7 个学生端
页面一起改、真机验过再做，不能夹在性能改造里顺手删。

本文件就是那道止血闸：已有替代品的旧入口必须挂 deprecated，且数量只许减不许增。
"""
from __future__ import annotations

import pytest

# 冻结基线：当前有 canonical /context/* 替代、因而已标记 deprecated 的旧入口数量。
# 收敛旧入口时把这个数字调小；调大意味着又新增了一个本可以走 canonical 的旧写入口。
DEPRECATED_BASELINE = 29

# 这些旧入口暂时没有 canonical 替代，不标 deprecated（标了等于让人无路可走）。
# 每从这里挪走一条，都应当是因为它的 /context/* 版本真的建好了。
KNOWN_WITHOUT_REPLACEMENT = {
    "/checkin", "/checkin/week", "/enterprises", "/exceptions/{exception_id}/appeal",
    "/help", "/consents/{consent_id}", "/consents/{consent_id}/confirm",
    "/consents/{consent_id}/view", "/consents/{consent_id}/reject",
    "/intention", "/intention/submit", "/intention/withdraw",
    "/insurance", "/safety/courses/{course_id}/start",
    "/safety/courses/{course_id}/submit", "/safety/completions/{completion_id}/commit",
    "/agreements/{agreement_id}/esign/sign", "/my",
    # 这条本身就长在 canonical 的 mobile_internship_student.py 上，只是没带 /context/ 前缀，
    # 不是遗留入口；登记在此以免被误判成待收敛的旧路由。
    "/safety/courses/{course_id}/detail",
}

PREFIX = "/api/v1/mobile/internship"


def _legacy_routes():
    """mobile.py 上的旧学生实习路由；canonical 的 /context/* 不算在内。

    读 OpenAPI schema 而不是 app.routes：本应用用懒加载 router 挂载，路由对象在
    app.routes 上并未展开，直接遍历会一条都取不到（而且会静默取到空集，让守卫假绿）。
    """
    from app.main import app

    found = []
    for path, ops in (app.openapi().get("paths") or {}).items():
        if not path.startswith(PREFIX):
            continue
        tail = path[len(PREFIX):]
        if tail.startswith("/context/") or tail.startswith("/compliance/"):
            continue
        for method, op in ops.items():
            if method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                found.append((method.upper(), tail, bool(op.get("deprecated"))))
    return found


def test_route_probe_actually_sees_routes():
    """守卫自身的自检：取不到任何旧路由时，上面几条断言会全部假绿。"""
    assert _legacy_routes(), "没有取到任何旧学生实习路由，说明探测方式失效，守卫已形同虚设"


def test_legacy_routes_with_replacement_are_marked_deprecated():
    """有 canonical 替代的旧入口必须在 OpenAPI 上明确标废弃。

    这样新同事（和未来的我）打开接口文档就能看出该走哪个，而不是照着最先搜到的那个写。
    """
    undeclared = []
    for method, tail, deprecated in _legacy_routes():
        if tail in KNOWN_WITHOUT_REPLACEMENT:
            continue
        if not deprecated:
            undeclared.append(f"{method} {tail}")
    assert not undeclared, (
        "以下旧学生实习入口已有 /context/* 替代却没标 deprecated，"
        f"新代码会继续接到旧链上：{sorted(undeclared)}"
    )


def test_deprecated_legacy_surface_does_not_grow():
    """旧入口只许减不许增。

    这条是本文件的真正目的：不阻止现有旧入口继续服役（拔掉要连学生端页面一起改），
    但任何「又加了一个本该走 canonical 的旧写入口」都会在这里立刻变红。
    """
    count = sum(
        1 for _m, tail, deprecated in _legacy_routes()
        if tail not in KNOWN_WITHOUT_REPLACEMENT and deprecated
    )
    assert count <= DEPRECATED_BASELINE, (
        f"旧学生实习入口从 {DEPRECATED_BASELINE} 增加到了 {count}。"
        "新功能必须走 /mobile/internship/context/*，不要再往 mobile.py 上加写入口。"
    )


def test_no_new_legacy_route_without_replacement():
    """没有 canonical 替代的旧入口清单被冻结，新增必须显式登记。

    冻结它是为了让「又冒出一个没有 canonical 版本的学生写入口」成为一个需要有人
    主动改测试、因而被看见的动作，而不是悄悄混进来。
    """
    live = {tail for _m, tail, _d in _legacy_routes()}
    unregistered = {
        tail for tail in live
        if tail in KNOWN_WITHOUT_REPLACEMENT
    }
    stale = KNOWN_WITHOUT_REPLACEMENT - live
    assert not stale, (
        f"清单里这些旧入口已经不存在了，请同步删掉登记：{sorted(stale)}"
    )
    assert unregistered <= KNOWN_WITHOUT_REPLACEMENT
