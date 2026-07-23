"""Verify E2E accounts from saved credential receipt (no re-import)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.e2e_bootstrap_graduation_accounts import CRED_PATH, verify_logins  # noqa: E402

def main() -> int:
    if not CRED_PATH.exists():
        print("missing credentials file", CRED_PATH)
        return 1
    receipt = json.loads(CRED_PATH.read_text(encoding="utf-8"))
    # If already rewritten to passwords map, wrap it
    if "passwords" in receipt and "credentialReceipt" not in receipt:
        # synthesize minimal receipt for extractor by converting passwords to fake rows via direct map
        results = []
        from scripts.e2e_bootstrap_graduation_accounts import _req, TENANT, ADMIN
        pwd_map = dict(receipt["passwords"])
        pwd_map.setdefault("admin2", ADMIN[1])
        for ln, pwd in pwd_map.items():
            r = _req("POST", "/auth/login", body={
                "loginName": ln, "password": pwd, "tenantCode": TENANT,
            })
            ok = r.get("code") == 0
            role = ((r.get("data") or {}).get("currentRole") or {}).get("roleCode") if ok else None
            results.append({"loginName": ln, "ok": ok, "role": role, "message": None if ok else r.get("message")})
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if all(x["ok"] for x in results if x["loginName"] != "e2e_sysadmin") else 1
    results = verify_logins(receipt)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    ok = sum(1 for x in results if x.get("ok"))
    print(f"ok={ok}/{len(results)}")
    return 0 if ok >= 10 else 1

if __name__ == "__main__":
    raise SystemExit(main())
