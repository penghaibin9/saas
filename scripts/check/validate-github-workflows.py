"""Parse every GitHub Actions workflow so invalid YAML cannot silently poison all branch checks."""
from __future__ import annotations

from pathlib import Path

import yaml


def main() -> None:
    workflows = sorted(Path(".github/workflows").glob("*.yml"))
    workflows += sorted(Path(".github/workflows").glob("*.yaml"))
    if not workflows:
        raise SystemExit("no GitHub Actions workflows found")

    failed = False
    for workflow in workflows:
        try:
            yaml.safe_load(workflow.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            failed = True
            print(f"ERROR {workflow}: {exc}")
        else:
            print(f"OK {workflow}")

    if failed:
        raise SystemExit("invalid GitHub Actions workflow YAML")


if __name__ == "__main__":
    main()
