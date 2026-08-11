"""Heuristically list business queries that need a tenant-isolation review.

This read-only scanner is intentionally conservative: it does not claim that a
candidate is exploitable.  It highlights direct Session.get calls and SQLAlchemy
SELECT/UPDATE/DELETE statements whose source statement does not visibly mention
tenant_id or a recognized tenant helper.  Run after every new module is added.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"
EXCLUDED_PARTS = {"migrations", "platform_service.py", "tenant_context.py", "tenant_scoped.py"}
SAFE_MARKERS = ("tenant_id", "_tid(", "current_tenant_id", "tenant_scope", "tenantId",
                "tenant_get(", "tenant_select(", "assert_same_tenant(")
BASELINE = Path(__file__).resolve().parents[1] / "scripts" / "tenant-query-baseline.txt"


def _normalize_location(value: str) -> str:
    """Make baseline locations portable across Windows and Linux runners."""
    return value.strip().replace("\\", "/")


def _tenant_model_names() -> set[str]:
    """带 tenant_id 列的 ORM 模型名集合。

    只有这些模型上的裸 Session.get 才是真的跨租户风险；控制面表（t_tenant 等）
    本来就没有 tenant_id，混在一起统计会把信号淹掉，也让门禁无法执行。
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from app.db.base import Base  # noqa: WPS433
    except Exception as exc:  # noqa: BLE001
        # 不能静默退化：拿不到 ORM 就分不清租户表和控制面表，基线会整体错位，
        # 门禁要么全放行要么全拦住，两种都比直接报错更坏。
        raise SystemExit(
            f"无法加载 ORM 模型，租户门禁无法判定（请在装好后端依赖的环境运行）：{exc}")
    names = set()
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if "tenant_id" in model.__table__.columns:
            names.add(model.__name__)
    return names


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="return non-zero when direct Session.get calls are found")
    parser.add_argument("--gate", action="store_true",
                        help="与基线比对：只要新增未收口的裸 Session.get 就失败（棘轮）")
    parser.add_argument("--write-baseline", action="store_true",
                        help="把当前结果写成新基线（只允许在收口后下调）")
    return parser.parse_args()


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _get_model_name(node: ast.Call) -> str:
    """从 db.get(Model, id) 里取出模型名。"""
    if not node.args:
        return ""
    first = node.args[0]
    if isinstance(first, ast.Name):
        return first.id
    if isinstance(first, ast.Attribute):
        return first.attr
    return ""


def main() -> int:
    args = _args()
    tenant_models = _tenant_model_names()
    direct_gets: list[str] = []
    candidates: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            print(f"PARSE {path.relative_to(ROOT)}:{exc.lineno} {exc.msg}")
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name not in {"get", "select", "update", "delete"}:
                continue
            start = max(0, node.lineno - 1)
            end = min(len(lines), getattr(node, "end_lineno", node.lineno) + 3)
            statement = " ".join(lines[start:end])
            location = _normalize_location(f"{path.relative_to(ROOT)}:{node.lineno}")
            if (name == "get" and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id.lower() in {"db", "session"}):
                # Session.get(Model, id) never carries tenant_id itself.  The caller
                # must immediately re-check ownership or replace it with a scoped select.
                model_name = _get_model_name(node)
                # 只统计真正带 tenant_id 的模型；控制面模型没有租户维度，不构成越权面。
                if tenant_models and model_name and model_name not in tenant_models:
                    continue
                # 取行后若干行内已显式校验租户的，视为已收口。
                # 窗口要够宽：常见写法是 db.get 之后紧跟一个多条件的 if 一起判
                # is_deleted / tenant_id / 归属，3 行看不完。
                check_window = " ".join(
                    lines[start:min(len(lines), getattr(node, "end_lineno", node.lineno) + 10)])
                if any(marker in check_window for marker in SAFE_MARKERS):
                    continue
                direct_gets.append(location)
            elif name in {"select", "update", "delete"} and not any(
                    marker in statement for marker in SAFE_MARKERS):
                candidates.append(location)

    print(f"direct_session_get={len(direct_gets)} query_review_candidates={len(candidates)}")

    if args.write_baseline:
        BASELINE.write_text("\n".join(sorted(direct_gets)) + "\n", encoding="utf-8")
        print(f"baseline written: {BASELINE} ({len(direct_gets)} entries)")
        return 0

    if args.gate:
        # 棘轮门禁：历史 1000+ 处裸 Session.get 不可能一次改完，但**不许再增加**。
        # 新增一处未带租户校验的裸取行 = 直接拦住 PR。
        old = set()
        if BASELINE.exists():
            old = {
                _normalize_location(line)
                for line in BASELINE.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
        now = set(direct_gets)
        added = sorted(now - old)
        removed = len(old - now)
        if added:
            print(f"\n新增 {len(added)} 处未做租户校验的裸 Session.get（禁止新增）：")
            for item in added:
                print("  BLOCK", item)
            print("\n改法：用 app.core.tenant_scoped.tenant_get(db, Model, pk) 取行，"
                  "或取行后调用 assert_same_tenant(row)。")
            return 1
        print(f"tenant query ratchet OK（较基线收口 {removed} 处，无新增）")
        return 0

    for item in direct_gets:
        print("HIGH", item, "verify tenant ownership after Session.get")
    for item in candidates:
        print("REVIEW", item)
    return 1 if args.strict and direct_gets else 0


if __name__ == "__main__":
    raise SystemExit(main())
