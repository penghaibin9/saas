# Control Plane Option B — Locked Construction Order

Branch: `integration/control-plane-option-b-20260815`
Base: `main@414216c4a79ff035aee87d70b35572572f5c0535`
Authority document: `SaaS_系统管理与平台主管理_生产级交叉复审校正版_方案B唯一施工总册_2026-08-15_E系列三线并行开工版.md`

## Loop engineering order

1. G0 — Final-main Re-audit
2. S0-01..S0-05 — Control Plane Move Only
3. B0 — Security Boundary
4. B1 — Canonical Role, non-migration work first
5. B2 — Platform Workforce / PAM
6. B3 — Authoritative Permission Catalog
7. B4 — EffectiveAccess
8. B5 — RoleTemplate, non-migration work first
9. B6 — Platform Product IAM
10. B7 — School IAM Workspace
11. I1 / I2 — Identity Import, no-new-schema work first
12. Revisit YELLOW cards only after E-A01 releases shared writers:
    - S0-06 route registration cleanup
    - B1 schema migration
    - B5 normalized template relation migration
    - I3 staging migration
    - other Control Plane migrations
13. I4 — 20K Production Gate
14. B8 — SYSTEM Shadow + Wildcard Retirement
15. E × IAM Joint Gold
16. Control Plane Final Gold

## Temporary writer locks

YELLOW / E-A01 temporary writer:
- `backend/app/api/v1/route_registration.py`
- `backend/alembic/versions/**`
- `backend/app/models/__init__.py`

RED / read-only from this branch:
- `backend/app/modules/internship/**` E-series authority
- `backend/app/models/internship_*`
- `enterprise-portal/**`
- student E-selection surfaces in `student-portal/**`
- E-selection surfaces in `miniapp/**`

CONTROL_PLANE_OWNER:
- Shared IAM Kernel
- Role / RolePermission / RoleTemplate / SecurityChange / EffectiveAccess
- `shared/contracts/permission-catalog.json`
- `backend/app/modules/system_admin/**`
- `backend/app/modules/platform/**`
- `frontend/src/modules/system/**`
- `frontend/src/modules/platform/**`

## Hard discipline

- One Control Plane integration truth; do not revive PR #112/#113 as parallel IAM roots.
- No force push.
- Targeted first; MySQL authoritative; exact-head only at phase seal.
- No skip/xfail/assertion weakening/known-failure expansion/fake audit/fake scan.
- A YELLOW collision stops only that card, never the whole branch.
- `moduleKey=internship`; do not create a second recruitment top-level product.
- `enterprise.internship.*` belongs to the canonical Permission Catalog but never replaces EnterpriseMember + AccessGrant + CampaignEnterprise + ownership/scope/state guards.
