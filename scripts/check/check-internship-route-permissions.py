from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTER_ROOT = ROOT / "backend/app/modules/internship/routers"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _module_constants(tree: ast.Module) -> dict[str, str]:
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[node.target.id] = node.value.value
    return values


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _resolve_code(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _permission_codes(node: ast.AST, constants: dict[str, str]) -> list[str]:
    """Return permission codes found under Depends(require_*permission(...))."""
    found: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or _call_name(child.func).split(".")[-1] != "Depends":
            continue
        if not child.args or not isinstance(child.args[0], ast.Call):
            continue
        factory = child.args[0]
        name = _call_name(factory.func).split(".")[-1]
        if name not in {"require_permission", "require_any_permission"}:
            continue
        for arg in factory.args:
            code = _resolve_code(arg, constants)
            if code:
                found.append(code)
    return sorted(set(found))


def _route_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef):
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        method = decorator.func.attr.lower()
        if method not in HTTP_METHODS:
            continue
        owner = _call_name(decorator.func.value)
        if owner.split(".")[-1] != "router":
            continue
        path = "<dynamic>"
        if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
            path = decorator.args[0].value
        yield method.upper(), path, decorator


def main() -> None:
    missing: list[str] = []
    invalid: list[str] = []
    route_count = 0
    file_count = 0

    for path in sorted(ROUTER_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        constants = _module_constants(tree)
        file_has_route = False
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for method, route_path, decorator in _route_decorators(node):
                route_count += 1
                file_has_route = True
                # Permission dependency may be declared in the function signature or
                # in the route decorator's dependencies=[...] argument.
                codes = _permission_codes(node.args, constants)
                codes.extend(_permission_codes(decorator, constants))
                codes = sorted(set(codes))
                location = f"{path.relative_to(ROOT)}:{node.lineno} {method} {route_path} ({node.name})"
                if not codes:
                    missing.append(location)
                    continue
                bad = [code for code in codes if not code.startswith("internship.")]
                if bad:
                    invalid.append(f"{location}: non-internship codes={bad}")
        if file_has_route:
            file_count += 1

    if route_count == 0:
        raise SystemExit("ERROR: internship route inventory is empty")
    errors = []
    if missing:
        errors.append("Routes missing declarative require_permission/require_any_permission:\n" + "\n".join(missing))
    if invalid:
        errors.append("Routes with invalid permission namespace:\n" + "\n".join(invalid))
    if errors:
        raise SystemExit("\n\n".join(errors))
    print(f"internship route permission contracts: OK ({route_count} routes across {file_count} files)")


if __name__ == "__main__":
    main()
