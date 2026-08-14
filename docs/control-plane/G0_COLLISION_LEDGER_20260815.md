# G0 Final-main Re-audit — Collision Ledger

Status: ACTIVE
Generated: 2026-08-15
Last live refresh: 2026-08-15 07:32 +08:00

## Exact branch truth

- main: `414216c4a79ff035aee87d70b35572572f5c0535`
- E-A01 / PR #128: `6089e92377ae9bc374a4c5c67f31ee2581bc2005`
- E-A02 / PR #131: `d64311b4d085d52f77aed5e4f2849e0ca78502d0`
- E-A03 / PR #129: `8f10b2c4baa60e37ec0a5ead5a523c9e9f5b875e`
- Control Plane / PR #133: `6852e4e3484097c7094e945856a9f0f6cd7965cc`

Live drift since the first G0 snapshot is expected and is re-read before every shared-writer decision. Current GitHub truth always wins over the handbook snapshot or an earlier ledger line.

Latest A01 movement is still a shared-writer change: `6089e923` modifies `backend/alembic/versions/20260815_internship_e_position_campaign.py` to replace a placeholder with the canonical position/campaign migration. Therefore the Alembic writer is **not released**. A02's latest change is an enterprise-portal auth-session lifecycle test; A03's latest change is student-selection fail-closed campaign-context work. Neither changes the Control Plane ownership decision.

## Collision classification

### YELLOW_A01_LOCK

Do not write until A01 releases the current writer batch:
- `backend/app/api/v1/route_registration.py`
- `backend/alembic/versions/**`
- `backend/app/models/__init__.py`

A01 has advanced from the original G0 head and is still actively writing Alembic at `6089e923`; S0-06, B1 schema migration, B5 normalized RoleTemplate relation migration, I3 staging migration and other Control Plane migrations remain blocked. A01 release is a writer-release condition, not a requirement to wait for the whole E series.

### RED_E_DOMAIN

Read/inspect/consume contracts only:
- `backend/app/modules/internship/**`
- `backend/app/models/internship_*`
- `enterprise-portal/**`
- E recruitment/selection files in `student-portal/**`
- E selection files in `miniapp/**`

### GREEN / CONTROL_PLANE_OWNER

Safe to progress independently:
- `backend/app/modules/system_admin/**`
- `backend/app/modules/platform/**`
- Control Plane adapters under `backend/app/core/**` that do not take over E domain guards
- Role / RolePermission command boundaries outside blocked schema writers
- `backend/app/services/audit_log.py`
- `shared/contracts/permission-catalog.json`
- Control Plane contracts under `shared/contracts/control-plane/**`
- `frontend/src/modules/system/**`
- `frontend/src/modules/platform/**`
- system/platform route inventory and move-only compatibility work that does not touch `route_registration.py`

## G0 fact map

### Role / RolePermission

- `t_role`, `t_permission`, `t_user_role`, `t_role_permission` exist in `backend/app/models/rbac.py`.
- CUSTOM role runtime permission resolution reads `Role -> RolePermission -> Permission` when `activeContextId=role:<id>`.
- Built-in SYSTEM roles still fall back to `ROLE_PERMISSIONS` in `backend/app/core/permissions.py`.
- `SCHOOL_ADMIN` still has `{"*"}` and must not be retired before B8 shadow reconciliation.

### RoleTemplate / CustomRoleSource

- Governance tables exist in `backend/app/models/permission_governance.py`.
- Control Plane B5 non-migration work now enforces DRAFT mutability, immutable PUBLISHED versions, diff/impact and rollback-as-new-version semantics on the existing table.
- CUSTOM school roles remain pinned rather than silently following template upgrades.
- Normalized RoleTemplate permission relations are still YELLOW because they require Alembic.

### SecurityChange

- B1 non-migration work now materializes ACTIVATE/ROLLBACK into `RolePermission` and keeps critical audit in the mutation transaction.
- Runtime Role / Permission catalog drift fail-closes instead of creating global permissions from a school request.
- Additional schema normalization remains YELLOW until A01 releases Alembic.

### Platform boundary / PAM

- `/api/v1/platform/*` now has a shared Platform Principal outer gate before permission matching.
- School `SCHOOL_ADMIN="*"` cannot cross the principal plane into Platform APIs.
- B2 adds runtime Platform context, recent-auth / ACR / AMR assurance, critical PAM audit, Support Scope catalog, scoped Support Session enforcement, explicit termination and Access Review close/revoke behavior without adding schema.
- Normalized PAM schema, if required by the final design, remains a migration card after writer release.

### Permission Catalog

- `shared/contracts/permission-catalog.json` is the Control Plane authority.
- E-series recruitment and enterprise permissions are registered under `moduleKey=internship`.
- `USED_UNDEFINED=CI RED` remains enforced; UI action keys are not promoted into RBAC permissions.
- Legacy wildcard/naming patterns are explicitly tracked as B8 debt instead of silently accepted as exact catalog truth.
- Exact-head Control Plane Targeted reconciliation is green.

### EffectiveAccess

- Shared EffectiveAccess contract now distinguishes principal plane, permission digest/version, security revision, module entitlement health and explainable denial reasons.
- School context preserves `moduleEntitlements=None` when entitlement calculation is unhealthy; it is not coerced to an empty purchased-module list.
- E enterprise Domain Guard remains owned by A01; Control Plane consumes server facts and never re-implements EnterpriseMember / AccessGrant / CampaignEnterprise / company-resource/state-machine authority.

### Identity Import

- I1/I2 runtime composition now makes Data Exchange upload register `SCANNING`, GET pure-read, and parsing an explicit process/retry command.
- Legacy student/teacher URLs are thin adapters into canonical Data Exchange; obsolete mixed direct parser returns HTTP 410.
- The S0 byte-frozen source still contains the historical direct-parser code for move-only evidence; file-capability inventory records it as `legacy` and `scanGated=false` rather than hiding the source risk.
- Exact-head Data Exchange MySQL/Alembic/pytest/frontend/negative-contract gate is green.
- 20K single-job import Gold remains `BLOCKED_BY_I3`; no staging migration means no false 20K claim.

## E-series IAM inputs that Control Plane owns

TENANT:
- `internship.recruitment.view`
- `internship.recruitment.manage`
- `internship.recruitment.invite`
- `internship.recruitment.close`

ENTERPRISE permission language in the shared catalog:
- `enterprise.internship.company.view`
- `enterprise.internship.company.edit`
- `enterprise.internship.position.view`
- `enterprise.internship.position.manage`
- `enterprise.internship.position.submit`
- `enterprise.internship.application.view`
- `enterprise.internship.application.decide`
- `enterprise.internship.student.view`
- `enterprise.internship.eval.submit`

Enterprise allow = permission AND active EnterpriseMember AND active/unexpired AccessGrant AND valid CampaignEnterprise AND company/resource ownership AND tenant/campaign scope AND domain state machine.

## Current machine evidence

At Control Plane exact head `6852e4e3`:
- S0 byte-identical Move gate: GREEN
- G0 inventory artifact: GREEN
- Permission Catalog reconciliation: GREEN
- File capability inventory schema: GREEN
- File capability strict existing baseline: GREEN
- Changed production file-capability registration: GREEN

The branch carries targeted scanners/contracts for:
- static Alembic inventory without writing the migration tree
- system/platform route snapshots
- `/platform` mutation inventory
- permission usage / creator inventory
- E permission catalog presence
- critical mutation policy
- I4 20K preflight state

G0 code-writing boundary remains respected: the Control Plane branch still touches none of A01's three locked writer classes.
