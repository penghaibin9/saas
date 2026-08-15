# 教务 C 线 Teaching Execution V2.1 — 施工顺序与文档读取地图

> 固定施工分支：`agent/academic-c-teaching-execution`  
> 基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 总册：`C_教务Teaching_Execution_当前代码精确施工总册_V2.1_20260816.md`  
> 原则：exact-head 代码事实优先；成熟 Authority 只 KEEP/HARDEN/REWIRE；不合并 main；不 force push。

## 1. 当前施工状态

| Wave | 目标 | 当前状态 | 下一硬门 |
|---|---|---|---|
| C-W0 | Mature Chain Freeze | IN_PROGRESS | exact-head targeted/MySQL freeze gate |
| C-W1 | Published Occurrence + Attendance | NOT_STARTED | 先证伪已有正式课次 resolver；B 合同未冻结则只做调用图/RED |
| C-W2 | Teacher Today | NOT_STARTED | 纯 read projection，禁止第二 Task/Todo |
| C-W3 | Exam hardening | NOT_STARTED | 保护现有 roster/publish 门禁 |
| C-W4 | Grade scale & operations | NOT_STARTED | SQL 分页、截止/催录、大 XLSX、退回重提等 |
| C-W5 | C Gold | NOT_STARTED | PC/miniapp/refresh/relogin/role change 一致性 |

## 2. Exact HEAD 与碰撞 Ledger

### Git truth

- `main`: `414216c4a79ff035aee87d70b35572572f5c0535`
- C 分支从该 SHA 建立；后续每批以 GitHub branch exact HEAD 为准。

### PR #96 — 教务静态收口

当前已确认直接触碰：

- `.github/workflows/academic-semester-rehearsal.yml`
- `backend/app/models/academic_affairs_registry.py`
- `backend/app/modules/academic_affairs/services/__init__.py`
- `backend/tests/test_aa_mobile_grade_entry_v2.py`
- `miniapp/src/pages/teacher/academic-affairs/grade-entry.vue`
- `scripts/check/academic-semester-rehearsal.sh`

C 线裁决：`academic_affairs_registry.py`、`services/__init__.py`、教师小程序 `grade-entry.vue` 均按碰撞只读处理；需要共享修改时交 INT 单 Owner，不能在 C 线抢写。

### PR #132 — 岗位实习横切基础设施

已确认碰 `backend/app/api/v1/route_registration.py`、迁移、部分共享模型等。C 线不修改这些共享面。

### PR #133 — Control Plane

已确认碰权限目录、统一数据交换、身份导入、公共路由、迁移等。C 线不修改这些共享面。

## 3. INT 单 Owner 禁写清单

C 分支默认只读：

- `backend/app/api/v1/route_registration.py`
- `backend/app/core/permissions.py`
- `backend/app/core/permission_catalog.py`
- `backend/app/models/data_exchange.py`
- `backend/app/services/data_exchange_confirm_service.py`
- `backend/app/services/identity_import_service.py`
- `backend/app/modules/academic_affairs/services/__init__.py`
- `backend/app/models/academic_affairs_registry.py`
- `backend/alembic/versions/**`

## 4. C-W0 Mature Chain KEEP Matrix

### Attendance — KEEP

Authority / canonical path:

- `academic_affairs_attendance_public_service.create_session`
- 当前学期必须存在且可写；
- 普通教师必须提供 TeachingTask；
- Task 必须处于可教学状态；
- Task batch 必须属于当前 term；
- 普通教师必须是任务正式教师；
- 通过 `resolve_versioned_roster()` 消费正式 TeachingRoster；
- 同一事务冻结 `ATTENDANCE_SESSION` RosterConsumerSnapshot。

现有保护测试：

- `backend/tests/test_aa_attendance_task_binding.py`
- `backend/tests/test_aa_teaching_roster_unification.py`
- `backend/tests/test_aa_roster_consumers_r9.py`

已发现但不在 W0 修改的缺口：当前公开 `create_session()` 内未看到 `sessionDate + slotNo` 必然解析为当前 Published Occurrence。转入 C-W1 继续全仓证伪。

管理员无 Task 的 class-based 路径当前存在 `ADMIN_MANUAL` 语义；是否已有模型级 sourceType/reason/evidence 足够隔离，转入 C-W1 继续判真。

### Roster Consumer Snapshot — KEEP

Authority:

- `academic_affairs_roster_consumer_service.py`

已确认：

- 仅允许 `ATTENDANCE_SESSION / EXAM_COURSE / GRADE_TASK`；
- roster version 校验 hash + member count；
- freeze 前锁 TeachingClass 并在锁内重新解析 current roster；
- stale pre-read 会 409 `APPROVAL_VERSION_CONFLICT`；
- 同一 consumer 仅允许一条 ACTIVE；
- 正式退回换版必须显式 `allow_replace=True + replace_reason`，旧快照变 `SUPERSEDED` 且保留历史；
- publish/继续流转可用 `require_consumer_snapshot_current()` fail-closed。

### Exam — KEEP

Authority:

- `academic_affairs_exam_facade.py`

已确认：

- Exam Batch 绑定正式可写 term；
- course confirm 必须关联 TeachingTask；
- confirm 冻结 `EXAM_COURSE` roster snapshot；
- 铺位只允许冻结名单成员；
- 同一学生同课程跨考场禁止重复；
- 有效容量门禁；
- publish 前校验日期/时间、Task、当前 roster snapshot、预计人数、考场、座位全集、容量、监考；
- 发布后普通改时/普通改派受阻，走显式变更链。

