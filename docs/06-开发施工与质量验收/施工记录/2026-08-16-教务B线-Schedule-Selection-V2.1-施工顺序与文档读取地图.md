# 2026-08-16 教务 B 线 Schedule / Selection V2.1 施工顺序与文档读取地图

> 固定仓库：`penghaibin9/saas`  
> 固定分支：`agent/academic-b-schedule-selection`  
> Draft PR：`#146`  
> 唯一施工总册：`docs/06-开发施工与质量验收/施工总册/B_教务Schedule_Selection_当前代码精确施工总册_V2.1_20260816.md`  
> 用户原始总册 SHA-256：`b78af9dbdc1da5067a7cd1fc05e32f1121d5662e9661bc6f46eb4d7dc0d02999`  
> branch create base / current main：`414216c4a79ff035aee87d70b35572572f5c0535`  
> 首次建图前 B HEAD：`1126d4bc515f49aaeaa3abfb19c14f720b3829b2`

## 1. Authority 与硬纪律

优先级固定：`exact-head 当前代码事实 > V2.1 当前裁决 > V1.5 附录 > 历史设计 > 外部成熟系统启发`。

禁止：
- 新建第二套 `ScopeHead / OfficialSchedule / TeachingRoster`；
- 课程名称作为正式资格身份；
- 旧 `AcademicGrade` 作为正式先修真值；
- 旧 `EFFECTIVE` 行直接代表当前正式课表；
- 坏 JSON fail-open；
- validator 内部 commit；
- 前端自行计算 `allowedActions`；
- 正式 `SelectionCourse` 无 TeachingTask；
- 无正式 term 发布；
- B 线抢共享迁移、权限、公共路由、公共注册；
- skip / xfail / ignore、SQLite 冒充 MySQL、弱化断言制造假绿；
- force push；
- 未经明确授权合并 main。

## 2. exact-head 与开放 PR Collision Ledger

| 对象 | 当前观察 | B 线裁决 |
|---|---|---|
| `main` | `414216c4a79ff035aee87d70b35572572f5c0535` | B 从此基线创建；每 Wave 开始前重读 |
| B | 建图前 `1126d4bc515f49aaeaa3abfb19c14f720b3829b2` | 后续每次写入更新 exact-head 证据 |
| PR #96 | Academic static closure / MySQL semester rehearsal，Draft | 复用既有教务测试资产；不覆盖其 service registry 变更 |
| PR #132 | E-series integration，Draft | 共享 migration / route collision 只记录，交 INT |
| PR #133 | Control Plane Option B，Draft | permissions / Data Exchange / identity / route / Alembic 为 INT 禁区 |
| PR #145 | A — Semester/Core V2.1，Draft；已改 `test_aa_term_current_mysql.py` 和 A 施工地图 | A-C1～A-C4 只消费已冻结输出；未冻结不伪造 |
| PR #112/#113 | platform/system control-plane 历史拆分线仍 open | 若碰公共权限/路由，继续按 INT 单 Owner |

## 3. INT 共享禁区（B 不直接施工）

- `backend/app/api/v1/route_registration.py`
- `backend/app/core/permissions.py`
- `backend/app/core/permission_catalog.py`
- `backend/app/models/data_exchange.py`
- `backend/app/services/data_exchange_confirm_service.py`
- `backend/app/services/identity_import_service.py`
- `backend/app/modules/academic_affairs/services/__init__.py`
- `backend/app/models/academic_affairs_registry.py`
- `backend/alembic/versions/**`

需要数据库约束时固定走：`inventory → 应用层先封 → backfill/标异常 → reconciliation → INT migration → MySQL 验收`。

## 4. B 独占/优先施工面

### Backend
- `backend/app/modules/academic_affairs/services/academic_affairs_schedule_truth_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_schedule_final_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_schedule_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_teaching_roster_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_teaching_roster_core_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_selection_core_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_selection_final_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_selection_service.py`
- Selection router / models / DecisionTrace / projection，只在不触碰 INT 单 Owner 文件时施工。

### Frontend
- `AaScheduleMaintainView.vue`
- `AaSchedulingConsoleView.vue`
- `AaSelectionConsoleView.vue`
- `AaSelectionStudentView.vue`
- 学生小程序选课页面
- 学生/教师正式课表消费者
- Selection roster / TeachingRoster 展示消费者

### Baseline tests
- `backend/tests/test_aa_schedule_active_truth.py`
- `backend/tests/test_aa_teaching_roster_unification.py`
- `backend/tests/test_aa_selection_lock_scaling.py`
- `backend/tests/test_aa_d6_selection_truth_contract.py`
- Lottery / FCFS / MySQL scope / concurrency 相关现有测试继续 inventory，不新造平行真值。

