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
- No lifecycle hook was added during C0/C1. Same-session hooks wait for the fact table/model and the
  A+B+C migration slot; backfill stays outside Alembic.
