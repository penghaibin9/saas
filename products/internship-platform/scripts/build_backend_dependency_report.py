#!/usr/bin/env python3
"""Inventory Standalone backend imports before copying shared kernel code."""
from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "app"
OUT = ROOT / "artifacts" / "backend-dependencies.json"

module_files: dict[str, set[str]] = defaultdict(set)
model_symbols: dict[str, set[str]] = defaultdict(set)
service_symbols: dict[str, set[str]] = defaultdict(set)

for path in sorted(BACKEND.rglob("*.py")):
    rel = str(path.relative_to(ROOT))
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [(alias.name, None) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [(node.module, [alias.name for alias in node.names])]
        else:
            continue
        for module, symbols in modules:
            if not module.startswith("app."):
                continue
            if module.startswith("app.modules.internship"):
                continue
            module_files[module].add(rel)
            if module == "app.models" and symbols:
                for symbol in symbols:
                    model_symbols[symbol].add(rel)
            if module == "app.services" and symbols:
                for symbol in symbols:
                    service_symbols[symbol].add(rel)

payload = {
    "schemaVersion": 1,
    "modules": [
        {"module": module, "fileCount": len(files), "files": sorted(files)}
        for module, files in sorted(module_files.items(), key=lambda item: (-len(item[1]), item[0]))
    ],
    "appModelsSymbols": [
        {"symbol": symbol, "fileCount": len(files), "files": sorted(files)}
        for symbol, files in sorted(model_symbols.items(), key=lambda item: (-len(item[1]), item[0]))
    ],
    "appServicesSymbols": [
        {"symbol": symbol, "fileCount": len(files), "files": sorted(files)}
        for symbol, files in sorted(service_symbols.items(), key=lambda item: (-len(item[1]), item[0]))
    ],
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "moduleCount": len(payload["modules"]),
    "modelSymbolCount": len(payload["appModelsSymbols"]),
    "serviceSymbolCount": len(payload["appServicesSymbols"]),
}, ensure_ascii=False))
print(f"[dependencies] {OUT}")