## 5. A 输入依赖

| Contract | 状态 | B 规则 |
|---|---|---|
| A-C1 Term Context Contract | `PENDING_A_FREEZE` | W3 周次/term 消费前必须重新读取冻结版；未冻结不猜 |
| A-C2 Course Identity Contract | `PENDING_A_FREEZE` | W2/W4 只使用稳定 course identity；未冻结不另造 |
| A-C3 Program Execution Contract | `PENDING_A_FREEZE` | Selection 资格需要时只消费正式输出 |
| A-C4 TeachingTask Formation Contract | `PENDING_A_FREEZE` | W4 SelectionCourse→Task 绑定前必须重读；未冻结继续 B 独立工作 |

## 6. B 输出合同

| Contract | 目标 Wave | 当前状态 |
|---|---|---|
| B-C1 Published Schedule Contract | W2 | `NOT_FROZEN` |
| B-C2 Selection Eligibility Contract | W1 初版 / W2 冻结 | `NOT_FROZEN` |
| B-C3 Student Selection Projection Contract | W5 | `NOT_FROZEN` |

## 7. Wave 施工地图

### B-W0 — 强底座回归冻结
读取：V2.1 强底座、V1.5 Official Schedule / TeachingRoster、仓库“教学任务/教学班/排课/课表/调停课/考勤”对齐资料。

exact-main 已读源码：
- `academic_affairs_schedule_truth_service.py`
- `academic_affairs_schedule_final_service.py`
- `academic_affairs_teaching_roster_service.py`
- `academic_affairs_selection_final_service.py`
- 对应 Schedule / Roster / Selection tests。

当前事实：
1. `ScopeHead` 是正式课表唯一头：`(term, scope) → active_batch_id`；换版用版本和 `SUPERSEDED`，发布顺序为锁范围头→全校资源冲突→CAS 换版。`KEEP`。
2. `schedule_final_service` 已有 Task-first canonical path：显式 `taskId` 会要求 READY 且属于同学期允许 Task；名称匹配仍作为 legacy fallback 存在。`KEEP + later meter/retire fallback`。
3. 正式周次由 term bounds / task bounds 决定，final service 不需要重建 18 周真值。`KEEP`。
4. `TeachingRoster` 在存在 Selection 关系时不回退行政班；最新 Selection 未 final 时 fail-closed；LOCK 投影正式名单。`KEEP`。
5. `Selection LOCK → TeachingRoster` 使用同一命令事务中的校验、状态转换和 roster projection。`KEEP`。
6. 发现一处真实基线回归合同漂移：production roster 明确允许 LOCKED 后正式空名单作为有效当前事实，但 `test_aa_teaching_roster_unification.py::test_locked_selection_with_empty_roster_is_not_ready` 仍期待 `SELECTION_EMPTY/ready=false`。W0 第一修应更新测试以锁定当前 Authority，禁止为了过旧测试反向削弱 production service。

W0 RED / Gate：
- 先修上述 stale regression contract；
- `test_aa_schedule_active_truth.py` 明确 MySQL-only，继续作为 ScopeHead 强门；
- TeachingRoster unification；
- selection lock scaling；
- D6 Selection Final→TeachingRoster contract；
- Lottery / FCFS / MySQL scope inventory 后纳入同一 exact-head Gate。

状态：`IN_PROGRESS / STATIC_AUTHORITY_PROVEN / MYSQL_EVIDENCE_OPEN`。

### B-W1 — SelectionPreflight 纯化
读取：B-P0-04/B-P0-07、Selection rules / eligibility、selection core/final/router/models、audit/DecisionTrace。

RED：
- 坏 rule/scope/prerequisite JSON 不得 fail-open；
- validator 绝不 commit；
- 同一拒绝只产生一条正式拒绝事实；
- SelectionPreflight 纯读；
- 发布规则冻结。

输出 B-C2 初版。状态：`NOT_STARTED`。

### B-W2 — 两个旧消费者替换
- `AcademicGrade/name → EffectiveGrade Provider`
- `EFFECTIVE schedule rows → ScopeHead active batch Provider`
- 冻结 B-C1 / B-C2；同步学生资格、冲突提示、正式课表消费者。
状态：`NOT_STARTED`。

### B-W3 — 排课管理 PC Task-first
- 管理 PC 选择 TeachingTask；课程/教师/班级只读回显；
- 新排课显式 `taskId`；
- 去 18 周 UI 默认；
- 去页面文本 CSV 正式 writer；批量导入跳 File Exchange；
- legacy name fallback 仅兼容 + 计量。
状态：`NOT_STARTED`。

