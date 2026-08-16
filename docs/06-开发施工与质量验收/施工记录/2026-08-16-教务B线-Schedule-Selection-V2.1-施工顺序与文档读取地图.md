# 2026-08-16 教务 B 线 Schedule / Selection V2.1 施工顺序与文档读取地图

> 固定仓库：`penghaibin9/saas`  
> 固定分支：`agent/academic-b-schedule-selection`  
> Draft PR：`#146`  
> 唯一施工总册：`docs/06-开发施工与质量验收/施工总册/B_教务Schedule_Selection_当前代码精确施工总册_V2.1_20260816.md`  
> 用户原始总册 SHA-256：`b78af9dbdc1da5067a7cd1fc05e32f1121d5662e9661bc6f46eb4d7dc0d02999`  
> branch create base：`414216c4a79ff035aee87d70b35572572f5c0535`  
> Contract Freeze 时 main：`457dc8821876b8e1b67e0fb5911a9eec33e37616`  
> W6 exact code/evidence HEAD：`6fc6bbaed7c8ef07e5d8ae3d12e41c726fdc0452`

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
- 为死锁预造通用 retry；
- force push；
- 未经明确授权合并 main。

## 2. exact-head 与 Collision Ledger

| 对象 | 当前观察 | B 线裁决 |
|---|---|---|
| `main` | `457dc8821876b8e1b67e0fb5911a9eec33e37616` | 已较 branch base 前进；不擅自 merge main |
| B | W6 exact code/evidence `6fc6bbaed7c8ef07e5d8ae3d12e41c726fdc0452` | W6 已满足 Contract Freeze 证据 |
| PR #132 | 已合入 main | `414216c4 → 457dc882` 与 PR #146 当前 71 个 changed paths 无直接同路径重叠；公共路由/迁移仍归 INT |
| PR #133 | Control Plane / INT 共享面 | permissions / Data Exchange / identity / route / Alembic 为 INT 禁区 |
| PR #145 | A — Semester/Core V2.1 | A-C1～A-C4 只消费正式冻结输出；formationMode 未冻结前不自造枚举 |
| PR #146 | Draft，mergeable=true | B 独立合同冻结；不合 main、不 force |

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

## 4. A 输入依赖与 B 输出合同

### A 输入依赖

| Contract | 当前状态 | B 规则 |
|---|---|---|
| A-C1 Term Context Contract | upstream owner | 只消费正式 termId，不猜新合同 |
| A-C2 Course Identity Contract | upstream owner | 只使用稳定 course id/code |
| A-C3 Program Execution Contract | upstream owner | 资格需要时只消费正式输出 |
| A-C4 TeachingTask Formation Contract | upstream/INT open | taskId/course/term/READY 已独立 fail-closed；formationMode 合法枚举等待正式冻结，不自造 |

### B 输出合同

| Contract | 状态 | 当前冻结事实 |
|---|---|---|
| B-C1 Published Schedule Contract | `FROZEN` | 当前正式课表只认 ScopeHead active batch；不回退 legacy EFFECTIVE |
| B-C2 Selection Eligibility Contract | `FROZEN` | EffectiveGrade + StudentAcademicFact + ScopeHead；坏规则 fail-closed；Command 同事务重验 |
| B-C3 Student Selection Projection Contract | `FROZEN` | `status/statusLabel/phase/eligibility/allowedActions/reason/howToResolve/window/lottery/reselect`；PC/miniapp 只消费服务器 allowedActions |

## 5. Wave 当前封板状态

### B-W0 — 强底座回归冻结
- `ScopeHead` 是正式课表唯一头；换版使用版本/SUPERSEDED。
- TeachingRoster 存在 Selection 关系时不回退行政班；未 final fail-closed。
- `Selection LOCK → TeachingRoster` 同事务投影正式名单。

状态：`COMPLETED`。

### B-W1 — SelectionPreflight 纯化
- malformed rule/scope/prerequisite JSON fail-closed；
- validator 0 commit；
- 单拒绝单审计；
- SelectionPreflight pure-read；
- admin → student PC → miniapp focused real-click；5 张 Gold 视觉 PASS。

状态：`COMPLETED @ 0aa85d17`。

### B-W2 — Authority consumer replacement
- `AcademicGrade/name → EffectiveGrade Provider`；
- `EFFECTIVE rows → ScopeHead active batch Provider`；
- 无 ScopeHead 不回退、双 active task fail-closed；
- fresh MySQL targeted Run `31928378623` success。

状态：`COMPLETED @ 971d5fa9`。

### B-W3 — 排课管理 PC Task-first
- READY TeachingTask-first；course/teacher/class 只读带出；显式 taskId；
- 周次来自 Task/Term，移除固定 18 周；
- textarea CSV writer 退出正式主路径，批量导入走 Academic File Exchange XLSX；
- focused browser Run `31930601841` / job `95124664211` success；4 张 Gold PASS。

