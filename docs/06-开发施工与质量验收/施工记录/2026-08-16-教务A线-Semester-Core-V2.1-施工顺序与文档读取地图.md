# 教务 A 线 Semester/Core V2.1 施工顺序与文档读取地图

> 固定分支：`agent/academic-a-semester-core`
> 唯一当前施工依据：`A_教务Semester_Core_当前代码精确施工总册_V2.1_20260816.md`
> 原则：current exact-head 代码事实 > V2.1 当前裁决 > V1.5 附录 > 历史设计。
> 禁止：未经明确授权合并 `main`、force push、skip/xfail/ignore、SQLite 代替 MySQL 并发证据、抢占 INT 共享文件 Owner。

## 1. Exact-head 开工事实

- `main` 开工 exact HEAD：`414216c4a79ff035aee87d70b35572572f5c0535`
- A 分支创建基线：`414216c4a79ff035aee87d70b35572572f5c0535`
- 本次地图刷新前 A exact HEAD：`eaa4b4660497322447714ab669ba232c7a957e64`
- 唯一总册原文已完整提交到本分支：`docs/06-开发施工与质量验收/施工记录/A_教务Semester_Core_当前代码精确施工总册_V2.1_20260816.md`
- 当前状态：`A-W1_IN_PROGRESS`；禁止在 MySQL + UI + E2E 未闭环前标 `COMPLETED`。

## 2. Open PR Collision Ledger

### PR #96 — `agent/academic-static-closure-20260811`
- 状态：OPEN / DRAFT；开工时 `mergeable=false`。
- 直接碰撞：教务服务注册、教务模型注册、教师小程序成绩录入等既有收口面。
- A 线裁决：不覆盖其共享注册语义；A 独占 service 改动必须做语义级对账，不能整树覆盖。

### PR #132
- 开工复核发现公共 `route_registration.py` / 横切模型测试存在碰撞风险。
- A 线裁决：公共路由不由 A 修改；若 A 新 endpoint 需要公共注册，交 INT 回收。

### PR #133 — control-plane 集成线
- 直接碰撞：Permission Catalog、Data Exchange、identity import、公共 route registration、Alembic 等共享面。
- A 线裁决：A-W4 只实现 Academic File Exchange 业务适配器和本线合同；公共 Data Exchange / identity / migration / permission 变化全部交 INT。

### 其他共享风险
- #112/#113 作为 control-plane 共享 Permission/Alembic/route-registration 风险持续监控。
- 任一开放 PR 新增触碰 A 当前改动文件时重新做 collision audit。

## 3. File Owner Matrix

### A 独占/本线可安全加固业务面
- `backend/app/modules/academic_affairs/services/academic_affairs_term_workspace_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_program_governance_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_task_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_dashboard_scope_facade.py`（只做公开读侧 facade，不接管共享注册）
- `backend/app/modules/academic_affairs/services/academic_affairs_effective_grade_policy_current_term.py`（复用既有自动安装点做 A-C1 安全边界）
- A 线对应 PC / portal / miniapp 消费者和 targeted tests。

### A 只读复用，不重写 Authority
- `academic_affairs_teaching_roster_service.py`
- `academic_affairs_schedule_truth_service.py`
- `academic_affairs_effective_grade_policy_service.py`
- `academic_affairs_graduation_immutable_service.py`
- `backend/app/services/academic_calendar_service.py`：SYS-12 全校学期治理；A-W1 读取其 contract 并通过既有 SQLAlchemy 安全层串行，不在本线重写其状态机。

### INT 共享禁区
- `backend/app/api/v1/route_registration.py`
- `backend/app/core/permissions.py`
- `backend/app/core/permission_catalog.py`
- `backend/app/models/data_exchange.py`
- `backend/app/services/data_exchange_confirm_service.py`
- `backend/app/services/identity_import_service.py`
- `backend/app/modules/academic_affairs/services/__init__.py`
- `backend/app/models/academic_affairs_registry.py`
- `backend/alembic/versions/**`
- TeachingTask ORM 若 formationMode 需要新增持久化字段：A 提合同/业务实现，INT 持迁移/共享注册 Owner。

## 4. A-W0 → A-W5 固定施工顺序

