#!/usr/bin/env python3
"""Build a reviewed, immutable Graduation Gold candidate inventory.

This script never promotes or rewrites the frozen manifest. It records complete,
partial, changed, and missing candidates so a capture failure cannot masquerade
as a successful baseline update.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    e2e = root / "e2e"
    manifest_path = e2e / "gold" / "graduation-v9-gold-manifest.json"
    output = e2e / "gold-candidate"
    output.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    missing: list[str] = []

    for baseline in manifest["baselines"]:
        candidate = e2e / "specs" / f"{baseline['spec']}-snapshots" / baseline["frozenFile"]
        exists = candidate.is_file()
        candidate_sha = digest(candidate) if exists else None
        logical_name = str(baseline["logicalName"])
        if not exists:
            missing.append(logical_name)
        rows.append(
            {
                "card": baseline["card"],
                "spec": baseline["spec"],
                "logicalName": logical_name,
                "frozenFile": baseline["frozenFile"],
                "baselineSha256": baseline["sha256"],
                "candidateSha256": candidate_sha,
                "changed": bool(exists and candidate_sha != baseline["sha256"]),
                "missing": not exists,
                "path": str(candidate.relative_to(root)),
            }
        )

    expected = int(manifest["baselineCount"])
    complete = len(rows) == expected and not missing
    payload = {
        "schemaVersion": 2,
        "head": args.head,
        "runId": os.environ.get("GITHUB_RUN_ID", "local"),
        "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "policy": "candidate-only-no-auto-promotion",
        "expectedCount": expected,
        "observedCount": len(rows) - len(missing),
        "complete": complete,
        "missing": missing,
        "changed": [row["logicalName"] for row in rows if row["changed"]],
        "baselines": rows,
    }
    (output / "candidate-inventory.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "sha256sum.txt").write_text(
        "".join(
            f"{row['candidateSha256']}  {row['path']}\n"
            for row in rows
            if row["candidateSha256"]
        ),
        encoding="utf-8",
    )
    (output / "provenance.txt").write_text(
        "\n".join(
            [
                f"head={args.head}",
                f"runId={os.environ.get('GITHUB_RUN_ID', 'local')}",
                f"runAttempt={os.environ.get('GITHUB_RUN_ATTEMPT', '1')}",
                "policy=no-auto-promotion",
                f"complete={str(complete).lower()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"complete": complete, "missing": missing, "changed": payload["changed"]}, ensure_ascii=False))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
