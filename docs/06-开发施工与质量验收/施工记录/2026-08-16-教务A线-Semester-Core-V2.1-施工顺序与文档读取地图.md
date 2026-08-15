# 教务 A 线 Semester/Core V2.1 施工顺序与文档读取地图

> 固定分支：`agent/academic-a-semester-core`
> 唯一当前施工依据：`A_教务Semester_Core_当前代码精确施工总册_V2.1_20260816.md`
> 原则：current exact-head 代码事实 > V2.1 当前裁决 > V1.5 附录 > 历史设计。
> 禁止：未经明确授权合并 `main`、force push、skip/xfail/ignore、SQLite 代替 MySQL 并发证据、抢占 INT 共享文件 Owner。

## 1. Exact-head 开工事实

- `main` exact HEAD：`414216c4a79ff035aee87d70b35572572f5c0535`
- A 分支创建基线：`414216c4a79ff035aee87d70b35572572f5c0535`
- A 分支第一笔提交：本施工地图；提交后以 GitHub 返回的新 exact HEAD 继续记录。
- 当前状态：`A-W0_IN_PROGRESS`

## 2. Open PR Collision Ledger

### PR #96 — `agent/academic-static-closure-20260811`
- 状态：OPEN / DRAFT；当前 `mergeable=false`。
- 直接碰撞：教务服务注册、教务模型注册、教师小程序成绩录入等既有收口面。
- A 线裁决：不覆盖其共享注册语义；A 独占 service 改动必须做语义级对账，不能整树覆盖。

### PR #132 — `agent/internship-enterprise-collaboration-v3-20260814`
- 状态：OPEN / DRAFT；base 为当前 `main@414216c4`。
- 直接碰撞：公共 `route_registration.py`，并涉及大量横切模型/测试。
- A 线裁决：公共路由不由 A 修改；若 A 新 endpoint 需要公共注册，交 INT 回收。

### PR #133 — `integration/control-plane-option-b-20260815`
- 状态：OPEN / DRAFT；base 为当前 `main@414216c4`。
- 直接碰撞：Permission Catalog、Data Exchange、identity import、公共 route registration、Alembic 等共享面。
- A 线裁决：A-W4 只实现 Academic File Exchange 业务适配器和本线合同；公共 Data Exchange / identity / migration / permission 变化全部交 INT。

### 开工时其他相关开放 PR
- #112 `refactor(platform): split platform control plane and implement Option B`：共享 Permission/Alembic/route-registration 风险，A 只监控，不抢 Owner。
- #113 `refactor(system): split school system control plane and implement Option B`：共享 Permission/Alembic/route-registration 风险，A 只监控，不抢 Owner。

## 3. File Owner Matrix

### A 独占业务面
- `backend/app/modules/academic_affairs/services/academic_affairs_term_workspace_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_program_governance_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py`
- `backend/app/modules/academic_affairs/services/academic_affairs_task_service.py`
- A 线对应 PC / portal / miniapp 消费者和 targeted tests（实际路径开工时以 exact-head 为准）。

### A 只读复用，不重写 Authority
- `academic_affairs_teaching_roster_service.py`
- `academic_affairs_schedule_truth_service.py`
- `academic_affairs_effective_grade_policy_service.py`
- `academic_affairs_graduation_immutable_service.py`

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
- `backend/app/modules/academic_affairs/models/academic_affairs_task.py` 或同语义 TeachingTask ORM 文件若 formationMode 需要持久化字段：A 提合同/业务实现，INT 持迁移/共享注册 Owner。

## 4. A-W0 → A-W5 固定施工顺序

`A-W0 基线/碰撞冻结 → A-W1 Term Authority → A-W2 Course/Program 执行语义 → A-W3 TeachingTask Formation → A-W4 新学校导入 → A-W5 开学准备度/注册前置 → INT 回收 → B 同步合同`

禁止重排成新路线；每个 Wave 只在 exact-head 上继续。

## 5. Wave 读取地图与输出 Contract

### A-W0 — 基线与碰撞冻结
必须读：
1. 当前 `main` / A exact HEAD；
2. PR #96/#132/#133 changed files；
3. 教务历史总控设计；
4. `academic_affairs_bundle.py` 或当前等价教务路由聚合；
5. Alembic 当前 heads / 并行 lineage；
6. exact-head A 独占服务与测试。

输出：Collision Ledger、File Owner Matrix、dirty-data inventory、Frontend Impact Matrix 初版。

### A-W1 — Term Authority
必须读：A-P0-01/A-P0-02、Term/Calendar/TimeSlot 附录；`AaTerm`、核心教务 service、term workspace、term calendar/detail router、Task generation、相关 tests。

先做：真实 MySQL 双管理员同时 set-current RED；随后修唯一 current；再做“无法确定教学周时正式 Task 禁止 18 周猜测”的 RED→GREEN。

输出：`A-C1 Term Context Contract`。

### A-W2 — Course / Program
必须读：A-P0-03、Course/Program 附录；`AaCourse/AaProgram/AaProgramCourse/AaProgramBinding`、Program Governance、Task Generation、Graduation 读取链及 tests。

输出：`A-C2 Course Identity Contract`、`A-C3 Program Execution Contract`。

### A-W3 — TeachingTask Formation
必须读：A-P0-04；TeachingTask model/service/generation、TeachingClass、TeachingRoster、Task Workbench、tests。

冻结：`ADMIN_FIXED / SELECTABLE / MERGED / RETAKE / LAYERED`；禁止新建 OpeningPlan。

