# G0 Final-main Re-audit — Collision Ledger

Status: ACTIVE
Generated: 2026-08-15
Last live refresh: after I1/I2 exact-head seal and I4 pre-I3 preflight

## Exact branch truth

- main: `414216c4a79ff035aee87d70b35572572f5c0535`
- E-A01 / PR #128: `a02513cc275ed8ba156d6a52765f21e4a69c9d6d`
- E-A02 / PR #131: `b967ed0cd91203f47856ce15e62c10412210f031`
- E-A03 / PR #129: `3f11c7d7a612d465b0e39d752df5e4d4f3ade6ff`
- Control Plane / PR #133: `b28c5ffa3c8ebcbf5a6cdd6d3ba9617f5c8cdd54`

Live drift is expected. GitHub current truth always wins over this ledger, the handbook snapshot, or an earlier SHA. Re-read the relevant PR HEAD before every shared-writer decision.

## Collision classification

### YELLOW_A01_LOCK

Do not write until A01 explicitly completes A01-13 and releases the current shared-writer batch:

- `backend/app/api/v1/route_registration.py`
- `backend/alembic/versions/**`
- `backend/app/models/__init__.py`

A01 PR #128 remains Draft and its checklist still shows `A01-13 MySQL 并发 / 越权 / 状态机 targeted seal` unchecked. Its latest `a02513cc` is an enterprise route-auth policy test commit; that does **not** constitute a writer-release signal. Therefore S0-06, B1 schema completion, B5 normalized/published RoleTemplate schema, I3 normalized staging and other Control Plane migrations remain blocked.

The release condition is explicit A01-13 seal / writer release, not elapsed time and not “latest commit did not happen to touch Alembic”.

### RED_E_DOMAIN

Read/inspect/consume contracts only:

- `backend/app/modules/internship/**`
- `backend/app/models/internship_*`
- `enterprise-portal/**`
- E recruitment/selection files in `student-portal/**`
- E selection files in `miniapp/**`

### GREEN / CONTROL_PLANE_OWNER

Safe to progress independently when construction order permits:

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

## Locked construction order after I1/I2

A01 writer release first, then:

`S0-06 → B1/B5 schema migration → I3 → other Control Plane migrations → I4 full 20K Production Gate → B8 → E×IAM Gold → Final Gold`

B8 must not be implemented early merely because its files are GREEN. Its frozen order is:

`SYSTEM shadow → zero unexplained drift → PR #104 20K role topology → school full E2E → explicit SCHOOL_ADMIN TENANT permission snapshot → retire wildcard`

## G0 fact map

### Role / RolePermission

- `t_role`, `t_permission`, `t_user_role`, `t_role_permission` exist in `backend/app/models/rbac.py`.
- CUSTOM role runtime permission resolution reads `Role -> RolePermission -> Permission` when `activeContextId=role:<id>`.
- Built-in SYSTEM roles still fall back to `ROLE_PERMISSIONS` in `backend/app/core/permissions.py`.
- `SCHOOL_ADMIN` still has `{"*"}` and must not be retired before B8 shadow reconciliation.

### RoleTemplate / CustomRoleSource

- Governance tables exist in `backend/app/models/permission_governance.py`.
- B5 non-migration work enforces DRAFT mutability, immutable PUBLISHED versions, diff/impact and rollback-as-new-version semantics on the current authority surface.
- CUSTOM school roles remain pinned rather than silently following template upgrades.
- Normalized RoleTemplate permission relations / final published-template schema remain YELLOW because they require the shared Alembic writer.
- B8 SYSTEM shadow therefore remains sequenced after B5 schema migration; do not invent a half-resolver against an unfinished publish schema.

### SecurityChange

- B1 non-migration work materializes ACTIVATE/ROLLBACK into `RolePermission` and keeps critical audit in the mutation transaction.
- Runtime Role / Permission catalog drift fail-closes instead of creating global permissions from a school request.
- Additional schema normalization remains YELLOW until A01 releases Alembic.

### Platform boundary / PAM