`A-W0 基线/碰撞冻结 → A-W1 Term Authority → A-W2 Course/Program 执行语义 → A-W3 TeachingTask Formation → A-W4 新学校导入 → A-W5 开学准备度/注册前置 → INT 回收 → B 同步合同`

禁止重排成新路线；每个 Wave 只在 exact-head 上继续。

## 5. Wave 读取地图与输出 Contract

### A-W0 — 基线与碰撞冻结
必须读：当前 `main` / A exact HEAD；PR #96/#132/#133 changed files；历史教务总控；路由聚合；Alembic heads；A 独占服务与测试。

输出：Collision Ledger、File Owner Matrix、dirty-data inventory、Frontend Impact Matrix 初版。

### A-W1 — Term Authority
必须读：A-P0-01/A-P0-02、Term/Calendar/TimeSlot 附录；`AaTerm`、核心教务 service、term workspace、term calendar/detail router、Task generation、SYS-12 AcademicCalendarGovernance、相关 tests。

施工顺序：
1. MySQL 双管理员 current-term RED；
2. 所有正式 writer 同租户串行；
3. SYS-12 ACTIVE 与 AaTerm current 统一边界；
4. public current resolver dirty-data fail-closed；
5. 18 周正式兜底 RED→GREEN；
6. 17/20 周真实学校 Gold；
7. UI 同步 + screenshot + real-click E2E。

输出：`A-C1 Term Context Contract`。

### A-W2 — Course / Program
读取 A-P0-03、Course/Program 附录；`AaCourse/AaProgram/AaProgramCourse/AaProgramBinding`、Program Governance、Task Generation、Graduation 读取链及 tests。

输出：`A-C2 Course Identity Contract`、`A-C3 Program Execution Contract`。

### A-W3 — TeachingTask Formation
读取 A-P0-04；TeachingTask model/service/generation、TeachingClass、TeachingRoster、Task Workbench、tests。

冻结：`ADMIN_FIXED / SELECTABLE / MERGED / RETAKE / LAYERED`；禁止新建 OpeningPlan。

输出：`A-C4 TeachingTask Formation Contract`。

### A-W4 — 新学校导入
读取 A-P0-05；Academic File Exchange service/router、公共 Data Exchange（只读理解）、migration import、Course/Program service、FileObject、XLSX tests。

只扩展现有 Academic File Exchange：Course Catalog Import + Program Import；共享 Data Exchange/Alembic 变化提交 INT。

输出：`A-C5 School Setup Contract`。

### A-W5 — School Setup Readiness / Registration 前置
读取 A-P1-06；`AaRegistration/AaRegistrationBatch`、eligibility_status、canonical `register_student` writer、roster registration、Opening Differences、UnifiedTodo。

先画 writer 调用图，再确定学校级 policy；只做 readiness/read projection，不复制 Selection 资格规则。

## 6. A-W1 当前 exact-head CURRENT FACT

### 6.1 Current-term 写侧
已确认正式写入口至少五类：
1. `academic_affairs_service.set_current_term()`；
2. `academic_affairs_service.publish_term()`；
3. `academic_affairs_service.publish_calendar()`；
4. `migration_import_service._persist_term(isCurrent=true)`；
5. `academic_calendar_service.transition(... ACTIVE)` → `_sync_academic_current_term()`。

其中第5类 exact-head 使用 bulk update，天然绕过 `AaTerm.is_current` attribute event，因此 A-W1 不能只封前三/四个页面 writer。

当前实现：
- 复用真实 `Tenant` 行作为每租户协调锁；
- `AaTerm.is_current=True` 正式 ORM writer 在接受赋值前取同一租户 `FOR UPDATE`；
- SYS-12 `AcademicCalendarGovernance.active_key=ACTIVE` 同样先取同一租户协调锁；
- 已存在 ACTIVE governance term 时，教务 writer 不得把另一个 term 设 current，返回 `TERM_CONTEXT_CONFLICT`；
- 同事务写多个 current fail-closed；
- 邻租户不互相清 current。

### 6.2 Current-term 读侧 / 双 Authority 发现
exact-head 发现：
- SYS-12 `academic_calendar_service.resolve_current()` 声明全系统当前学期唯一入口，并以 `(tenant_id, calendar_type, active_key)` 唯一约束保证至多一个 ACTIVE；
- 教务 `/terms/current` 历史仍直接读 `AaTerm.is_current.first()`；
- `CALENDAR_CONSUMERS` 虽把教务标为 `wired=True`，代码搜索只发现 system API 真正直接调用 `resolve_current()`，因此该 wired 标记不能当接线证据。

