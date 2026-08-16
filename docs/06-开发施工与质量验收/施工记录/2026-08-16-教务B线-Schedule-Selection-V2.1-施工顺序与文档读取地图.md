# 2026-08-16 教务 B 线 Schedule / Selection V2.1 施工顺序与文档读取地图

> 固定仓库：`penghaibin9/saas`  
> 固定分支：`agent/academic-b-schedule-selection`  
> Draft PR：`#146`  
> 唯一施工总册：`docs/06-开发施工与质量验收/施工总册/B_教务Schedule_Selection_当前代码精确施工总册_V2.1_20260816.md`  
> 用户原始总册 SHA-256：`b78af9dbdc1da5067a7cd1fc05e32f1121d5662e9661bc6f46eb4d7dc0d02999`  
> branch create base / main baseline：`414216c4a79ff035aee87d70b35572572f5c0535`  
> 当前 B exact HEAD：`00dddd7641ed3de7b8274087ff17ae4376f060ad`

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
| `main` | branch baseline `414216c4a79ff035aee87d70b35572572f5c0535` | 每 Wave 开始前重读；不擅自合 main |
| B | `00dddd7641ed3de7b8274087ff17ae4376f060ad` | W3 exact-head browser seal 已完成；进入 W4 |
| PR #96 | Academic static closure / MySQL semester rehearsal，Draft | 复用既有教务测试资产；不覆盖其 service registry 变更 |
| PR #132 | E-series integration，Draft | 共享 migration / route collision 只记录，交 INT |
| PR #133 | Control Plane Option B，Draft | permissions / Data Exchange / identity / route / Alembic 为 INT 禁区 |
| PR #145 | A — Semester/Core V2.1，Draft | A-C1～A-C4 只消费已冻结输出；W4 formationMode 未冻结前不自造枚举 |
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
| A-C1 Term Context Contract | `PENDING_A_FREEZE` | 已有 termId 只按当前正式模型消费；新合同未冻结不猜 |
| A-C2 Course Identity Contract | `PENDING_A_FREEZE` | W2/W4 只使用稳定 course id/code；未冻结不另造 |
| A-C3 Program Execution Contract | `PENDING_A_FREEZE` | Selection 资格需要时只消费正式输出 |
| A-C4 TeachingTask Formation Contract | `PENDING_A_FREEZE` | W4 formationMode 合法枚举等待 A 冻结；taskId/course/term/READY 独立 fail-closed 可先施工 |

## 6. B 输出合同

| Contract | 目标 Wave | 当前状态 |
|---|---|---|
| B-C1 Published Schedule Contract | W2 | `FROZEN @ 971d5fa9` |
| B-C2 Selection Eligibility Contract | W1 初版 / W2 冻结 | `FROZEN @ 971d5fa9` |
| B-C3 Student Selection Projection Contract | W5 | `NOT_FROZEN` |

## 7. Wave 施工地图

### B-W0 — 强底座回归冻结
当前事实：
1. `ScopeHead` 是正式课表唯一头：`(term, scope) → active_batch_id`；换版用版本和 `SUPERSEDED`。`KEEP`。
2. `schedule_final_service` 已有 Task-first canonical path。`KEEP`。
3. 正式周次由 term / task bounds 决定。`KEEP`。
4. `TeachingRoster` 在存在 Selection 关系时不回退行政班；未 final fail-closed。`KEEP`。
5. `Selection LOCK → TeachingRoster` 同事务投影正式名单。`KEEP`。
6. stale empty-roster regression contract 已修正：LOCKED 空正式名单是有效当前事实，不回退行政班。

状态：`COMPLETED`。

### B-W1 — SelectionPreflight 纯化
完成：
- malformed rule/scope/prerequisite JSON fail-closed；
- validator 不内部 commit；
- 单拒绝单审计事实；
- SelectionPreflight 纯读；
- admin → student PC → miniapp 单 spec real-click；
- 5 张 Gold 截图人工视觉复审通过。

状态：`COMPLETED @ 0aa85d1734e458e502917f4de02bbfbafdb3d073`。

### B-W2 — 两个旧消费者替换
完成：
- `AcademicGrade/name → EffectiveGrade transcript Provider`；
- `EFFECTIVE schedule rows → ScopeHead active batch Provider`；
- 无 ScopeHead 不回退，双 active task fail-closed；
- S11/S15/S16 + consumer/static contracts fresh MySQL targeted 通过。

状态：`COMPLETED @ 971d5fa971ec1312256bf10b9a7519fe7fde1f0f`。