状态：`COMPLETED @ 00dddd76`。

### B-W4 — Selection batch/course identity
已完成 B 独立子封板：
- SelectionCourse 正式 POST 要求 `teachingTaskId`；
- TeachingTask 必须存在且 READY；
- Task.courseId == SelectionCourse.courseId；
- TeachingTaskBatch.termId == SelectionBatch.termId；
- 管理 PC READY Task-first，身份字段只读；
- focused browser 最终 Run `31935498739` / job `95136602282` at `8e970f8a` success；4 张最终截图 PASS。

仍开放给 upstream/INT：
- `formationMode` 合法合同等待 A-C4 正式冻结；
- term/window/scope/rule 独立 version/hash 与 DB constraint 的 schema/Alembic 部分由 INT 单 Owner。

状态：`TASK_IDENTITY_BROWSER_SUBSEAL_COMPLETED / FULL_W4_UPSTREAM_INT_OPEN`。

### B-W5 — Student Selection Projection / B-C3
- Final Selection Owner 使用单一 evaluator；list/preflight 共用纯读资格决策；Command 持锁重验；
- Student PC / miniapp 不再本地计算资格，只渲染 VIEW/ENROLL/DROP；
- browser Run `31939849884` / job `95147335347` success；6 张 Gold PASS；
- terminal-state MySQL Run `31940339930` / job `95148472722` success，覆盖 OPEN/SELECTED/FULL/RESELECT/PENDING_LOTTERY/LOTTERY_LOST/COURSE_CANCELLED/LOCKED；
- W6 admission 改动后恢复 affected-path gates，并在 `b534e291` 重验：source `31945824884`、MySQL `31945824813`、browser `31945824949` 全 success。

状态：`COMPLETED / B-C3 FROZEN`。

### B-W6 — MySQL 高峰与并发封板

#### W6-1 FCFS peak
- 128 last-seat：最后 1 名额只允许 1 成功，其余业务性满额；
- 1k burst：20 门 × 50 容量，1000 请求全持久化、无超卖/重复/丢写；
- 首轮暴露 production QueuePool exhaustion；未扩大测试连接池假绿；
- production fix 使用 DB checkout 前 process-local admission/backpressure，MySQL 继续作为最终容量 Authority；
- Run `31942196454` / job `95152888348` at `270786d5`：exact-head、clean MySQL、唯一 W6-1 contract、JUnit 全 success。

#### W6-2 LOCK/drop lock order
- RED Run `31946102898` at `5a003d92`：clean MySQL + exact-head 成功，真实触发 MySQL `1213 Deadlock found when trying to get lock`；
- 根因：`lock_batch` 的 `batch→record` 与旧 `student_drop` 的 `record→batch` 形成环形等待；
- 修复：`student_drop` 统一为 `course→batch→record`，保留 record-not-found 拒绝优先级；不增加 generic retry；
- 首轮 GREEN Run `31946625351` at `22dac089` success；
- W6-3/W6-4 后 `final_service.py` 再变化，因此补 exact-current-head 重验；
- 最终 Run `31950976921` / job `95174265400` at `6fc6bbae`：exact-head、clean MySQL、真实 LOCK/drop race、JUnit 全 success；最终状态 `batch=LOCKED / record=LOCKED / selectedCount=1`，DROP 业务性拒绝，无 1213。

#### W6-3 Lottery concurrency
- 双管理员同时 draw 同一 CLOSED Lottery：严格 1 success + 1 HTTP 409，不可重摇；
- 最终 `DRAWN / selectedCount=1 / [LOTTERY_LOST, SELECTED]`；
- CLOSED 待开奖不得从 list/preflight/command 任一层回落 legacy FCFS；
- Run `31947630586` / job `95166066035` at `5050ea41`：exact-head、clean MySQL、唯一 W6-3 contracts、JUnit 全 success。

#### W6-4 Selection↔TeachingRoster reconcile + neighbor tenant
- LOCKED student set / TeachingRoster studentIds / memberCount / rosterHash 必须一致；
- 人工篡改 roster version memberCount/hash 后 resolver 必须 `APPROVAL_VERSION_CONFLICT 409` fail-closed；
- 邻租户使用相同 batch/course 整数 ID 写入 LOCKED 哨兵记录，不得污染本租户 resolver；
- Run `31947845802` / job `95166595705` at `948764ca`：exact-head、clean MySQL、唯一 W6-4 contracts、JUnit 全 success；
- `948764ca → 6fc6bbae` 仅 W6-2 workflow 注释变化，W6-4 生产/测试树等价 carry-forward。

#### W6-5 deadlock/retry 裁决
- 真实 1213 已由 W6-2 RED 证明；根因是可消除的反向锁序；
- 当前 Selection 不含 1213 特判、OperationalError retry loop 或 generic retry；
- 裁决：`NO_GENERIC_RETRY`。继续以统一锁序 + MySQL Authority + targeted real race 作为正式合同。