A-W1 当前裁决：
- 公开 `/terms/current` 优先消费 SYS-12 ACTIVE governance；
- 尚未纳入 SYS-12 的历史学校保留 strict legacy fallback；
- legacy fallback 多 current 必须 `DATA_CONFLICT`，禁止 `.first()` 随机选；
- governance ACTIVE 指向的 term 缺失/跨租户时 fail-closed；
- 这是兼容式 REWIRE，不新增第二学期真值。

### 6.3 Teaching weeks
- 历史正式 Task writer 的 `_FALLBACK_WEEKS = 18` 已删除；
- 可证明来源保留：`term.teaching_weeks` → `exam_week_start-1` → TEACHING 校历事件 → 完整 term date range；
- 都无法证明时正式生成返回 `DATA_CONFLICT + TEACHING_WEEKS_UNRESOLVED`；
- 17周/20周已有明确 targeted contract；
- 根据完整日期推导出恰好18周属于真实事实，不等于硬编码18周兜底。

### 6.4 真实 CI 历史红灯
早期 exact-head `ccd1b8bb...`：
- CI backend targeted：`4 failed, 47 passed`；四条新 current 测试因 worker thread monkeypatch 错 facade `_tid`，属于 TEST_CONTEXT_RED；
- Main full regression shard：`5 failed, 1113 passed, 3 skipped`；除上述四条外，另有 isolated ORM fixture 因无 Tenant 父行被新生产锁误伤，属于真实 regression。

已修：
- 测试改为 patch canonical `academic_affairs_service` module；
- 正式 writer fixture 创建真实 Tenant；
- transient orphan ORM fixture 保持兼容，但已持久化正式 writer 无 Tenant 仍 fail-closed。

最新 A-W1 HEAD 在本地图刷新前为 `eaa4b466...`，对应 CI 尚 queued/in-progress，禁止写 GREEN。

## 7. 独立施工 / 等待关系

### A 可独立施工
- A 独占 service 的 RED、resolver、projection、业务校验、targeted tests。
- 不需要新共享字段的 UI/DTO 同步。
- 前端消费者盘点、截图/E2E 用例与现有 Authority 对账。

### 必须等待/移交 INT
- formationMode 新持久化字段及 Alembic。
- Permission Catalog / common permissions。
- public route registration。
- Academic services/model registry。
- public Data Exchange / identity import schema 或 writer。

### 对 B/C/D 的合同边界
- B 在 `A-C4` 冻结后才能把 Selection/Roster 最终语义绑定到 formationMode。
- C/D 只消费 A-C1/A-C2/A-C3/A-C4 的 stable ID / resolver，不得自行按名称、行政班或状态名重解释。
- A 不写 B 的 Selection/正式课表，不写 C 的 Attendance/Exam/Grade，不写 D 的 Graduation/Archive Authority。

## 8. Frontend Impact Matrix

| Backend Change | API/DTO | Consumer | UI Change | Screenshot | Real Click | Status |
|---|---|---|---|---|---|---|
| A-C1 current resolver | `/terms/current` | 学期列表/详情/工作区；教师/学生 current-term 消费者 | governance ACTIVE 优先，legacy 双 current 不随机选 | W1 必须 | W1 必须 | BACKEND_IN_PROGRESS |
| teachingWeeks fail-closed | Task generation preflight | 新建学期/教学周配置/Task 工作台/准备度 | 不默认18周；显示真实 blocker + howToResolve | W1 必须 | W1 必须 | UI_IMPLEMENTED_VISUAL_OPEN |
| Program activation resolver | Program/Opening/Task/Graduation read | 培养方案治理/Task 预检/毕业只读提示 | PUBLISHED/ENABLED/FROZEN 解释统一 | W2 必须 | W2 必须 | OPEN |
| formationMode | TeachingTask DTO | Task Workbench + B downstream | 中文人话：固定行政班/自主选课/合班/重修/分层 | W3 必须 | W3 必须 | OPEN |
| Course/Program import | Academic File Exchange | 导入工作区 | 上传→扫描→预检→错误→确认→回读→重跑 | W4 必须 | W4 必须 | OPEN |
| readiness/registration policy | readiness/registration projection | 开学准备度/注册资格/批次 | blocker 可下钻，只修源事实清零 | W5 必须 | W5 必须 | OPEN |