保护测试：

- `backend/tests/test_aa_exam_facade_contract_and_changes.py`（MySQL-only）
- `backend/tests/test_aa_exam_fact_guards.py`

裁决：C-W0/C-W1 不重写 Exam。

### Grade — KEEP

Authority:

- `academic_affairs_grade_service.py`

已确认：

- GradeTask 绑定具体 `courseId`；
- courseCode/version 缺失时 fail-closed；
- TeachingTask 的课程身份不能被客户端替换；
- 正常任务消费正式 versioned roster；
- 名单外学生不能录正式成绩；
- submit 冻结 `GRADE_TASK` roster snapshot；
- publish 前验证冻结名单仍为 current；
- 正式成绩保留稳定课程身份、修读次数、教学班、名单版本/来源回链；
- 管理员补录使用独立 `ADMIN_SUPPLEMENT_CLASS` 来源语义，不得反向成为普通发布链。

已识别的规模欠账：`list_tasks()` 仍 `.all()` 后 Python slicing；严格留给 C-W4，不在 W0 趁机改。

### EffectiveGrade — KEEP

Authority:

- `academic_affairs_effective_grade_policy_service.py`

已确认：

- 正式身份优先 `courseId`，其次 `courseCode + version`；
- name-only 历史记录使用逐行独立 `LEGACY_NAME_KEY`，不按同名静默合并；
- 无 active policy 的正式成绩写入 fail-closed；
- 同一生效学期多条 active policy fail-closed；
- 多次修读缺冻结策略时 fail-closed；
- policy snapshot 具 event key + hash，重试幂等，内容漂移禁止覆盖。

保护测试：

- `backend/tests/test_aa_effective_grade_identity.py`
- `backend/tests/test_aa_effective_grade_policy_snapshot.py`
- `backend/tests/test_aa_mobile_effective_grade_policy.py`

### Grade Correction / Recheck — KEEP

Authority:

- `academic_affairs_grade_correction_command.py`
- `academic_affairs_grade_recheck_service.py`

已确认正式方向：更正/复查不是原地覆盖正式成绩；旧版本退出当前态并保留历史，新正式版本追加写入，继续消费 EffectiveGrade policy snapshot / audit / workflow 事实。

保护测试优先纳入：

- `backend/tests/test_aa_grade_recheck_concurrency.py`
- `backend/tests/test_aa_p0_hardening_20260804.py`

## 5. C-W0 targeted freeze gate

C-W0 只加独立 Gate，不改成熟生产 Authority。Gate 必须使用 MySQL 8.0，并至少覆盖：

1. Attendance Task/Roster；
2. Roster snapshot versioning；
3. Exam roster/publish guards；
4. Grade formal roster + stable course identity；
5. EffectiveGrade identity/policy snapshot；
6. Correction/Recheck concurrency and append-only semantics。

状态：`PENDING_GITHUB_ACTIONS`。只有 exact-head run `completed/success` 才把 C-W0 标 COMPLETED。

## 6. B Contract Freeze 输入

C-W1 依赖：

- B-C1 Published Schedule Contract；
- B TeachingRoster Contract。

当前尚未在 C 线拿到 B 最终冻结证据。因此规则锁死：**B 未冻结时，C-W1 只允许做调用图、源码证伪和 RED；不得在 C 线伪造 B Authority。**

## 7. C 输出合同

- C-C1 Attendance Consumer Contract — C-W1 输出
- C-C2 Exam Consumer Contract — C-W3 输出
- C-C3 Effective Grade Read Contract — C-W4 输出

D 线只消费这些正式合同/EffectiveGrade 事实，不读取成绩草稿。

## 8. Frontend Impact Matrix

| Backend Change | API/DTO | Consumer | UI Change | Screenshot | Real Click | Status |
|---|---|---|---|---|---|---|
| C-W0 无生产合同变化，仅冻结既有 Authority | N/A | N/A | N/A | N/A | N/A | W0_PROOF_ONLY |
| C-W1 Published Occurrence/Attendance（若合同变化） | 待判真 | 教师 PC + 教师小程序课表/考勤/Today | 必须同批 | 必须 | 必须 | NOT_STARTED |
| C-W3 Exam hardening（若合同变化） | 待判真 | 管理/教师/学生 Exam | 必须同批 | 必须 | 必须 | NOT_STARTED |
| C-W4 Grade allowedActions/status | 待判真 | 教师 PC + 小程序 grade-entry + 学生成绩消费者 | 必须同批 | 必须 | 必须 | NOT_STARTED |

## 9. 固定验收状态语义

- 只有后端绿：`BACKEND_GREEN_UI_OPEN`
- UI 已改未视觉：`UI_IMPLEMENTED_VISUAL_OPEN`
- 视觉绿未真实点击：`VISUAL_GREEN_E2E_OPEN`
- exact-head 改变导致旧证据失效：`EVIDENCE_STALE`
- backend + MySQL + frontend + screenshot + real-click E2E + refresh + role/dataScope negative + console/network + exact-head 全满足才可 `COMPLETED`。

## 10. 连续施工入口

当前入口：`C-W0 targeted freeze gate → exact-head evidence`。

C-W0 一旦绿，自动进入：

`C-W1 全仓 Published Occurrence 证伪 → 调课前后课次解析 → Attendance RED → 最小生产修复（若确有缺口） → targeted/MySQL → Frontend Impact → UI/截图/真实点击 → C-C1`。
