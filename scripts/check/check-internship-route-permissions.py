from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTER_ROOT = ROOT / "backend/app/modules/internship/routers"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
PUBLIC_AUTH_METADATA_KEY = "x-internship-auth"
PUBLIC_AUTH_METADATA_VALUE = "public"


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


def _factory_permission_codes(factory: ast.Call, constants: dict[str, str]) -> list[str]:
    name = _call_name(factory.func).split(".")[-1]
    if name not in {"require_permission", "require_any_permission"}:
        return []
    found = []
    for arg in factory.args:
        code = _resolve_code(arg, constants)
        if code:
            found.append(code)
    return sorted(set(found))


def _module_permission_aliases(tree: ast.Module, constants: dict[str, str]) -> dict[str, list[str]]:
    """Resolve `_VIEW = require_any_permission(...)` style declarative aliases."""
    aliases: dict[str, list[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Call):
            continue
        codes = _factory_permission_codes(node.value, constants)
        if codes:
            aliases[target.id] = codes
    return aliases


def _permission_codes(
    node: ast.AST,
    constants: dict[str, str],
    aliases: dict[str, list[str]],
) -> list[str]:
    """Return permission codes found under Depends(require_*permission(...)) or its module alias."""
    found: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or _call_name(child.func).split(".")[-1] != "Depends":
            continue
        if not child.args:
            continue
        dependency = child.args[0]
        if isinstance(dependency, ast.Call):
            found.extend(_factory_permission_codes(dependency, constants))
        elif isinstance(dependency, ast.Name):
            found.extend(aliases.get(dependency.id, []))
    return sorted(set(found))


def _explicit_public_auth(decorator: ast.Call) -> bool:
    """Require a literal OpenAPI marker instead of maintaining a hidden path allowlist."""
    for keyword in decorator.keywords:
        if keyword.arg != "openapi_extra" or not isinstance(keyword.value, ast.Dict):
            continue
        for key, value in zip(keyword.value.keys, keyword.value.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == PUBLIC_AUTH_METADATA_KEY
                and isinstance(value, ast.Constant)
                and value.value == PUBLIC_AUTH_METADATA_VALUE
            ):
                return True
    return False


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
    public_auth_count = 0
    file_count = 0

    for path in sorted(ROUTER_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        constants = _module_constants(tree)
        aliases = _module_permission_aliases(tree, constants)
        file_has_route = False
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for method, route_path, decorator in _route_decorators(node):
                route_count += 1
                file_has_route = True
                # Permission dependency may be declared in the function signature or
                # in the route decorator's dependencies=[...] argument.
                codes = _permission_codes(node.args, constants, aliases)
                codes.extend(_permission_codes(decorator, constants, aliases))
                codes = sorted(set(codes))
                location = f"{path.relative_to(ROOT)}:{node.lineno} {method} {route_path} ({node.name})"
                public_auth = _explicit_public_auth(decorator)
                if public_auth:
                    # Public is valid only for a deliberately marked authentication surface; this
                    # prevents the marker becoming a general permission bypass.
                    if not route_path.startswith("/auth/"):
                        invalid.append(f"{location}: public auth marker outside /auth/")
                    if codes:
                        invalid.append(f"{location}: route cannot be both public and permission-gated")
                    public_auth_count += 1
                    continue
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
        errors.append("Routes with invalid permission namespace/policy:\n" + "\n".join(invalid))
    if errors:
        raise SystemExit("\n\n".join(errors))
    print(
        f"internship route permission contracts: OK "
        f"({route_count} routes across {file_count} files; {public_auth_count} explicit public auth routes)"
    )


if __name__ == "__main__":
    main()
