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
- C4 now contains five private, transaction-only hook mappings and rollback/dedupe tests. They do
  not open or commit sessions. Their canonical call sites remain deliberately unmodified until C7,
  because the current single Alembic head does not contain `t_student_lifecycle_fact`; wiring them
  earlier was reverse-tested against `test_aa_status_change.py` and correctly identified as a real
  1146 regression. C7 must add each call immediately before the existing canonical commit (or inside
  the caller-owned academic transaction), never through `after_commit`.
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

C7 remains blocked at the 2026-08-30 B-session pre-read checkpoint: `origin/main` is
`eecb4d01d2a9592b71975be07c54f994f08e7461`; the active B private ref has advanced through
`18aedb8e34bb063ab50403697a632f962cec9c7e` to
`7d34c69a39b047bcda0b6e817db078b4a35495b5`, still without a B migration or emitted
`PLAT_B_INTEGRATION_HEAD`/`PLAT_B_ALEMBIC_HEAD`. A and B private refs remain divergent, no local or
remote ref/marker proves an A+B integration head, and the PLAT-C worktree still resolves only the main Alembic head
`20260829_pr236_main_merge`. Therefore no PLAT-C migration, model/base import, shared router/resolver,
canonical fact-hook or Student360 shadow registration is present at C0-C6.