### B-W3 — 排课管理 PC Task-first
完成：
- 管理 PC 新排课主入口改为 READY TeachingTask-first；
- 课程/教师/教学班只读回显，写入显式 `taskId`；
- UI 周次来自 TeachingTask，去固定 18 周默认；
- textarea CSV 正式 writer 退出主路径；批量导入切 Academic File Exchange XLSX；
- 第一批静态合同 + staff PC production build success；
- focused browser Run `31930601841` / job `95124664211` 在 exact HEAD `00dddd76` success；
- 4 张 Gold 人工视觉复审通过：Task-first selected / scheduled success / relogin persisted / File Exchange drawer。

状态：`COMPLETED @ 00dddd7641ed3de7b8274087ff17ae4376f060ad`。

### B-W4 — Selection 批次与课程身份
当前 independent RED：
- `add_course()` 对不存在 `teachingTaskId` 会静默继续；必须 fail-closed；
- TeachingTask 必须 `READY`；
- TeachingTask.course_id 必须等于 SelectionCourse.courseId；
- TeachingTask 所属 batch.term_id 必须等于 SelectionBatch.term_id；
- `formationMode` 合法枚举等待 A-C4 冻结，不自造；
- term/window/scope/rule version/hash 继续 inventory；
- dirty-data inventory；应用层先封；DB constraint 交 INT。

状态：`IN_PROGRESS / INDEPENDENT_FAIL_CLOSED_NEXT`。

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
| W0 Authority baseline freeze | 无正式 API/DTO 行为变化 | Schedule/Roster consumers | N/A | N/A | N/A | `COMPLETED` |
| W1 Preflight blockers | blockers / reason | 管理 PC + Student PC + miniapp | 同源 blocker/reason | 5 Gold PASS | PASS | `COMPLETED @ 0aa85d17` |
| W2 EffectiveGrade/ScopeHead provider | 无 DTO 变化 | Selection eligibility/conflict | N/A | N/A | N/A | `COMPLETED @ 971d5fa9` |
| W3 Task-first schedule writer | `taskId` canonical | AaScheduleMaintainView | Task-first + 只读 identity + File Exchange | 4 Gold PASS | PASS | `COMPLETED @ 00dddd76` |
| W4 batch/course identity | term/Task-bound fail-closed | AaSelectionConsoleView | 若错误合同/提示变化则同步 | OPEN | OPEN | `IN_PROGRESS` |
| W5 Student Projection | allowedActions/status projection | Student PC + miniapp | 两端只消费正式动作 | OPEN | OPEN | `NOT_STARTED` |

## 9. UI / Visual / Real-click 硬门

任何 Wave 只要后端正式合同变化：
`backend → canonical service → API/DTO → frontend adapter → affected PC/miniapp → help → before/after screenshot → 实际打开截图视觉识别 → real-click E2E → refresh/relogin/cross-client → exact-head evidence`。

后端绿但 UI/截图/真实点击未闭环时，只能标 `BACKEND_GREEN_UI_OPEN`；不得标 `COMPLETED`。

## 10. Evidence Ledger

| Evidence | Exact HEAD | Result |
|---|---|---|
| main baseline | `414216c4a79ff035aee87d70b35572572f5c0535` | branch creation baseline |
| uploaded manual SHA-256 | `b78af9dbdc1da5067a7cd1fc05e32f1121d5662e9661bc6f46eb4d7dc0d02999` | exact bytes materialized in branch |
| W0 Schedule/TeachingRoster KEEP | `0aa85d17` | exact-head MySQL authority freeze success |
| W1 cross-end real-click | `0aa85d17` | admin + student PC + miniapp success; 5 Gold visual PASS |
| W2 EffectiveGrade/ScopeHead targeted | `971d5fa9` | Run `31928378623` success |
| W3 static contract + staff build | `8e4da53a` | Run `31928948822` success |
| W3 focused browser seal | `00dddd76` | Run `31930601841`, job `95124664211` success; 4 Gold visual PASS |

## 11. 固定循环与下一入口

固定循环：
`文档 → exact-head源码 → CURRENT FACT → RED → 修根因 → targeted → MySQL → Frontend Impact Review → UI同步 → before/after截图 → 视觉识别 → real-click E2E → refresh/relogin/跨端 → KEEP regression → exact-head evidence → 回写本地图 → 下一安全 Wave`。

**下一入口：B-W4 independent fail-closed：先锁 `SelectionCourse → TeachingTask` 的存在性、READY、same-course、same-term；随后重读 A-C4，只在 formationMode 合同正式冻结后接合法枚举。禁止提前造 formationMode 真值，禁止碰 INT migration。**