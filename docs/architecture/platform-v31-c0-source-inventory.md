# PLAT-C C0 source inventory

Base: `eecb4d01d2a9592b71975be07c54f994f08e7461` (`origin/main`, 2026-08-29).

## Git and owner truth

- The attached audit anchor `2fee0d3a` is stale. PR #236 is already merged into the live main.
- Open PR #237 is an `ACTIVE_PRODUCT` repair. Its changed files include one shared hotspot,
  `backend/alembic/versions/20260825_repair_recovery_run.py`, but none of the PLAT-C private
  package paths created in C0/C1.
- PLAT-C migration and shared registration remain stopped. C must first consume an A+B
  integration head whose single Alembic head contains both lineages.

## Exact FileVersion authority

| Concern | Current authority | C0 conclusion |
|---|---|---|
| Version family timeline | `backend/app/services/file_version_service.py` | Business binding family, not exact-version derivation |
| Exact immutable identity | `FileVersion -> FileObject.sha256` | Reuse; do not create a second byte/version authority |
| Logical sensitivity | `FileAsset.sensitivity_level` plus `FileObject.security_level` | Reuse and carry forward |
| Object authorization | `backend/app/services/file_access_service.py::authorize_file_object` | Mandatory source check |
| Domain authorization | `backend/app/services/file_access_resolvers.py` registry | Mandatory; do not add a parallel ACL |
| Historical version relation | `FileBinding.version_id` + `asset_id` | Historical versions may resolve; `is_current` is not required |
| Request source identity | exact `file_version_id` + expected SHA-256 | Implemented by the C1 private port |

The C1 adapter returns bounded business binding references only. It does not return storage keys,
signed URLs, preview tickets, cookies or tokens. `extract`, `compare` and derived-result reads all
re-enter the source preview authorization path.

## Current-truth writer inventory

The production current writers remain outside PLAT-C:

- Graduation: `backend/app/modules/graduation/materials/command_service.py::_append_version`
- Internship: `backend/app/modules/internship/services/internship_material_center_service.py::_adopt_source`
- Student Affairs: `backend/app/modules/student_affairs/services/affairs_material_center_service.py`
- Affairs archive packages: `backend/app/services/affairs_archive_service.py::_register_package_version`
- Legacy/import/backfill writers remain in their existing migration or backfill services.

The PLAT-C private package contains no assignment to `FileVersion.is_current`,
`FileAsset.current_version_id`, `FileBinding.is_current` or a domain material's
`current_version_id`.

## Lifecycle and Student360 truth

- The complete static inventory of all current `StudentStageEvent(...)` construction sites and the
  deliberately small direct-domain candidate list is recorded in
  `docs/architecture/platform-v31-lifecycle-writer-inventory.yaml`.
- `teacher_mobile_student360_projection_service.py` performs scope-first SQL visibility, then one
  row per domain and the last ten `StudentStageEvent` rows.
- Its `sections`, risk summaries and current statuses remain direct-domain reads. PLAT-C may later
  shadow only the timeline and must not switch sections to facts.
- C4 contains five transaction-only hook mappings and rollback/dedupe tests. C7 registered each
  mapping in the canonical mutation's existing session before commit (or inside the caller-owned
  academic transaction). The hooks do not open or commit sessions and no `after_commit` path exists.
- The resumable backfill remains a standalone script outside Alembic. It binds checkpoints to tenant
  and schema version, keyset-scans `StudentStageEvent`, bulk-resolves `StudentProfile`, excludes
  sandbox rows, and reports source/fact post-compare counts.

## C0-C6 private checkpoint evidence

Verified in the independent PLAT-C worktree before any C7 registration:

- 68 PLAT-C backend characterization, security, rollback, visibility, worker and backfill tests pass;
  the suite contains no skip or xfail.
- Staff PC and Student PC production builds pass. Miniapp H5 and Weixin builds pass. The private
  four-client contract tests pass 3/3 and assert one real server contract, exact version/SHA inputs,
  summary-only miniapp output and unchanged Student360 direct-domain sections.
- Reverse falsification closed two additional boundaries: FileJob rejects arbitrary URI/protocol-
  relative values, and parser/compare elapsed-time checks run after expensive parsing/diff work.
- The 2026-08-30 third reverse review reproduced an inheritance defect where an unknown legacy
  sensitivity code could reach a derived FileObject unchanged. The worker now fails closed by
  normalising every unknown source level to `HIGHLY_SENSITIVE` before extraction or comparison.
- A further source-bound falsification reproduced that a forged `DOCUMENT_DERIVATIVE` binding could
  borrow a valid source ACL without proving that its FileObject was the stored output of that exact
  artifact/result. The private C7 resolver candidate now requires tenant, result identity, generated
  FileObject id and all pinned source identities to match a `SUCCEEDED` persisted row before ACL.
- Derived-body reads now also verify the embedded artifact contract, extractor/algorithm version and
  single/both source version+SHA identities against the persisted result row. Replacing a body and its
  digest together can no longer return content from a different authorized or unauthorized source.
- Lifecycle reads independently fail closed for legacy/unknown sensitivity values. Student summaries
  are masked for sensitive or unknown facts, and scoped staff receive sensitive summaries only with
  the explicit sensitive-view permission, even if a historical row has an overly broad visibility.
- FileJob failure persistence was reverse-tested with an exception containing a temporary URL and
  access token. Retry/failure rows now retain only a bounded sanitized error code, while worker lock
  owners are stored as one-way hashes; neither path can persist credentials, tickets or raw URLs.
- The credential guard also runs inside the sole `persist_job_spec` boundary, so an internal caller
  cannot bypass request preparation and directly store a credential-bearing `DerivedJobSpec`.
- The mandatory C7 order lock is executable C-private tooling. It consumes only B's future exact
  `PLAT_B_INTEGRATION_HEAD` and `PLAT_B_ALEMBIC_HEAD`, proves the integration commit is an ancestor of
  current C HEAD and requires that B revision to be the single live Alembic head; every missing,
  stale, sibling or unconsumed condition exits with `C_ORDER_LOCK=STOP` before migration work.
- A canonical academic status smoke path passed after the premature fact hook was removed. A later
  full canonical fixture rebuild stopped before PLAT-C execution because the baseline MySQL fixture
  could not recreate `t_role_template` (1146); this is preserved as a real same-head gate blocker,
  not skipped or relabelled.

C7 consumed B's emitted exact integration head
`3439f5d04598b5c8199c8452c0929ba94b09f754`. That commit includes A head
`342a73782ee9c12be4e0951f123bfe304dba93c0`, resolves the single B Alembic head
`20260830_plat_b_forms`, and is an ancestor of
the PLAT-C integration commit. C then registered revision `20260830_plat_c_lifecycle` with B as its
`down_revision`, the three shared ORM models, the router, the source-bound derivative resolver, the
five same-session canonical hooks, and Student360 timeline shadow metrics. Student360 `sections` and
the returned legacy `timeline` remain direct-domain/`StudentStageEvent` truth; backfill remains the
standalone resumable script under `backend/scripts/`.
