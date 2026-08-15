# 教务 C 线 Teaching Execution V2.1 — 施工顺序与文档读取地图

> 固定施工分支：`agent/academic-c-teaching-execution`  
> Draft PR：`#148`  
> 基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 总册：`C_教务Teaching_Execution_当前代码精确施工总册_V2.1_20260816.md`  
> 原则：exact-head 代码事实优先；成熟 Authority 只 KEEP/HARDEN/REWIRE；不合并 main；不 force push。

## 1. 当前施工状态

| Wave | 目标 | 当前状态 | 下一硬门 |
|---|---|---|---|
| C-W0 | Mature Chain Freeze | `PROVEN@098f88ab / REVALIDATING_CURRENT_HEAD` | W0 Gate 在每个后续 HEAD 继续跑 KEEP regression |
| C-W1 | Published Occurrence + Attendance | `IN_PROGRESS / B-C1_NOT_FROZEN` | ADMIN_SPECIAL targeted → B-C1 freeze → occurrence RED/fix → UI/visual/E2E → C-C1 |
| C-W2 | Teacher Today | NOT_STARTED | 纯 read projection，禁止第二 Task/Todo |
| C-W3 | Exam hardening | NOT_STARTED | 保护现有 roster/publish 门禁 |
| C-W4 | Grade scale & operations | NOT_STARTED | SQL 分页、截止/催录、大 XLSX、退回重提等 |
| C-W5 | C Gold | NOT_STARTED | PC/miniapp/refresh/relogin/role change 一致性 |

## 2. Exact HEAD 与碰撞 Ledger

### Git truth

- `main`: `414216c4a79ff035aee87d70b35572572f5c0535`
- C 分支从该 SHA 建立。
- 首个 W0 Gold HEAD：`098f88abe52cc3c52c0470b49a5fe9b3384ab615`。
- W0 Run：`31899498070`，`Academic C W0 Mature Chain Freeze`，`completed/success`。
- 后续 C-W1 commit 会使旧 exact-head 证据按规则过期；因此同一 W0 KEEP Gate 在每个新 HEAD 自动重验，不复用旧 SHA 冒充当前证据。

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
- 通过 `resolve_versioned_roster()` 消费正式 TeachingRoster；
- 同一事务冻结 `ATTENDANCE_SESSION` RosterConsumerSnapshot。

保护测试：

- `backend/tests/test_aa_attendance_task_binding.py`
- `backend/tests/test_aa_teaching_roster_unification.py`
- `backend/tests/test_aa_roster_consumers_r9.py`

W0 发现、W1 接管的缺口：公开 `create_session()` 内没有把 `sessionDate + slotNo` 解析成当前 Published Occurrence。

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

C-W1 新增 ADMIN_SPECIAL 后，Gate 已增加 `test_aa_attendance_admin_special_contract.py` 与 source invariant；当前 HEAD 必须重新 success 后才能把 W0 证据记为 current。

## 6. C-W1 Published Occurrence / Attendance

### 6.1 Published Occurrence 证伪结果

已读：

- `academic_affairs_schedule_truth_service.py`
- `academic_affairs_schedule_change_service.py`
- `academic_affairs_scheduling_final_service.py`
- `academic_affairs_term_calendar_convenience_service.py`
- `AaTerm / AaCalendarEvent / AaTimeSlot`
- Attendance public/canonical service 与移动端调用链。

当前事实：

1. 正式课表已有唯一 `AaScheduleScopeHead(term, scope) -> active_batch_id` Authority；发布时锁 ScopeHead、做全校资源冲突、CAS 换版，旧 batch `SUPERSEDED`。`KEEP`。
2. 调停课终审会把旧 `AaScheduleItem` 标 `CHANGED`；ADJUST/MAKEUP 生成新 `EFFECTIVE` item，并保留 `change_id/new_item_id` 回链。`KEEP`。
3. `AaTerm` 有 start/end/teachingWeeks；`AaCalendarEvent` 已承载 HOLIDAY/SWAP；不是新建第二校历的理由。`KEEP`。
4. C 全仓尚未发现 Attendance 创建时消费上述正式课表 truth 的 resolver；当前 `sessionDate + slotNo` 只校验“有日期”，没有正式课次验证。
5. **但 B 线自己的施工地图确认：B-C1 Published Schedule Contract 目标 B-W2，当前仍 `NOT_FROZEN`。** 因此 C 现在禁止自行定义 PublishedOccurrence Provider，只保留调用图与 RED 目标；等 B-C1 冻结后接正式 Provider。

待 RED：

- 非正式日期/节次失败；
- 调课后旧课次失败、新课次成功；
- 单双周错误失败；
- HOLIDAY 普通考勤失败；
- SWAP/MAKEUP 正式课次成功。

### 6.2 ADMIN_SPECIAL 旁路 — 已进入施工

模型事实：`AaAttendanceSession` 当前没有独立 source_type/reason/evidence 列，只有 `session_type` 和 `AffairsAuditTrail`。Alembic 属 INT 单 Owner，因此 C 不私建 migration，也不把不存在的模型字段写成已完成。