状态：`COMPLETED @ code/evidence HEAD 6fc6bbae`。

## 6. Frontend Impact Matrix

| Backend Change | Consumer | UI / Evidence | 状态 |
|---|---|---|---|
| W0 Authority baseline | Schedule/Roster consumers | 无 DTO 变化 | COMPLETED |
| W1 Preflight blockers | 管理 PC + Student PC + miniapp | 5 Gold + real-click | COMPLETED |
| W2 EffectiveGrade/ScopeHead | Selection eligibility/conflict | 无 DTO 变化 | COMPLETED |
| W3 Task-first schedule writer | AaScheduleMaintainView | 4 Gold + real-click | COMPLETED |
| W4 Task-bound SelectionCourse | AaSelectionConsoleView | 4 Gold + real-click | B independent subseal completed |
| W5 Student Projection | Student PC + miniapp | 6 Gold + cross-client real-click | COMPLETED |
| W6 concurrency hardening | Command/runtime only | W5 source/MySQL/browser affected-path regression all success | COMPLETED |

## 7. Evidence Ledger

| Evidence | Exact HEAD | Result |
|---|---|---|
| branch creation main baseline | `414216c4` | historical baseline |
| Contract Freeze observed main | `457dc882` | PR #132 already merged; no direct path collision with #146 current changed paths |
| W0/W1 authority + cross-end | `0aa85d17` | MySQL + real-click + 5 Gold PASS |
| W2 EffectiveGrade/ScopeHead | `971d5fa9` | Run `31928378623` success |
| W3 focused browser | `00dddd76` | Run `31930601841`, job `95124664211` success |
| W4 final browser evidence | `8e970f8a` | Run `31935498739`, job `95136602282` success |
| W5 browser | `3b2c26a0` | Run `31939849884`, job `95147335347` success |
| W5 terminal-state MySQL | `33886a0a` | Run `31940339930`, job `95148472722` success |
| W5 post-W6 regression source | `b534e291` | Run `31945824884` success |
| W5 post-W6 regression MySQL | `b534e291` | Run `31945824813` success |
| W5 post-W6 regression browser | `b534e291` | Run `31945824949` success |
| W6-1 peak | `270786d5` | Run `31942196454`, job `95152888348` success |
| W6-2 RED | `5a003d92` | Run `31946102898`: real MySQL 1213 |
| W6-2 current-head GREEN | `6fc6bbae` | Run `31950976921`, job `95174265400` success |
| W6-3 Lottery | `5050ea41` | Run `31947630586`, job `95166066035` success |
| W6-4 roster reconcile | `948764ca` | Run `31947845802`, job `95166595705` success; relevant tree unchanged through 6fc6bbae |

## 8. B Contract Freeze 与 C handoff

B 独立范围正式冻结：
1. Published Schedule 只认 `ScopeHead active batch`；
2. Selection eligibility 只认正式 term / TeachingTask / StudentAcademicFact / EffectiveGrade / ScopeHead；
3. Student Selection UI 只认服务端 B-C3 projection / allowedActions；
4. Selection 最终名单只通过 `CLOSED→LOCKED` 投影到 versioned TeachingRoster；
5. TeachingRoster 的 student set/memberCount/hash 必须自洽，摘要漂移 fail-closed；
6. Selection Command 的并发 Authority 在 MySQL，进程内 admission 只做背压，不代替数据库裁决；
7. 锁序以真实 MySQL race 证明并固定；不引入通用 deadlock retry。

### 给 C 线的唯一消费通知

C（Teaching Execution）从此只消费正式、版本化 `TeachingRoster`：
- 不直接把 `AaSelectionRecord` 当教学执行名单；
- 存在 Selection 关系时不得回退行政班名单；
- roster 未 ready / version/hash/memberCount 不一致时 fail-closed；
- 考勤、考务、成绩等冻结型消费者必须记录/校验 roster version/hash/memberCount。

## 9. 仍开放但不阻断 B 独立 Contract Freeze 的项

- W4 `formationMode` 合法枚举：等待 A-C4 正式冻结；
- term/window/scope/rule 独立 version/hash 与 DB constraint：schema/Alembic 交 INT；
- main 已前进到 `457dc882`：最终集成时由 INT 做共享文件/迁移头/权限/路由的同步与 Gold 验收；B 不自行 merge main。

状态：`B_CONTRACT_FREEZE_COMPLETED_WITH_UPSTREAM_INT_OPEN`。

## 10. 下一入口

B 线不再扩功能；Waitlist / Swap / Saved Schedule / Reserve Capacity（候补/换课/保存课表/定向容量）继续后置。

下一入口固定为：
`INT/C handoff → C 只消费正式 TeachingRoster → upstream A-C4/INT 开放项补齐 → integration exact-head Gold`。
