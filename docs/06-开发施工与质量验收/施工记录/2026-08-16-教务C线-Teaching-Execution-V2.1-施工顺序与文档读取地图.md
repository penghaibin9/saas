# 教务 C 线 Teaching Execution V2.1 — 施工顺序与文档读取地图

> 固定施工分支：`agent/academic-c-teaching-execution`  
> Draft PR：`#148`  
> 基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 总册：`C_教务Teaching_Execution_当前代码精确施工总册_V2.1_20260816.md`  
> 原则：exact-head 代码事实优先；成熟 Authority 只 KEEP/HARDEN/REWIRE；不合并 main；不 force push。

## 1. 当前施工状态

| Wave | 目标 | 当前状态 | 下一硬门 |
|---|---|---|---|
| C-W0 | Mature Chain Freeze | `PROVEN@098f88ab / CURRENT_HEAD_REVALIDATING` | 当前用户提交重新触发 W0；只认同 SHA success |
| C-W1 | Published Occurrence + Attendance | `IN_PROGRESS / C_OWNED_HARDENED / B-C1_NOT_FROZEN` | current-head W0 → B-C1 freeze → occurrence RED/fix → UI/visual/E2E → C-C1 |
| C-W2 | Teacher Today | NOT_STARTED | 纯 read projection，禁止第二 Task/Todo；C-W1 未完成不得启动 |
| C-W3 | Exam hardening | NOT_STARTED | 保护现有 roster/publish 门禁 |
| C-W4 | Grade scale & operations | NOT_STARTED | SQL 分页、截止/催录、大 XLSX、退回重提等 |
| C-W5 | C Gold | NOT_STARTED | PC/miniapp/refresh/relogin/role change 一致性 |

## 2. Exact HEAD 与碰撞 Ledger

### Git truth

- `main`: `414216c4a79ff035aee87d70b35572572f5c0535`
- C 分支从该 SHA 建立。
- 首个 W0 Gold HEAD：`098f88abe52cc3c52c0470b49a5fe9b3384ab615`。
- 首个 W0 Run：`31899498070`，`Academic C W0 Mature Chain Freeze`，`completed/success`。
- `fe0975078` 的 W0 Run `31901849111`：`98 passed / 1 failed`；唯一失败为客户端 `classId` 与 TeachingTask class 不一致时，生产代码先进入 roster resolver。
- 生产根因修复：`9f68516e1f51366eda3f5750f3daaa80078d3ff9`，把 Task/class fail-fast 校验提前到 `resolve_versioned_roster()` 前；未改测试、未弱化断言、未改权限/事务/roster freeze 语义。
- `79df7d195d82715ef8090f0e02e55b3ebbf7736c`：原附件总册 exact materialize + staging 自清理 bot commit；bot push 对应 W0 被 GitHub 标 `action_required`，没有执行测试，因此不能算 current Gold。
- 本地图当前更新为有业务含义的用户提交，用来正常触发新 exact-head W0；后续只认该新 SHA 的真实执行结果。
- 后续任何 C-W1 commit 都会使旧 exact-head 证据失效；不得复用旧 SHA 冒充当前证据。

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

W0 Gate 会直接检查本分支相对 main 的 diff；命中以上文件或任何 Alembic revision 即失败。

## 4. C-W0 Mature Chain KEEP Matrix

### Attendance — KEEP

Authority / canonical path：

- `academic_affairs_attendance_public_service.create_session`
- 当前学期必须存在且可写；
- 普通教师必须提供 TeachingTask；
- Task 必须处于可教学状态；
- Task batch 必须属于当前 term；
- 普通教师必须是任务正式教师；
- 客户端若同时提交 `classId`，必须在进入 roster resolver 前确认其与 TeachingTask class 一致；不一致立即 fail-fast；
- 通过 `resolve_versioned_roster()` 消费正式 TeachingRoster；
- 同一事务冻结 `ATTENDANCE_SESSION` RosterConsumerSnapshot。

保护测试：

- `backend/tests/test_aa_attendance_task_binding.py`
- `backend/tests/test_aa_teaching_roster_unification.py`
- `backend/tests/test_aa_roster_consumers_r9.py`

