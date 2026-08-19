# C-C1 Attendance Consumer Contract — FROZEN

> C line: `agent/academic-c-teaching-execution`  
> PR: #148  
> Freeze evidence HEAD: `3288e10907106d17d9dec64dc2a185b90a503bd5`  
> Evidence run: `Academic C W0 Mature Chain Freeze #102 / 31951673555` — `success`  
> Scope: Attendance consumes existing B-C1 Published Schedule + TeachingRoster truth. C does not create schedule authority.

## 1. Canonical formal occurrence

Ordinary classroom attendance resolves one and only one current occurrence through:

`current term → existing SCHOOL/0 + COLLEGE/x ScopeHead → active PUBLISHED batch → TeachingTask-based EFFECTIVE ScheduleItem → calendar logical date → week/weekday/slot/parity → APPLIED schedule change → task/teacher/class/course identity → versioned TeachingRoster`

The consumer never:

- creates ScopeHead;
- chooses the latest PUBLISHED batch as a substitute for ScopeHead;
- scans historical EFFECTIVE rows outside current active batches;
- uses course name / teacher name / class name / bare date+slot as formal identity;
- turns a stale client schedule item into a new current occurrence silently.

## 2. Calendar contract

- `HOLIDAY`: ordinary classroom attendance is rejected.
- `SWAP` source day: ordinary classroom attendance is rejected.
- `SWAP` target day: actual attendance date remains the target day, while week/weekday/parity are calculated from the original teaching day.
- multiple SWAP targets, HOLIDAY+SWAP target, or other ambiguous calendar facts fail closed.

## 3. Schedule change contract

- historical `CHANGED` item cannot be used for new ordinary attendance.
- changed/new occurrence must be an `EFFECTIVE` item in the current active batch.
- item with `change_id` must resolve to the same-tenant `AaScheduleChange(status=APPLIED)`.
- only `ADJUST / MAKEUP` can explain a new effective occurrence.
- `new_item_id / task_id / batch_id` must match the occurrence being consumed.

## 4. Optimistic client identity

Teacher clients may submit `scheduleItemId` as optimistic occurrence identity.

If live resolution returns another item, the command returns stable `409 DATA_CONFLICT` with expected/resolved evidence. It never silently rebinds the request.

## 5. ScopeHead boundaries

- SCHOOL and COLLEGE heads pointing to the same active batch are one authority and are deduplicated.
- the same TeachingTask appearing in more than one distinct current active batch is a data conflict and fails closed.
- an active head pointing to a missing/non-PUBLISHED batch is a data conflict.

## 6. TeachingTask readiness

The single executable-state contract is:

`TEACHER_CONFIRMED / COLLEGE_REVIEW / APPROVED / READY`

Attendance write path, attendance task discovery, and teacher miniapp must remain aligned to this set. Non-executable tasks cannot become ordinary classroom attendance even when a schedule row exists.

## 7. TeachingRoster and command behavior

Occurrence truth is validated before roster freeze and fact creation.

The mature command keeps:

- TeachingTask/class fail-fast before roster resolution;
- formal teacher ownership/data-scope checks;
- current versioned TeachingRoster consumption;
- `ATTENDANCE_SESSION` RosterConsumerSnapshot freeze;
- existing transaction/locking semantics.

C-C1 does not rewrite TeachingRoster Authority.

## 8. Duplicate occurrence / concurrency

Before INT lands canonical DB identity/unique constraints, C-W1 already protects ordinary classroom creation with a current locking read while holding formal schedule authority locks. MySQL concurrency evidence proves a single winner for two simultaneous creates of the same current occurrence.

This application guard is transitional defense, not a replacement for INT-owned schema work.

INT still owns:

- canonical `teaching_task_id` / `occurrence_identity` persistence;
- tenant-scoped active formal occurrence UNIQUE;
- `source_type / source_reason / source_evidence` schema;
- legacy inventory/backfill and dirty-data decision;
- migration upgrade/downgrade/rollback.

## 9. ADMIN_SPECIAL isolation

`ADMIN_SPECIAL` is not an ordinary classroom occurrence.

- ordinary teachers have no creation entry;
- admin special supplement requires explicit reason + evidence;
- source remains visible in DTO/UI/audit;
- default classroom statistics and standard absence-warning scan exclude ADMIN_SPECIAL;
- ADMIN_SPECIAL does not consume the formal occurrence duplicate guard.

## 10. Freeze evidence

At `3288e10907106d17d9dec64dc2a185b90a503bd5`, `Academic C W0 Mature Chain Freeze` completed successfully. The same job proved:

- current-main/shared-owner boundary check: success;
- mature production modules compile: success;
- Attendance / Exam / Grade / EffectiveGrade targeted MySQL regression: success;
- attendance frontend consumer source contracts: success;
- freeze invariant source contract: success.

C-C1 status: **FROZEN**.

The next C line stage is C-W2 Teacher Today. Teacher Today is a read projection only: it consumes this contract and must not create a second schedule/task/todo authority.
