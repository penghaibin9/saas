# G0 Final-main Re-audit — Collision Ledger

Status: ACTIVE
Generated: 2026-08-15

## Exact branch truth

- main: `414216c4a79ff035aee87d70b35572572f5c0535`
- E-A01 / PR #128: `69dab96f035b201406b42c5544d8b5d5800ed3c7`
- E-A02 / PR #131: `66ef48bdb6aeebe3c30e69c7ccae6c64fd53c24d`
- E-A03 / PR #129: `1b376ac7d3fe0769ed3f19e0f2afc0659bfd7ca0`

Important drift from the handbook snapshot: E-A03 advanced from `7e30a645...` to `1b376ac7...`. Current GitHub truth wins.

## Collision classification

### YELLOW_A01_LOCK

Do not write until A01 releases the current writer batch:
- `backend/app/api/v1/route_registration.py`
- `backend/alembic/versions/**`
- `backend/app/models/__init__.py`

PR #128 currently changes all three, plus E-series model/module/test files and four internship E migrations.

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
- `backend/app/core/permissions.py`
- `backend/app/models/rbac.py`
- `backend/app/models/permission_governance.py`
- `backend/app/services/audit_log.py`
- `shared/contracts/permission-catalog.json`
- `shared/contracts/module-manifest.json`
- `frontend/src/modules/system/**`
- `frontend/src/modules/platform/**`
- system/platform route inventory and move-only compatibility work that does not touch `route_registration.py`

## G0 fact map

### Role / RolePermission

- `t_role`, `t_permission`, `t_user_role`, `t_role_permission` exist in `backend/app/models/rbac.py`.
- CUSTOM role runtime permission resolution already reads `Role -> RolePermission -> Permission` when `activeContextId=role:<id>`.
- Built-in SYSTEM roles still fall back to `ROLE_PERMISSIONS` in `backend/app/core/permissions.py`.
- `SCHOOL_ADMIN` still has `{"*"}` and must not be retired before B8 shadow reconciliation.

### RoleTemplate / CustomRoleSource

- Governance tables exist in `backend/app/models/permission_governance.py`.
- `RoleTemplate` is currently governance/delivery metadata, not the single runtime permission truth.
- `CustomRoleSource` stores permission JSON and is not yet normalized 1:1 to runtime `RolePermission` materialization.

### SecurityChange

- `security_change_service.transition()` row-locks the change and requires `expected_version`.
- ACTIVATE/ROLLBACK currently mutate `CustomRoleSource.permission_codes_json`; they do not materialize `RolePermission`.
- Critical audit is executed after `db.commit()` through a best-effort `_audit()` that swallows failures. B1 must make activation/rollback mutation + critical audit atomic.

### Platform boundary / PAM

- `backend/app/api/v1/platform.py` has a local `require_platform_super_admin()` role gate, but the platform identity plane is not yet a shared outer-gate contract for every `/platform/*` endpoint.
- `platform_access_governance_service.py` separates `PLATFORM_*` duties from school roles and fail-closes school identities.
- `assert_support_session()` exists, but current code search finds no production endpoint call site outside its definition; Support Session is therefore SHADOW / NOT RUNTIME.
- Duty/JIT/Support `save_record()` commits before route-level audit, so critical PAM audit is not atomic.

### EffectiveAccess

- `get_effective_access_context()` already distinguishes module entitlement calculation failure with `moduleEntitlements=None`, `moduleAccessHealthy=false`.
- Adapters must preserve this distinction and must not coerce `None` to `[]`.

### Identity Import

- Legacy `/system/identity-import/*validate-file` and `*confirm-batch` paths remain a separate risk surface to inventory and later adapt to the canonical Data Exchange/FileObject scan chain.
- 20K import proof is not established by the existing 20K sandbox/data-volume proof.

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

## G0 unresolved machine checks

The branch carries a targeted scanner to make these machine-verifiable before G0 seal:
- static Alembic single-head calculation
- system/platform route snapshots
- `/platform` mutation inventory
- permission usage / creator inventory
- E permission catalog presence once B3 lands

G0 code-writing boundary is respected: this ledger changes no runtime behavior and touches none of A01's locked files.