W0 发现、W1 接管的缺口：公开 `create_session()` 内仍没有把 `sessionDate + slotNo` 解析成当前 Published Occurrence。

### Roster Consumer Snapshot — KEEP

Authority：`academic_affairs_roster_consumer_service.py`

已确认：

- 仅允许 `ATTENDANCE_SESSION / EXAM_COURSE / GRADE_TASK`；
- roster version 校验 hash + member count；
- freeze 前锁 TeachingClass 并在锁内重新解析 current roster；
- stale pre-read 会 409 `APPROVAL_VERSION_CONFLICT`；
- 同一 consumer 仅允许一条 ACTIVE；
- 正式退回换版必须显式 `allow_replace=True + replace_reason`，旧快照变 `SUPERSEDED` 且保留历史；
- publish/继续流转可用 `require_consumer_snapshot_current()` fail-closed。

### Exam — KEEP

Authority：`academic_affairs_exam_facade.py`

已确认：正式可写 term、TeachingTask、`EXAM_COURSE` roster freeze、名单外不可铺位、同课程跨考场不可重复、有效容量、发布前日期/时间/Task/current roster/预计人数/考场/座位全集/容量/监考完整性，以及发布后显式变更链。

保护测试：

- `backend/tests/test_aa_exam_facade_contract_and_changes.py`（MySQL-only）
- `backend/tests/test_aa_exam_fact_guards.py`

裁决：C 不重写 Exam。

### Grade — KEEP

Authority：`academic_affairs_grade_service.py`

已确认：

- GradeTask 绑定稳定 `courseId`/version；
- TeachingTask 课程身份不能被客户端替换；
- 正常任务消费正式 versioned roster；
- 名单外学生不能录正式成绩；
- submit 冻结 `GRADE_TASK` snapshot；
- publish 校验 snapshot 仍 current；
- 正式成绩保留课程身份、修读次数、教学班、名单版本/来源回链；
- 管理员补录为独立 `ADMIN_SUPPLEMENT_CLASS` 来源，不得反向成为普通发布链。

W4 欠账：`list_tasks()` 仍 `.all()` 后 Python slicing；严格留到 C-W4。

### EffectiveGrade — KEEP

Authority：`academic_affairs_effective_grade_policy_service.py`

已确认：courseId > courseCode+version；name-only 历史行使用独立 `LEGACY_NAME_KEY`；无 active policy、同生效学期多 active policy、多次修读缺冻结策略均 fail-closed；策略快照 event key + hash 幂等且禁止内容漂移覆盖。

保护测试：

- `backend/tests/test_aa_effective_grade_identity.py`
- `backend/tests/test_aa_effective_grade_policy_snapshot.py`
- `backend/tests/test_aa_mobile_effective_grade_policy.py`

### Grade Correction / Recheck — KEEP

Authority：

- `academic_affairs_grade_correction_command.py`
- `academic_affairs_grade_recheck_service.py`

更正/复查不是原地覆盖；旧正式版本退位并留历史，新 ACTIVE 版本追加写入，继续冻结 EffectiveGrade policy snapshot / audit / workflow。

保护测试：

- `backend/tests/test_aa_grade_recheck_concurrency.py`
- `backend/tests/test_aa_p0_hardening_20260804.py`

## 5. C-W0 exact-head Evidence

W0 独立 Gate：`.github/workflows/academic-c-w0-mature-chain-freeze.yml`。

首个成功证据：

- HEAD：`098f88abe52cc3c52c0470b49a5fe9b3384ab615`
- Run：`31899498070`
- conclusion：`success`
- DB：MySQL 8.0
- 覆盖：Attendance Task/Roster、Roster Snapshot、Exam roster/publish、Grade identity/roster、EffectiveGrade、Correction/Recheck。

当前 evidence chain：

