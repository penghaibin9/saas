"""Replay the production school-IAM Control Plane Authority after schema migration."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Keep this bootstrap executable directly as `python scripts/...` from backend/, which
# is how several isolated real-browser gates invoke it. Do not rely on caller-specific
# PYTHONPATH; only add the repository backend root that contains the `app` package.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.school_iam_authority_service import converge_school_iam_authority


def main() -> None:
    head_sha = str(
        os.environ.get("SCHOOL_IAM_AUTHORITY_EXPECTED_SHA")
        or os.environ.get("SCHOOL_ADMIN_CUTOVER_EXPECTED_SHA")
        or os.environ.get("GITHUB_SHA")
        or ""
    ).strip()
    if len(head_sha) < 7:
        raise RuntimeError("SCHOOL_IAM_AUTHORITY_EXPECTED_SHA/GITHUB_SHA is required")

    result = converge_school_iam_authority(
        source="CONTROL_PLANE_SCHOOL_IAM_AUTHORITY_BOOTSTRAP",
        source_commit_sha=head_sha,
        actor_user_id=None,
    )
    if not result.get("converged") or not result.get("shadow", {}).get("zeroUnexplainedDrift"):
        raise RuntimeError(f"school IAM Authority did not converge: {result}")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
