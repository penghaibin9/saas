"""CI bootstrap for graduation E2E identities.

The identity-import API may intentionally omit initial passwords from its JSON response.
This wrapper verifies that organization creation and the official account import succeed,
then leaves password normalization to e2e_reset_graduation_passwords.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.e2e_bootstrap_graduation_accounts import (  # noqa: E402
    ensure_org,
    import_accounts,
    login,
)


def main() -> int:
    token = login()
    org = ensure_org(token)
    print("org:", json.dumps(org, ensure_ascii=False))

    imported = import_accounts(token)
    if not imported.get("confirmed"):
        raise SystemExit(
            "graduation identity import was not confirmed: "
            + json.dumps(imported.get("detail"), ensure_ascii=False)
        )
    print(
        "[e2e-bootstrap] identity import confirmed:",
        imported.get("batchNo"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