- `fe0975078`：98 passed / 1 failed，暴露 class mismatch 校验顺序问题。
- `9f68516e`：生产根因修复落地；后续文档 materialize staging 使该 SHA 证据不能作为最终签字。
- `79df7d19`：总册 exact materialize 成功，但 bot-push W0 为 `action_required`，不算执行。
- 本地图更新后的用户 HEAD：必须重新跑 W0；只有同 SHA `completed/success` 才能恢复 `CURRENT_HEAD_GOLD`。

## 6. C-W1 Published Occurrence / Attendance

### 6.1 Published Occurrence 证伪结果

已读：

- `academic_affairs_schedule_truth_service.py`
- `academic_affairs_schedule_change_service.py`
- `academic_affairs_scheduling_final_service.py`
- `academic_affairs_term_calendar_convenience_service.py`
- `academic_affairs_service.py` calendar canonical path
- `mobile_academic_affairs_facade.py`
- `AaTerm / AaCalendarEvent / AaTimeSlot / AaScheduleItem / AaScheduleScopeHead`
- Attendance public/canonical service 与移动端调用链。

当前事实：

1. 正式课表已有唯一 `AaScheduleScopeHead(term, scope) -> active_batch_id` Authority；发布时锁 ScopeHead、做全校资源冲突、CAS 换版，旧 batch `SUPERSEDED`。`KEEP`。
2. Scope 同时支持 `SCHOOL,0` 和 `COLLEGE,<id>`；资源冲突跨学院全校扫描。因此 C 不能 hard-code `SCHOOL,0`，必须消费 B-C1 冻结的 Task→scope→active batch 解析规则。
3. 调停课终审会把 STOP/ADJUST 旧 `AaScheduleItem` 标 `CHANGED`；ADJUST/MAKEUP 生成新 `EFFECTIVE` item，并保留变更回链。`KEEP`。
4. `AaScheduleItem` 已有 `task_id / weekday / slot_no / start_week / end_week / week_parity / status`，不需要 C 再造第二套 schedule item 模型。
5. `AaTerm` 有 start/end/teachingWeeks；`AaCalendarEvent` 已承载 HOLIDAY/SWAP。canonical calendar 校验 SWAP 必须有 `swapToDate`；convenience 只做读投影，不是第二 Authority。
6. C 全仓尚未发现 Attendance 创建时消费上述正式课表 truth 的 resolver；当前 `sessionDate + slotNo` 仍只校验“有日期”，没有正式课次验证。
7. `mobile_academic_affairs_facade._current_term_and_batch()` 目前仍从当前学期里直接取最新 `status=PUBLISHED` batch，而不是 `ScopeHead.active_batch_id`；B 最新 HEAD 中也仍如此。这是 B-W2/B-C1 必须替换的旧移动课表消费者 seam，C 不能只加 Attendance 校验却让教师课表继续读旧批次。
8. **B 最新已复核 HEAD `e5897fd5cbb72e8c3001b3f7b8ba286921e0cc52`，其施工地图仍明确 B-C1 Published Schedule Contract = `NOT_FROZEN`。** 因此 C 现在禁止自行定义 PublishedOccurrence Provider，只保留调用图与 RED 设计；等 B-C1 冻结后接正式 Provider。

待 RED（B-C1 FROZEN 后立刻编码）：

- 正式 active-batch occurrence 成功；
- 非正式日期/节次失败；
- 调课/停课后旧 `CHANGED` occurrence 失败，新 `EFFECTIVE` ADJUST/MAKEUP occurrence 成功；
- start/end week 越界失败；
- ODD/EVEN 单双周错误失败；
- HOLIDAY 普通考勤失败；
- SWAP 正式换日课次成功；
- 邻租户/错误 scope 不得命中；
- 同一正式 occurrence 重复创建必须 fail-closed。

### 6.2 ADMIN_SPECIAL 旁路 — C 自有部分已 HARDEN

模型事实：`AaAttendanceSession` 当前没有独立 source_type/reason/evidence/occurrence_identity/teaching_task_id 列，只有 `session_type` 等兼容字段；也没有 `uk_aa_attendance*` occurrence 唯一约束。Alembic 属 INT 单 Owner，因此 C 不私建 migration，也不把不存在的模型字段写成已完成。

C 当前应用层 fail-closed：