### B-W4 — Selection 批次与课程身份
- term/window/scope/rule version/hash；
- `SelectionCourse` 必须同 term、同 course、合法 formationMode 的 TeachingTask；
- dirty-data inventory；应用层先封；DB constraint 交 INT。
状态：`NOT_STARTED`。

### B-W5 — Student Selection Projection
后端统一返回 `status/statusLabel/phase/eligibility/allowedActions/reason/howToResolve/window/lottery/reselect`；PC/miniapp 只渲染 allowedActions。
覆盖 OPEN / PENDING_LOTTERY / LOTTERY_LOST / COURSE_CANCELLED / LOCKED。
输出 B-C3。状态：`NOT_STARTED`。

### B-W6 — MySQL 高峰封板
- 最后 1 名额 100+ 并发；
- 1k burst；
- 双 Lottery draw；
- LOCK/drop 竞态；
- Selection↔Roster count/hash；
- deadlock retry；
- 邻租户负向。
完成后 B Contract Freeze，并通知 C 只消费正式 TeachingRoster。
状态：`NOT_STARTED`。

## 8. Frontend Impact Matrix

| Backend Change | API/DTO | Consumer | UI Change | Screenshot | Real Click | Status |
|---|---|---|---|---|---|---|
| W0 Authority baseline freeze | 无正式 API/DTO 行为变化 | Schedule/Roster consumers | N/A：本 Wave 不改 UI 合同 | N/A | N/A | `STATIC_REVIEW_IN_PROGRESS` |
| W1 Preflight blockers | 待施工 | AaSelectionConsoleView + student eligibility consumers | 必须显示同一 blocker/reason | OPEN | OPEN | `NOT_STARTED` |
| W2 EffectiveGrade/ScopeHead provider | 待施工 | 学生资格/冲突/正式课表消费者 | 禁止旧真值文案/状态 | OPEN | OPEN | `NOT_STARTED` |
| W3 Task-first schedule writer | `taskId` canonical | AaScheduleMaintainView / AaSchedulingConsoleView | Task-first + 只读 identity | OPEN | OPEN | `NOT_STARTED` |
| W4 batch/course identity | term/window/scope/Task-bound | AaSelectionConsoleView | 新建/发布/供给阻断 | OPEN | OPEN | `NOT_STARTED` |
| W5 Student Projection | allowedActions/status projection | Student PC + miniapp | 两端只消费正式动作 | OPEN | OPEN | `NOT_STARTED` |

## 9. UI / Visual / Real-click 硬门

任何 Wave 只要后端正式合同变化：
`backend → canonical service → API/DTO → frontend adapter → affected PC/miniapp → help → before/after screenshot → 实际打开截图视觉识别 → real-click E2E → refresh/relogin/cross-client → exact-head evidence`。

后端绿但 UI/截图/真实点击未闭环时，只能标 `BACKEND_GREEN_UI_OPEN`；不得标 `COMPLETED`。

## 10. Evidence Ledger

| Evidence | Exact HEAD | Result |
|---|---|---|
| main baseline | `414216c4a79ff035aee87d70b35572572f5c0535` | frozen for branch creation |
| B branch creation | `414216c4a79ff035aee87d70b35572572f5c0535` | branch created |
| uploaded manual SHA-256 | source `b78af9dbdc1da5067a7cd1fc05e32f1121d5662e9661bc6f46eb4d7dc0d02999` | materialization/checksum gate started |
| W0 static Schedule truth audit | main `414216c4` | KEEP confirmed |
| W0 static TeachingRoster audit | main `414216c4` | KEEP confirmed; stale empty-roster test found |
| W0 MySQL / targeted | pending | NOT CLAIMED |
| W0 screenshots/E2E | N/A unless behavior/UI changes | NOT CLAIMED |

## 11. 固定循环与下一入口

固定循环：
`文档 → exact-head源码 → CURRENT FACT → RED → 修根因 → targeted → MySQL → Frontend Impact Review → UI同步 → before/after截图 → 视觉识别 → real-click E2E → refresh/relogin/跨端 → KEEP regression → exact-head evidence → 回写本地图 → 下一安全 Wave`。

**下一入口：完成总册 materialization SHA 校验 → 修 W0 stale empty-roster regression contract → 收齐 Schedule truth / TeachingRoster / selection-lock scaling / Lottery / FCFS / MySQL scope exact-head Gate；W0 未冻结前不进入 W1 生产改造。**
