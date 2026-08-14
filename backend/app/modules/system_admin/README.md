# System Admin Control Plane module

This package is the backend owner for school-side `/api/v1/system/*` control-plane code.

Current migration rule:

- Start with Move Only router ownership changes.
- Keep `backend/app/api/v1/system.py` as the compatibility facade until route contracts are frozen and migrated.
- Do not change URL, HTTP method, dependency semantics, response contracts, state machines, SQL behavior, audit semantics, tenant isolation, or data-scope semantics in a Move Only commit.
- Shared IAM primitives remain under the shared kernel (`app/core`, shared models/contracts); do not fork a second permission or role-template system here.
- Do not modify PR #101 academic-affairs canonical code, PR #104 sandbox seed/reset ownership, or PR #105 graduation canonical code from this package.

Target subpackages:

- `routers/` — school system-admin HTTP ownership
- `services/` — system-admin-only application services after router ownership is stable
- `schemas/` — system-admin request/response contracts
- `policies/` — tenant IAM ceilings and system-admin policy helpers