- 普通教师请求 `ADMIN_SPECIAL` → 403；
- 管理员无 TeachingTask → 必须显式 `sessionType=ADMIN_SPECIAL`；
- ADMIN_SPECIAL → `specialReason/reason` 至少 5 字；
- ADMIN_SPECIAL → `specialEvidence/evidence` 必须存在；
- 有 TeachingTask 的 ADMIN_SPECIAL 仍走正式 versioned roster 并冻结 `ATTENDANCE_SESSION` snapshot；
- 无 Task 的特殊补录按明确行政班圈定；
- `session_type=ADMIN_SPECIAL` 持久化，audit detail 写 `source/reason/evidence`；
- DTO 增加派生 `sourceType=ADMIN_SPECIAL|FORMAL_TEACHING`；
- 默认正式课堂统计排除 ADMIN_SPECIAL；只有显式筛选才统计特殊补录；
- 标准旷课预警只消费 `FORMAL_TEACHING`，ADMIN_SPECIAL 不污染课堂预警；
- PC 特殊补录筛选下不提供标准“旷课预警扫描”；
- Round3 E2E fixture 已 TeachingTask-first，禁止管理员无 Task + classId 假装正式课堂。

生产提交起点：`6fed703c6023d170953f2ddd5550cdfcbf45508c`；后续 W1 修复包含预警、统计、UI、fixture 与 `9f68516e` class fail-fast 顺序修复。

保护测试：

- `backend/tests/test_aa_attendance_admin_special_contract.py`
- `backend/tests/test_aa_attendance_warning_source_contract.py`
- `frontend/tests/academic-attendance-source-contract.test.mjs`
- `miniapp/tests/academic-attendance-source-contract.test.mjs`

模型级 source/reason/evidence/occurrence identity/unique：`PENDING_INT_MIGRATION_DECISION`；约束已写入 `2026-08-16-教务C线-CW1-INT迁移与数据治理交接.md`。

### 6.3 Duplicate occurrence / concurrency 前置结论

当前 `AaAttendanceSession` 不含正式 occurrence/task identity，也没有 occurrence 唯一键；`create_session()` insert 前没有同课次去重锁。因此 B-C1 到位后：

1. C 先用正式 B-C1 occurrence identity 做应用层锁/重复冲突（409）并补 MySQL 并发 RED；
2. dirty-data inventory / legacy ADMIN_MANUAL 继续依据 append-only `AffairsAuditTrail`，不得猜历史原因；
3. DB unique / backfill / migration 交 INT；
4. C 不为过渡方便自创 `courseName+classId+date+slot` 伪唯一键。

## 7. B Contract Freeze 输入

C-W1 依赖：

- B-C1 Published Schedule Contract；
- B TeachingRoster Contract。

最近观察 B：

- branch：`agent/academic-b-schedule-selection`
- HEAD：`e5897fd5cbb72e8c3001b3f7b8ba286921e0cc52`
- B-C1：`NOT_FROZEN`

规则锁死：**B 未冻结时，C-W1 occurrence 部分只做调用图/源码证伪/RED 设计，不伪造 B Authority；C-W2 不启动。**

## 8. C 输出合同

- C-C1 Attendance Consumer Contract — C-W1 输出；当前 `DRAFT / BLOCKED_BY_B_C1`。
- C-C2 Exam Consumer Contract — C-W3 输出。
- C-C3 Effective Grade Read Contract — C-W4 输出。

D 线只消费这些正式合同/EffectiveGrade，不读取成绩草稿。

## 9. Frontend Impact Matrix