A-W1 UI exact-head 审计：
- `AaTeachingWeekConfigView.vue` 没有 18 周默认值；
- `AaTaskBatchListView.vue` 已透传生成失败消息，并明确“不会猜测生成”；
- `AaTermFormView.vue` 已把“如18”改成“按学校校历填写，如17或20”，并说明无法可靠推导时会阻断正式任务生成；
- `AaTermDetailView.vue` 仍有“未配置教学周显示0”的展示欠账，待本 Wave 后续 UI 收口；
- screenshot / real-click 尚未完成，所以 W1 不能标 COMPLETED。

## 9. UI / Screenshot / Real-click 硬门

只要 Wave 影响 UI：
1. 改前 capture baseline；
2. 真实前后端数据重新截图；
3. 打开截图逐张视觉检查；
4. 修视觉问题后重截图；
5. 浏览器按可见控件真实点击，不以 API-only 代替；
6. refresh/relogin 后确认持久事实；
7. console 0 error；正式网络 fake mock=0；
8. 证据绑定 exact HEAD / route / role / tenant / viewport / fixture / run/job。

后端绿但 UI 未闭环时只能标 `BACKEND_GREEN_UI_OPEN`，不得标 COMPLETED。

## 10. Dirty-data / Runtime Evidence

GitHub connector 本身不提供生产 MySQL 交互会话，因此不得伪造生产脏数据统计。

- 生产 current-term 多 current 实际行数：`UNMEASURED_PRODUCTION_MYSQL_REQUIRED`
- 生产 governance ACTIVE / AaTerm current mismatch：`UNMEASURED_PRODUCTION_MYSQL_REQUIRED`
- Program 双 active 实际行数：`UNMEASURED_PRODUCTION_MYSQL_REQUIRED`
- TeachingTask 重复批次/异常周数实际行数：`UNMEASURED_PRODUCTION_MYSQL_REQUIRED`
- 跨租户异常引用：`UNMEASURED_PRODUCTION_MYSQL_REQUIRED`

CI 的真实 MySQL fixture 只作为并发/合同证明，不能冒充生产数据 inventory。

## 11. 每批固定循环

`读 Wave 文档 → exact-head 源码 → CURRENT FACT → RED → 最小完整生产修复 → targeted tests → MySQL（如涉及） → Frontend Impact Review → UI 同步 → before/after screenshot → 实际打开截图视觉识别 → real-click E2E → refresh/relogin → KEEP regression → exact-head evidence → 更新本地图 → 下一安全 Wave`

## 12. Evidence Log

### 2026-08-16 / A-W0 开工
- main 开工 HEAD：`414216c4...`
- A branch from exact main：YES
- PR #96/#132/#133 + #112/#113：完成首轮 collision freeze
- `_FALLBACK_WEEKS = 18`：CURRENT FACT CONFIRMED

### 2026-08-16 / A-W1 第一轮
- `4f79b29a...`：current-term MySQL RED；
- `ccd1b8bb...` 真实 CI 暴露 test-context + orphan fixture regression；
- `acc48fd8...` / `a0a4553...`：修复上述两类问题；
- `1f75a81c...`：A V2.1 总册原文完整入枝；
- `5e964a98...`：18周正式兜底 RED；
- `dfe92e09...`：正式 Task writer 删除硬编码18周 fallback；
- `04fed2e0...`：新建学期 UI 改成真实周数语义；
- `5d9d75c6...`：SYS-12 ACTIVE 与 AaTerm current 共用租户协调锁，禁止 active governance 下旁路切另一学期；
- `f95f4595...`：公开 current-term resolver governance-first + strict legacy fallback；
- `eaa4b466...`：补治理激活并发、治理优先、legacy 双 current fail-closed MySQL 合同；
- `eaa4b466...` 对应最新 CI：queued/in-progress，尚无 GREEN 结论。

下一施工入口：`收 eaa4b466 exact-head 真红灯 → 修真实失败 → 补 AaTerm详情“未配置≠0” → current-term 消费者对账 → A-C1 Contract Freeze → W1 screenshot/real-click → 再进入 A-W2`。