C 当前先做应用层 fail-closed：

- 普通教师请求 `ADMIN_SPECIAL` → 403；
- 管理员无 TeachingTask → 必须显式 `sessionType=ADMIN_SPECIAL`；
- ADMIN_SPECIAL → `specialReason/reason` 至少 5 字；
- ADMIN_SPECIAL → `specialEvidence/evidence` 必须存在；
- 有 TeachingTask 的 ADMIN_SPECIAL 仍走正式 versioned roster 并冻结 `ATTENDANCE_SESSION` snapshot；
- 无 Task 的特殊补录按明确行政班圈定；
- `session_type=ADMIN_SPECIAL` 持久化，audit detail 写 `source/reason/evidence`；
- DTO 增加派生 `sourceType=ADMIN_SPECIAL|FORMAL_TEACHING`，便于消费者区分。

生产提交：`6fed703c6023d170953f2ddd5550cdfcbf45508c`。

保护测试：`backend/tests/test_aa_attendance_admin_special_contract.py`，已纳入 W0 MySQL Gate。

模型级 source/reason/evidence 独立字段：`PENDING_INT_MIGRATION_DECISION`；不是 C 当前完成项。

## 7. B Contract Freeze 输入

C-W1 依赖：

- B-C1 Published Schedule Contract；
- B TeachingRoster Contract。

最近观察 B branch：`agent/academic-b-schedule-selection` 正在 B-W1，B-C1 仍未冻结。规则锁死：**B 未冻结时，C-W1 occurrence 部分只做调用图/源码证伪/RED 设计，不伪造 B Authority。**

## 8. C 输出合同

- C-C1 Attendance Consumer Contract — C-W1 输出；当前 `DRAFT / BLOCKED_BY_B_C1`。
- C-C2 Exam Consumer Contract — C-W3 输出。
- C-C3 Effective Grade Read Contract — C-W4 输出。

D 线只消费这些正式合同/EffectiveGrade，不读取成绩草稿。

## 9. Frontend Impact Matrix

| Backend Change | API/DTO | Consumer | UI Change | Screenshot | Real Click | Status |
|---|---|---|---|---|---|---|
| C-W0 Authority freeze | 无生产行为变化 | N/A | N/A | N/A | N/A | `PROVEN@098f88 / CURRENT_REVALIDATING` |
| ADMIN_SPECIAL fail-closed + `sourceType` | attendance session DTO additive | 教师 miniapp attendance list/detail；管理员兼容调用 | 普通教师 UI 本来强制 TeachingTask，不新增特殊入口；若出现特殊历史场次需显式标识 | OPEN | OPEN | `BACKEND_IMPLEMENTED_EVIDENCE_OPEN` |
| Published Occurrence（待 B-C1） | 待冻结 | 教师 PC/miniapp课表、考勤、Teacher Today | 调课后旧课次退出、新课次生效 | OPEN | OPEN | `BLOCKED_BY_B_C1` |
| C-W3 Exam | 待判真 | 管理/教师/学生 Exam | 必须同批 | OPEN | OPEN | NOT_STARTED |
| C-W4 Grade allowedActions/status | 待判真 | 教师 PC + miniapp grade-entry + 学生成绩消费者 | 必须同批 | OPEN | OPEN | NOT_STARTED |

教师小程序现状已核：新建场次强制选择本人 TeachingTask，sessionTypes 仅“常规/实训/晚自习/其他”，没有 ADMIN_SPECIAL 正常入口；因此本轮绝不把特殊补录按钮塞进普通教师工作流。

## 10. 文档完整性

用户上传原始 C 总册本地证据：

- size：`333509` bytes
- SHA-256：`388b3f78e55bc43ef82c3cd71973d47fc530e674e271d3234b18ee6456d2afe4`

分支当前根目录总册为首次内容接口写入的 2191 行节选，不满足“原文放进分支”。修复方案沿 B 线已验证的一次性 materialize workflow：分片上传 → Actions 拼接/解压 → size/SHA 双校验 → 覆盖正式总册 → 自清理 helper。状态：`IN_PROGRESS`，未完成前不得声称原文已完整入库。

## 11. 固定验收状态语义

- 只有后端绿：`BACKEND_GREEN_UI_OPEN`
- UI 已改未视觉：`UI_IMPLEMENTED_VISUAL_OPEN`
- 视觉绿未真实点击：`VISUAL_GREEN_E2E_OPEN`
- exact-head 改变导致旧证据失效：`EVIDENCE_STALE`
- backend + MySQL + frontend + screenshot + real-click E2E + refresh + role/dataScope negative + console/network + exact-head 全满足才可 `COMPLETED`。

## 12. 连续施工入口

当前连续入口：

`ADMIN_SPECIAL exact-head Gate → 完整总册 materialize → 持续轮询 B-C1 → B-C1 一冻结立刻接 PublishedOccurrence RED/Provider → Attendance targeted/MySQL → frontend impact → UI/visual/real-click → C-C1 → C-W2`。