| Backend Change | API/DTO | Consumer | UI Change | Screenshot | Real Click | Status |
|---|---|---|---|---|---|---|
| C-W0 Authority freeze | 无生产行为变化 | N/A | N/A | N/A | N/A | `PROVEN@098f88 / CURRENT_REVALIDATING` |
| ADMIN_SPECIAL fail-closed + `sourceType` | attendance session DTO additive | 教师 miniapp attendance list/detail；PC stats | 普通教师不新增特殊入口；特殊历史场次显式中文来源；PC 默认正式课堂统计 | OPEN | OPEN | `BACKEND_IMPLEMENTED_EVIDENCE_OPEN` |
| Published Occurrence（待 B-C1） | B-C1 provider + C attendance consumer | `mobile_academic_affairs_facade`、教师课表、考勤创建 | 教师课表必须 ScopeHead 真值；考勤不再自由拼日期/节次；调课后旧课次退出、新课次生效 | OPEN | OPEN | `BLOCKED_BY_B_C1` |
| C-W3 Exam | 待判真 | 管理/教师/学生 Exam | 必须同批 | OPEN | OPEN | NOT_STARTED |
| C-W4 Grade allowedActions/status | 待判真 | 教师 PC + miniapp grade-entry + 学生成绩消费者 | 必须同批 | OPEN | OPEN | NOT_STARTED |

教师小程序现状已核：

- `attendance.vue` 新建场次强制选择 TeachingTask；sessionTypes 仅“常规/实训/晚自习/其他”，没有 ADMIN_SPECIAL 正常入口；
- 当前仍允许日期自由选、节次自由填/可空；B-C1 后必须由正式 occurrence 约束，不得靠前端自己算真值；
- `teacherApi → realApi → /mobile/teacher/academic/attendance/*` 为原始真实接口直通，没有 mapper 丢 DTO；
- `my-schedule/index.vue` 已适合作为 C-W1 调课前后视觉证据：按周/单双周展示课表，但当前无点名动作；
- 教师 `academic-affairs/index.vue` 当前“今日课表”由前端用 weekday/currentWeek/parity 自行筛选，整卡只去完整课表。C-W1 只保证其 schedule source 在 B-C1 后 rewired 到 ScopeHead；“今日课→名单→点名三步内”严格留到 C-W2 read projection，不提前混做。

PC 现状：考勤主要为查询/统计，不是普通教师正式逐生创建入口；C-W1 主要同步正式/特殊来源口径与调课后只读结果，不新增 PC 创建旁路。

## 10. 文档完整性 — COMPLETED

用户上传原始 C 总册唯一源证据：

- size：`333509` bytes
- actual text lines：`6169`
- SHA-256：`388b3f78e55bc43ef82c3cd71973d47fc530e674e271d3234b18ee6456d2afe4`

远端 exact materialize 证据：

- source checkout：`076d8d4227de442c9cc4c5d2825584dc4e54d34c`
- materialize Run：`31917454026`
- rerun job：`95092226331`
- log：`parts=7 payload_chars=73804`
- log：`size=333509 lines=6169 sha256=388b3f78e55bc43ef82c3cd71973d47fc530e674e271d3234b18ee6456d2afe4`
- bot commit：`79df7d195d82715ef8090f0e02e55b3ebbf7736c`
- result：root manual 6169 lines；`.tmp/academic-c-manual*`、7 correct parts、旧 parts、一次性 materialize workflow 全部从 PR diff 清零。

状态：`COMPLETED / EXACT_BYTES_PROVEN`。

## 11. 固定验收状态语义

- 只有后端绿：`BACKEND_GREEN_UI_OPEN`
- UI 已改未视觉：`UI_IMPLEMENTED_VISUAL_OPEN`
- 视觉绿未真实点击：`VISUAL_GREEN_E2E_OPEN`
- exact-head 改变导致旧证据失效：`EVIDENCE_STALE`
- backend + MySQL + frontend + screenshot + real-click E2E + refresh + role/dataScope negative + console/network + exact-head 全满足才可 `COMPLETED`。

## 12. 连续施工入口

当前连续入口：

`当前用户 HEAD W0 targeted → 只修真实红灯 → 轮询 B-C1 → B-C1 一冻结立刻读取 exact contract → ScopeHead/mobile schedule consumer rewire + PublishedOccurrence RED/Provider consumer → Attendance targeted/MySQL duplicate concurrency → frontend impact → UI/visual/real-click → C-C1 → C-W2`

若 B-C1 尚未冻结：继续只做 occurrence 调用图/RED 设计/前端 impact inventory，不自行实现 PublishedOccurrence，不跳 C-W2。