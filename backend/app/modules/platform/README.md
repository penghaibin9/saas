# Platform Control Plane module

This package is the backend owner for `/api/v1/platform/*` control-plane code.

Current migration rule:

- Start with Move Only router ownership changes.
- Keep `backend/app/api/v1/platform.py` as the compatibility facade until route contracts are frozen and migrated.
- Do not change URL, HTTP method, dependency semantics, response contracts, state machines, SQL behavior, audit semantics, or tenant boundaries in a Move Only commit.
- Shared IAM primitives remain under the shared kernel (`app/core`, shared models/contracts); do not fork a second permission system here.
- Do not touch PR #101 academic-affairs ownership, PR #104 sandbox reset ownership, or PR #105 graduation canonical logic from this package.

Target subpackages:

- `routers/` — platform-only HTTP ownership
- `services/` — platform-only application services after router ownership is stable
- `schemas/` — platform request/response contracts
- `policies/` — platform principal, permission, JIT/support access policies