- `/api/v1/platform/*` has a Platform Principal outer gate before permission matching.
- School `SCHOOL_ADMIN="*"` cannot cross the principal plane into Platform APIs.
- B2 includes runtime Platform context, recent-auth / ACR / AMR assurance, critical PAM audit, Support Scope catalog, scoped Support Session enforcement, explicit termination and Access Review close/revoke behavior without adding schema.

### Permission Catalog

- `shared/contracts/permission-catalog.json` is the Control Plane authority.
- E-series recruitment and enterprise permission language is registered under `moduleKey=internship`.
- `USED_UNDEFINED=CI RED` remains enforced; UI action keys are not promoted into RBAC permissions.
- Legacy wildcard/naming patterns are B8 debt, not silently accepted as final catalog truth.

### EffectiveAccess

- Shared EffectiveAccess distinguishes principal plane, permission digest/version, security revision, module entitlement health and explainable denial reasons.
- Module-authority failure is now non-cacheable: `moduleAccessHealthy=false → cacheable=false + ctxKey=null`, even when security revision itself is healthy.
- School context preserves `moduleEntitlements=None` when entitlement calculation is unhealthy.
- E enterprise Domain Guard remains owned by A01; Control Plane consumes server facts and never re-implements EnterpriseMember / AccessGrant / CampaignEnterprise / company-resource/state-machine authority.

### Identity Import

- I1/I2 canonical upload first reserves a durable `FileUploadSession` request identity, then stores the sensitive FileObject and registers one SCANNING ImportJob.
- Same request key replays to the same FileObject/ImportJob, including after adapter ref changes to the final identity batch.
- GET remains pure read; parsing is an explicit process/retry command.
- Legacy student/teacher URLs are thin adapters; obsolete mixed direct parser remains HTTP 410.
- Exact-head `367f2f72` Data Exchange MySQL gate is sealed: single Alembic head + upgrade, compile, 23 authoritative tests, PC lint/build and negative confirmation/RBAC contracts all success.
- 20K single-job import Gold remains `BLOCKED_BY_I3`; no normalized staging migration means no false 20K claim.

### I4 pre-I3

- Role-member and role-audit resources are DB paged with bounded `pageSize`.
- Control Plane Targeted at exact head `b28c5ffa` executes I4 preflight and is success.
- The preflight explicitly freezes `currentSingleJobGold=false` and `I3_NORMALIZED_STAGING_MIGRATION` as the blocker.
- Dynamic EffectiveAccess unit coverage is part of change-sensitive backend pytest; queued/running is not counted as success until GitHub reports success.

### B8 readiness only — no runtime switch yet

The authority handbook freezes four separate resolver planes:

1. OLD built-in `ROLE_PERMISSIONS`
2. NEW published TENANT RoleTemplate
3. CUSTOM `RolePermission`
4. PLATFORM Workforce resolver

Shadow compares TENANT SYSTEM roles only. CUSTOM must not fall back to templates; PLATFORM must not enter school RoleTemplate. `ALLOW/DENY` disagreement in either direction must be explainable before any wildcard retirement.

Current `permission_bundle_service` already inventories and expands wildcard debt and `WildcardRetirement` exists, but existing tests intentionally assert that governance writes do not yet alter real authz. Therefore runtime SYSTEM shadow is genuinely not implemented and must wait for the published RoleTemplate schema + full I4 sequence.

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

Sealed evidence already obtained:

- I1/I2 exact-head `367f2f72`: Data Exchange MySQL Authority gate — GREEN
- I4 pre-I3 exact-head `b28c5ffa`: Control Plane Targeted including I4 preflight — GREEN
- S0 byte-identical Move gate — GREEN
- G0 inventory — GREEN
- Permission Catalog reconciliation — GREEN
- File capability inventory strict baseline — previously GREEN on the Control Plane line

At `b28c5ffa`, queued/pending/in-progress GitHub jobs remain **not proven** until they complete. Do not promote pre-I3 I4 to full 20K Gold before I3 exists and the real XLSX + scan + worker + MySQL + receipt gate passes.

G0 code-writing boundary remains respected: the Control Plane branch has not taken any of A01's three locked writer classes.