输出：`A-C4 TeachingTask Formation Contract`。

### A-W4 — 新学校导入
必须读：A-P0-05；Academic File Exchange service/router、公共 Data Exchange（只读理解）、migration import、Course/Program service、FileObject、XLSX tests。

只扩展现有 Academic File Exchange：Course Catalog Import + Program Import；共享 Data Exchange/Alembic 变化提交 INT。

输出：`A-C5 School Setup Contract`。

### A-W5 — School Setup Readiness / Registration 前置
必须读：A-P1-06；`AaRegistration/AaRegistrationBatch`、eligibility_status、canonical `register_student` writer、roster registration、Opening Differences、UnifiedTodo。

先画 writer 调用图，再确定学校级 policy；A-W5 只做 readiness/read projection，不复制 Selection 资格规则。

输出：`身份 → 学期 → 课程 → 方案 → Task → blockers` 只读准备度投影，并移交 INT/B。

## 6. 当前 exact-head CURRENT FACT（A-W0 首轮）

### Term current
- `set_current_term()` 当前仍采用“读取目标 → 清理其他 `is_current=true` → 目标置 true → commit”的多行切换。
- 当前模型已知唯一约束是租户+学年+学期序号；尚无“每租户只能一个 current”的数据库级证明。
- 裁决：A-W1 必须以真实 MySQL 双连接并发 RED 开始，不能用 UI 防抖冒充 Authority 修复。

### Teaching weeks
- Task generation exact-head 仍存在 `_FALLBACK_WEEKS = 18`。
- 正式 Task 生成无法可靠解析教学周时仍可能落到 18 周兜底。
- 裁决：正式 writer 必须 fail-closed；17 周/20 周学校分别按真实学期结构生成，不能猜 18 周。

### Program activation
- 开工检查项：Program Governance 与 Task Generation 的 active 状态解释存在需要统一的风险；A-W2 必须基于 exact-head 重新锁定唯一 resolver，不在 W0 先改。

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
| current term 唯一性 / A-C1 | term workspace/current-term consumers | 学期列表/详情/工作区；教师/学生 current-term 消费者 | 默认学期只能来自 A-C1，禁止本地另算 | W1 必须 | W1 必须 | OPEN |
| teachingWeeks fail-closed | Task generation preflight | 学期/Task 工作台/开学准备度 | 不再默认18周；显示真实 blocker + howToResolve | W1 必须 | W1 必须 | OPEN |
| Program activation resolver | Program/Opening/Task/Graduation read | 培养方案治理/Task 预检/毕业只读提示 | PUBLISHED/ENABLED/FROZEN 解释统一 | W2 必须 | W2 必须 | OPEN |
| formationMode | TeachingTask DTO | Task Workbench + B downstream | 中文人话：固定行政班/自主选课/合班/重修/分层 | W3 必须 | W3 必须 | OPEN |
| Course/Program import | Academic File Exchange | 导入工作区 | 上传→扫描→预检→错误→确认→回读→重跑 | W4 必须 | W4 必须 | OPEN |
| readiness/registration policy | readiness/registration projection | 开学准备度/注册资格/批次 | blocker 可下钻，只修源事实清零 | W5 必须 | W5 必须 | OPEN |

所有后端合同变化后，管理 PC / 教师 PC / 学生 PC / 教师 miniapp / 学生 miniapp 若存在消费者必须逐端登记；无消费者写 N/A + 理由。

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

## 10. A-W0 Dirty-data / Runtime Evidence

当前 GitHub 代码审计连接没有生产/测试 MySQL 会话，因此不得伪造 dirty-data 统计。

- current-term 多 current 实际行数：`UNMEASURED_MYSQL_RUNTIME_REQUIRED`
- Program 双 active 实际行数：`UNMEASURED_MYSQL_RUNTIME_REQUIRED`
- TeachingTask 重复批次/异常周数实际行数：`UNMEASURED_MYSQL_RUNTIME_REQUIRED`
- 跨租户异常引用：`UNMEASURED_MYSQL_RUNTIME_REQUIRED`

处理：A-W1 首个可执行 MySQL gate 必须先产出上述 inventory；在此之前 A-W0 的源码碰撞冻结可完成，但数据库事实不得写“0”。

## 11. 每批固定循环

`读 Wave 文档 → exact-head 源码 → CURRENT FACT → RED → 最小完整生产修复 → targeted tests → MySQL（如涉及） → Frontend Impact Review → UI 同步 → before/after screenshot → 实际打开截图视觉识别 → real-click E2E → refresh/relogin → KEEP regression → exact-head evidence → 更新本地图 → 下一安全 Wave`

## 12. Evidence Log

### 2026-08-16 / 开工
- main exact HEAD：`414216c4a79ff035aee87d70b35572572f5c0535`
- A branch created from exact main：YES
- PR #96/#132/#133：已复核 OPEN/DRAFT 与碰撞域
- 新增相关 PR：#112/#113 作为共享 control-plane 风险持续监控
- `set_current_term` 并发风险：CURRENT FACT CONFIRMED
- `_FALLBACK_WEEKS = 18`：CURRENT FACT CONFIRMED
- MySQL runtime dirty-data：未连接，禁止猜测
- UI change：本批仅控制文档，N/A
- Screenshot / real-click：本批无 UI 变化，N/A
- 下一入口：完成 Draft PR 后继续 A-W0 余项 → A-W1 MySQL current-term RED
