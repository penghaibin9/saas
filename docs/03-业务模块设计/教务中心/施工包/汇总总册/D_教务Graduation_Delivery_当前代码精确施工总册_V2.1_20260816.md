# 教务中心 ABCD（四线）当前代码精确审计最终施工总册 V2.1

> 仓库：`penghaibin9/saas`  
> 当前审计基线：`main（主分支）@414216c4a79ff035aee87d70b35572572f5c0535`  
> 日期：2026-08-16  
> 目标：不是补功能清单，而是把“真实学校完整学期”落实成四个可以并行长期施工的 AI（人工智能）施工总册。

## 一、最高优先级原则

1. 当前 `exact-head（精确提交头）` 代码事实 > V2.1 本轮裁决 > V1.5 详细设计 > 更早历史设计 > 外部成熟系统启发。
2. 已有成熟 `Authority（权威真值）` 只允许 `KEEP（保留）/HARDEN（加固）/REWIRE（重新接线）`，禁止再造第二套。
3. 四线允许并行，但 `INT（总集成线）` 从第一天存在并独占共享迁移、权限、公共路由、公共数据交换、服务注册。
4. 所有数据库并发、唯一约束、容量、名单换版、正式发布必须使用 `MySQL（关系型数据库）` 验收。
5. 禁止 `skip（跳过）`、`xfail（预期失败）`、`ignore（忽略）`、假数据、弱化断言制造假绿。
6. 未经明确授权不得合并 `main（主分支）`，不得 `force push（强制推送）`。
7. 每个英文技术词在本文第一次或主要出现时都附中文解释。

## 二、四线和 INT（总集成线）

- A（上游核心线）：学期、课程、培养方案、开课投影、教学任务、新学校基础数据。
- B（排课选课线）：正式排课、课表发布、Selection（选课）、TeachingRoster（正式教学名单）。
- C（教学执行线）：教师日常、考勤、调停课、考务、成绩、EffectiveGrade（有效成绩）。
- D（毕业交付线）：学分/毕业、Archive（归档）、评教规模、迁移、消息、恢复、R11（真实学校完整学期试点）。
- INT（总集成线）：只负责共享文件、跨线合同、迁移头、权限、路由和最终 Gold（最终验收基线），不发明第五套业务。

建议分支：
- `agent/academic-a-semester-core`（A线）
- `agent/academic-b-schedule-selection`（B线）
- `agent/academic-c-teaching-execution`（C线）
- `agent/academic-d-graduation-delivery`（D线）
- `integration/academic-school-gold`（INT总集成线）

共享单一 Owner（所有者）：
- `backend/app/api/v1/route_registration.py`（公共路由注册）
- `backend/app/core/permissions.py`（公共权限）
- `backend/app/core/permission_catalog.py`（权限目录）
- `backend/app/models/data_exchange.py`（公共数据交换模型）
- `backend/app/services/data_exchange_confirm_service.py`（公共数据交换确认）
- `backend/app/services/identity_import_service.py`（统一身份导入）
- `backend/app/modules/academic_affairs/services/__init__.py`（教务服务注册）
- `backend/app/models/academic_affairs_registry.py`（教务模型注册）
- `backend/alembic/versions/**`（数据库迁移）

当前碰撞重点：
- PR #96（教务静态收口拉取请求）：碰教务服务注册、模型注册、教师小程序成绩录入。
- PR #133（控制面拉取请求）：碰权限目录、统一数据交换、身份导入、学校初始化、公共路由、迁移。
- PR #132（横切基础设施拉取请求）：碰公共路由、学期基础、教务模型、学生学业事实、教学任务、文件对象和大量测试。

## 三、真实学校完整学期主链

`学校参数/身份 → 学期 → 课程 → 培养方案 → Opening Projection（开课投影） → TeachingTask（教学任务） → Schedule ScopeHead（正式课表头） → Selection（选课）/固定名单 → TeachingRoster（正式教学名单） → Attendance（考勤） → Exam（考务） → Grade（成绩） → EffectiveGrade（有效成绩） → Graduation（毕业） → Archive（归档） → R11（真实学校完整学期试点）`

## 四、专业人士七视角

每批施工完成前，必须从七个角度重新签字：
1. 教务处负责人：制度是否真实，异常能否处理。
2. 学院教务员：数据范围、批量工作、阻断责任人是否清楚。
3. 教师：今天的课、点名、监考、成绩是否高频顺畅。
4. 学生：状态、失败原因、下一步、两端一致性是否清楚。
5. 数据库架构师：唯一性、锁顺序、幂等、版本、历史、迁移是否安全。
6. 安全与运维：跨租户、跨学院、敏感数据、消息、恢复、监控是否可靠。
7. 测试负责人：RED（先失败测试）、MySQL（关系型数据库）、负向、并发、E2E（端到端）、刷新后持久性是否齐全。

## 五、成熟系统对照只作为制度校验

Oracle PeopleSoft（甲骨文高校学生记录系统）、Workday Student（Workday学生信息系统）、Ellucian（高校学生成功与规划系统）以及国内高校正方教务公开运行共同证明：真正成熟教务不是页面多，而是课程/计划/开课/排课/注册/名单/教学/考试/成绩/毕业/历史形成一条一致记录链；候补、换课、学业规划等高级能力必须建立在这条主链已经正确的前提上。

---



# 0A-D. D线一键开工总控提示词（直接复制到D施工窗口）

```text
@GitHub

你现在接管教务中心 V2.1 四线并行施工：

D — Graduation/Delivery（毕业与交付线）

仓库：
penghaibin9/saas

固定施工分支：
agent/academic-d-graduation-delivery

创建 Draft PR（草稿拉取请求），不合并 main（主分支），不 force push（强制推送）。

唯一当前施工总册：
《D_教务Graduation_Delivery_当前代码精确施工总册_V2.1_20260816.md》

D线目标不是再加几个毕业页面，而是把最终学校签字点从“看起来绿”变成“真实可证明”，并把后端结论同步到真实UI、截图和点击验收。

第一笔建立：

docs/06-开发施工与质量验收/施工记录/
2026-08-16-教务D线-Graduation-Delivery-V2.1-施工顺序与文档读取地图.md

记录：
main/D exact HEAD；
开放PR碰撞；
D Authority；
D-W0～D-W5；
每Wave文档/源码/测试；
A/B/C输入合同；
可提前施工/等待合同项目；
Graduation/Archive/R11 RED；
Frontend Impact Matrix；
截图视觉证据；
真实点击E2E；
MySQL规模；
Migration/Outbox/Restore；
clean tenant/migrated tenant；
exact-head学校证据；
下一入口。

先读本总册：
D-0
D-P0-01～D-P0-06
D-P1-07/D-P1-08
D-W0～D-W5
0B/0C-D
自行纠错
最终签字；
再按Wave读V1.5附录。

D-W0：
立即可施工，不依赖其他线。
读取 D-P0-01、毕业/学位/证据附录、毕业审核历史文档。
源码：
graduation_immutable_service
graduation_service
graduation evidence
decision trace
StudentAcademicFact
graduation models
test_aa_graduation
immutable history tests。
第一刀RED：
SYSTEM_ABNORMAL + 普通review_note + GRADUATED/COMPLETED 必须失败。
普通final只允许SYSTEM_PASSED。
如果学校真有特批，做独立正式Override（例外）流程。
冻结 D-C1 Graduation Decision Contract。
同步毕业审核UI：SYSTEM_ABNORMAL不能显示普通“确认毕业”；如果有Override必须明确区分NORMAL/OVERRIDE。
必须截图异常、正常、例外关键态并真实点击终审/阻断/刷新。

D-W1：
读取 D-P0-03、13-domain Archive附录、archive规则。
源码：
archive_domain_policy
archive core service
archive evaluator
ArchiveManifest
PostArchiveCorrectionCase
tests。
统一 PASS/BLOCKED/NOT_APPLICABLE/UNKNOWN。
UNKNOWN绝不PASS。
先修graduation domain termId/日期缺失，再扫其他域类似false-green。
冻结 D-C2 Archive Gate Contract。
同步Archive UI：UNKNOWN必须显示待治理/阻断，不得绿色；截图各状态并真实点击预检/下钻/归档阻断。

D-W2：
依赖A-C4和B TeachingRoster Contract。
未冻结时可先写RED/设计，不自造合同。
读取 D-P0-02/D-P1-08、R11附录、A-C4、B合同。
源码：
semester_pilot_service
semester_pilot_router
R11 models/tests。
建立 SCHEDULE_READY / ROSTER_PENDING_SELECTION / ROSTER_READY / DOWNSTREAM_READY。
ADMIN_FIXED PRE_TERM需名单；SELECTABLE PRE_TERM可等待选课，但进入IN_TERM前必须Roster ready。
冻结 D-C3 Semester Pilot Contract。
同步R11 UI：ROSTER_PENDING_SELECTION必须与错误缺名单视觉区分；每阶段截图必须能下钻真实blocker；真实点击阶段确认。

D-W3：
读取 D-P0-04/D-P1-07、evaluation peak/20K附录。
源码：
evaluation_public_service
Evaluation models
stats
archive policy
production audit guards
performance tests。
先真实MySQL同Task 50/100/200并发、多Task混合；采集p50/p95/p99、lock wait、deadlock、duplicate、submittedCount。
只有数据不达标才申请INT迁submission digest/unique。
若前端评价状态/截止/重复提交提示因合同变化，必须同步学生端/管理端UI并截图+真实点击提交。

D-W4：
读取 D-P0-05/D-P0-06、cutover/outbox/PITR/RPO/RTO附录、历史迁移设计、部署/备份/runbook。
依赖A-W4 Course/Program Import。
系统：
academic_file_exchange_service
migration_import_service
FileObject
Outbox
scheduler
storage
MySQL backup/binlog
deploy scripts。
建立Cutover Ledger：source/digest/initial/conflicts/final delta/T0/T+1/diff/owner/sign-off。
T0后新系统唯一writer，旧系统只读。
做真实隔离MySQL PITR和FileObject恢复。
若系统已有迁移/切换/交付工作台，必须同步后端新状态；截图失败/成功/待对账并真实点击。

D-W5：
等待A/B/C合同冻结。
读取A-C1～A-C5、B-C1～B-C3、C-C1～C-C3、D-C1～D-C3、R11、当前碰撞账本、部署恢复证据。
固定回放：
A → B → C → D → INT exact-head → R11 COMPLETED。
必须完成clean tenant Gold、migrated tenant Gold、20K、Permission negative、DataScope negative、cross-tenant sentinel、Outbox recovery、MySQL PITR、FileObject restore、R11 real data。
最终前端必须做管理端/教师端/学生端关键链截图识别和真实点击，不允许只以接口/CI说明学校可上线。

禁止：
SYSTEM_ABNORMAL靠普通备注毕业；
修改历史GraduationEvaluationRun；
覆盖DecisionFact；
UNKNOWN Archive当PASS；
为R11伪造SELECTABLE名单；
CI rehearsal代替真实R11；
业务Archive代替Backup/Restore；
只backup不restore；
T0后双写；
未压测就重构Evaluation正确性；
第二套Archive/Graduation truth；
skip/xfail/ignore；
SQLite代替MySQL；
force；
合并main。

固定循环：
文档 → exact-head源码 → CURRENT FACT → RED → 后端修根因 → targeted → MySQL/运维证据
→ Frontend Impact Review
→ UI同步
→ before/after截图
→ 打开截图做视觉识别
→ 修视觉问题并重截图
→ 真实浏览器可见控件点击E2E
→ refresh/relogin/跨角色
→ exact-head证据
→ 回写D施工地图
→ 下一安全Wave。

后端绿但UI/截图/真实点击未完成，只能标BACKEND_GREEN_UI_OPEN，禁止COMPLETED。

现在：
创建固定分支 → Draft PR → 写D线施工地图 → 立即D-W0。
```


# 0B. 四线统一硬门：后端 Contract（接口合同）变化必须同步前端 UI（界面）+ 截图识别 + 真实点击验收

> 本节对 A/B/C/D（四条施工线）的**每一个 Wave（施工波次）**生效。  
> 它不是建议项，而是 `Definition of Done（完成定义）`。  
> 只要本批后端正式合同变化后，任一受影响前端消费者尚未同步，或截图视觉复审/真实浏览器点击未完成，本批不得标记 `COMPLETED（完成）`。

## 0B-1. 后端变更后的固定影响链

任何下列内容发生变化：
- model（模型）
- schema（数据结构）
- status machine（状态机）
- Authority（权威真值）
- Contract（接口合同）
- permission（权限）
- dataScope（数据范围）
- allowedActions（允许动作）
- lifecycle（生命周期）
- validation（校验）
- projection（投影）
- DTO（数据传输对象）
- router/API（路由/接口）
- concurrency behavior（并发行为）
- error code（错误码）
- read-only / archived behavior（只读/归档行为）

都必须执行：

`backend model（后端模型）
→ canonical service（正式服务）
→ router/API（路由/接口）
→ response DTO（返回合同）
→ frontend API adapter（前端接口适配）
→ 管理 PC（管理电脑端）
→ 教师 PC（教师电脑端）
→ 学生 PC（学生电脑端）
→ 教师 miniapp（教师小程序）
→ 学生 miniapp（学生小程序）
→ help/operation guidance（帮助与操作指引）
→ screenshot visual audit（截图视觉识别复审）
→ real-click E2E（真实点击端到端）
→ exact-head evidence（精确提交头证据）`

只要该业务事实存在对应前端消费者，就必须进入影响矩阵；不存在的端必须写 `N/A（不适用）` 和原因，不能直接漏掉。

## 0B-2. 每个 Wave 必须维护 Frontend Impact Matrix（前端影响矩阵）

在本线“施工顺序与文档读取地图”中维护：

| Backend Change（后端变化） | API/DTO（接口合同） | Consumer（前端消费者） | UI Change（界面变化） | Screenshot（截图） | Real Click（真实点击） | Status（状态） |
|---|---|---|---|---|---|---|

每一个后端变更都必须回答：
1. 哪些页面读取这个字段/状态？
2. 哪些按钮由它决定显示、隐藏、禁用？
3. 哪些页面自己重复计算了后端业务规则？
4. 哪些旧字段/旧接口/legacy writer（历史写入口）必须退出正常路径？
5. 是否新增状态、阻断、只读态、下一动作？
6. 空态、错误态、归档态、无权限态是否要同步？
7. 管理 PC / 教师 PC / 学生 PC / 教师小程序 / 学生小程序是否存在同一事实消费者？
8. 帮助文案和操作引导是否已经过时？
9. 真实用户从首页/列表/详情/操作入口是否还能完成完整业务？

## 0B-3. 前端禁止复制正式业务规则

前端不得自行重新计算：
- 学生是否可选课；
- 教师是否可点名/录成绩；
- 当前是否允许退课；
- 是否允许锁名单；
- 是否允许发布；
- 是否允许毕业；
- 是否允许归档；
- 是否有权限；
- 是否属于当前正式学期；
- 是否属于正式教学名单；
- 是否属于正式课表；
- 是否满足先修/重修；
- 是否为当前有效成绩。

这些必须优先来自后端正式 projection（投影）：
- `status（状态）`
- `statusLabel（状态中文）`
- `phase（阶段）`
- `allowedActions（允许动作）`
- `blockers（阻断）`
- `reason（原因）`
- `howToResolve（解决方式）`
- `nextAction（下一步）`
- `readOnly（是否只读）`

前端负责**解释与交互**，不能发明第二套状态机。

## 0B-4. 新后端状态必须同批覆盖所有 UI（界面）语义

例如新增/收紧：
- PENDING_LOTTERY（待抽签）
- LOTTERY_LOST（未中签）
- COURSE_CANCELLED（课程停开）
- ROSTER_PENDING_SELECTION（等待选课名单）
- SYSTEM_ABNORMAL（系统异常）
- OVERRIDE_APPROVED（例外批准）
- NOT_APPLICABLE（不适用）
- UNKNOWN（未知）
- ARCHIVED（已归档）

必须同时检查：
- 中文状态；
- 状态标签/颜色；
- 首屏结论；
- 下一步；
- 可执行按钮；
- 禁用原因；
- 详情说明；
- 空态；
- 错误态；
- 筛选；
- 统计；
- 导出；
- 帮助；
- PC（电脑端）；
- miniapp（小程序）。

禁止后端已经新增正式状态，前端仍显示原始英文枚举或落入错误的 `default（默认）` 分支。

## 0B-5. 后端 writer（写入口）升级，旧 UI 写法必须同时退出正式路径

例如后端已经 TeachingTask-first（教学任务优先）：
前端不得继续用：
`课程 + 教师 + 班级 → 自由拼装 → 提交`

而必须改成：
`选择 TeachingTask（教学任务）
→ 课程/教师/对象只读回显
→ 只填写允许变化的业务参数
→ 提交正式 taskId（任务编号）`

legacy writer（历史写入口）如必须保留：
- 仅兼容历史；
- 正常 UI 不再入口；
- 必须有调用计量；
- 调用归零后再评估退役。

## 0B-6. UI（界面）设计同步不是“把字段塞上去”

每个受影响页面必须重新回答：
1. 用户打开页面第一眼应该看到什么结论？
2. 当前最重要 blocker（阻断）是什么？
3. 下一步是什么？
4. 当前为什么能/不能操作？
5. 哪个对象是正式 Authority（权威对象）？
6. 是否还让用户手工输入本应由后端正式对象决定的字段？
7. 页面是否因为新增状态变得拥挤、难懂或按钮冲突？
8. 小屏是否仍可操作？
9. 老师/学生是否需要看内部代码枚举？答案默认是否定的。

前端同步必须遵守：
**首屏结论 → 关键数字/对象 → blocker（阻断）→ 下一动作 → 明细证据**，
而不是只增加一个字段或一个按钮。

## 0B-7. Screenshot Before/After（修改前后截图）硬门

只要本批影响 UI：
1. 在改动前，优先捕获当前页面 baseline screenshot（基线截图）；若当前页面无法正常进入，记录原因。
2. 完成 UI 后必须使用**真实运行的前端 + 真实后端接口**重新截图。
3. 电脑端优先沿用仓库现有 visual Gold（视觉基线）viewport（视口）；若无既有标准，至少覆盖常用桌面视口和一个较窄桌面视口。
4. 小程序使用真实小程序/H5目标视口或仓库现有视觉测试视口。
5. 关键页面至少截图：
   - 正常态；
   - 一个高价值异常/阻断态；
   - 新增状态/只读态（如果本批涉及）。
6. 如果是列表+详情+操作的主链，不得只截空列表；必须有真实业务数据。

### 截图必须做视觉识别复审

施工 Agent（智能体）必须实际打开截图进行视觉检查，不能只证明“截图文件生成了”。

逐张检查：
- 标题/副标题是否与新业务合同一致；
- 首屏结论是否清楚；
- blocker（阻断）是否醒目但不过度；
- 按钮是否与 allowedActions（允许动作）一致；
- 是否仍出现旧字段、旧状态、旧入口；
- 文字是否截断、重叠、溢出；
- 表格是否横向炸裂；
- 卡片是否过密；
- 对话框/抽屉是否超出视口；
- sticky header（粘性表头）是否遮挡；
- 状态标签是否语义一致；
- loading/empty/error/read-only（加载/空态/错误/只读）是否完整；
- 窄屏是否出现不可点击控件；
- 是否出现假数据、mock（模拟）文案、placeholder（占位符）泄漏；
- 是否出现浏览器 console error（控制台错误）。

**发现视觉问题必须继续修 → 重新截图 → 再识别。**
截图有问题时不得因为自动测试绿而结束。

## 0B-8. Real-click E2E（真实点击端到端）硬门

UI 批次完成前，必须由浏览器自动化/真实浏览器会话按**可见控件真实点击**完成主链，不允许只调用 API（接口）代替 UI 验收。

至少覆盖：
1. 从真实路由进入页面；
2. 通过页面选择学期/批次/TeachingTask（教学任务）等对象；
3. 点击真实按钮；
4. 打开真实 modal/drawer（弹窗/抽屉）；
5. 填真实表单；
6. 点击确认；
7. 观察真实 network request（网络请求）到后端；
8. 读取页面成功/失败反馈；
9. 刷新页面；
10. 重新打开对象；
11. 确认后端持久状态仍一致；
12. 必要时换角色/换端确认同一事实。

同时必须覆盖至少一个负向点击：
- 无权限；
- 错误状态；
- 409 conflict（冲突）；
- 校验失败；
- 已归档只读；
- 重复点击；
中的一个或多个。

### 严禁把以下内容当作真实点击完成
- 只跑后端 pytest（测试）；
- 只调用接口；
- 只跑组件 shallow test（浅层测试）；
- 只检查 DOM（页面节点）存在；
- 只生成截图但没有点击；
- 使用前端 mock service（模拟服务）；
- 因登录/环境困难改成假数据流程。

如果当前 CI（持续集成）无法提供浏览器环境：
本批状态只能是 `UI_E2E_BLOCKED（界面端到端被环境阻断）`，不能声称完成。

## 0B-9. UI Gold（界面最终验收）必须绑定 exact-head（精确提交头）

每次截图/真实点击证据必须记录：
- Git commit SHA（提交哈希）；
- route（路由）；
- role（角色）；
- tenant（租户）；
- viewport（视口）；
- dataset/fixture identity（数据集/夹具身份）；
- screenshot artifact（截图证据）；
- E2E run/job（端到端运行/任务）；
- browser console result（浏览器控制台结果）；
- network mock count（模拟网络数量，正式 Gold 必须为0或明确允许的基础设施例外）。

代码提交头变化后，受影响的旧截图和旧 E2E 证据自动失效，必须按影响范围重验。

## 0B-10. 完成状态强制分级

只有后端绿：
`BACKEND_GREEN_UI_OPEN（后端已绿、界面未收口）`

前端改完但未截图复审：
`UI_IMPLEMENTED_VISUAL_OPEN（界面已实现、视觉未收口）`

截图通过但未真实点击：
`VISUAL_GREEN_E2E_OPEN（视觉已绿、端到端未收口）`

真实点击通过但 exact-head 之后又改代码：
`EVIDENCE_STALE（证据已过期）`

只有以下全部满足才允许：
`COMPLETED（完成）`

- backend targeted tests（后端定向测试）绿；
- MySQL（关系型数据库）相关门禁绿；
- frontend unit/component tests（前端单元/组件测试）绿；
- 受影响页面 UI 已同步；
- screenshot visual audit（截图视觉识别复审）绿；
- real-click E2E（真实点击端到端）绿；
- refresh persistence（刷新后持久一致）绿；
- PC/miniapp consistency（电脑端/小程序一致）绿；
- permission negative（权限负向）绿；
- dataScope negative（数据范围负向）绿；
- console 0 error（控制台0错误）；
- 正式网络 0 fake mock（0假模拟）；
- exact-head evidence（精确提交头证据）有效。

## 0B-11. 截图证据如何进入 PR（拉取请求）

- 若仓库已有 checked-in visual Gold（纳入版本库的视觉基线），按现有规范更新，不得私自降低阈值。
- 若仓库没有纳入版本库的截图基线，截图优先作为 CI/E2E artifact（持续集成/端到端产物），不要无节制把大批 PNG（二进制图片）提交进仓库。
- 但必须在本线“施工顺序与文档读取地图”中写入：
  - exact HEAD；
  - 截图名称/产物位置；
  - 视觉复审结论；
  - E2E run/job；
  - 失败过哪些视觉问题；
  - 修复后最终结论。

---



## 0C-D. D线后端变化对应的前端同步重点

D线必须重点复查：
- Graduation Audit（毕业审核）批次/结果/详情/三名单；
- 学生毕业进度/毕业结论消费者；
- Graduation Override（毕业例外，如最终建设）；
- Archive（归档）预检/域状态/归档清单；
- Post-Archive Correction（归档后纠错）；
- R11（真实学校完整学期试点）阶段工作区；
- Evaluation（评教）学生端/管理端；
- 数据迁移/Cutover Ledger（切换台账）；
- 恢复/交付只读证据页面（如系统已有）。

特别要求：
- SYSTEM_ABNORMAL（系统异常）不能再在UI上出现普通“确认毕业”按钮。
- 如果存在正式Override（例外），页面必须清楚区分 NORMAL（正常）与 OVERRIDE（例外），不能把例外伪装成普通通过。
- Archive 的 UNKNOWN（未知）必须显示为阻断/待治理，不能用绿色成功样式。
- ROSTER_PENDING_SELECTION（等待选课名单）必须与“错误/缺名单”视觉区分。
- R11每个阶段截图必须能下钻到真实 blocker（阻断），不能只截总览绿卡。


---

# D（毕业交付线）— 当前代码精确审计与最终施工裁决

## D-0 当前真实成熟度

**当前代码生产成熟度：86/100。目标：99/100。**

D线底层治理并不弱：不可变毕业评估、十三域Archive（归档）、归档后纠错、R11（真实学校完整学期试点）、File Exchange（文件交换）、Outbox（事务消息箱）都已经具备商业系统骨架。

真正问题是：**几个“最终签字点”仍有假绿可能。**

### 当前必须保护的强能力
- GraduationEvaluationRun（毕业评估运行）是append-only（只追加）不可变事实。
- GraduationDecisionFact（毕业决策事实）引用exact run（精确评估运行）。
- 预览与正式预审共用同一严格evaluator（评估器）。
- StudentAcademicFact（学生学业事实）按effective time（生效时间）取历史身份。
- ArchiveManifest（归档清单）与PostArchiveCorrectionCase（归档后纠错案件）已经建立“不能原地改历史”的正确方向。
- R11要求production（生产环境）、DB enabled（数据库启用）、mock login off（模拟登录关闭）、real data confirmed（真实数据确认）和六阶段。
- 评教已经有学生本人、正式Roster（名单）、匿名HMAC（消息认证码）、重复提交保护。
- Academic File Exchange（教务文件交换中心）有安全扫描、预检、确认、摘要和下载票据。

### 当前真实P0（最高优先级）
1. SYSTEM_ABNORMAL（系统异常）毕业评估仍可凭不少于5字的普通审核备注终审GRADUATED/COMPLETED（毕业/完成）。
2. R11 PRE_TERM（开学准备阶段）要求所有TeachingClass（教学班）都已有LOCKED Roster（锁定名单），不符合SELECTABLE（自主选课）课程真实生命周期。
3. Archive毕业域在termId（学期编号）缺失或学期日期不完整时会返回passed=true（通过），存在false green（假绿）。
4. 评教同一Task（任务）使用行锁串行提交，并通过JSON LIKE（结构化文本模糊匹配）找匿名token（凭证），高峰规模需真实MySQL（关系型数据库）验证。
5. 新学校切换、T+1对账、基础设施PITR（时间点恢复）与FileObject（文件对象）恢复仍是最终上线证据缺口。
6. 十三域部分检查使用 `.all()` 后Python处理，多年历史规模需SQL化。

---

## D-P0-01 毕业评估很严格，但普通五字备注可以绕过它

### 当前强点
`academic_affairs_graduation_immutable_service.py（毕业不可变服务）`

`_strict_overall（严格总判定）`：
只有所有必需项全部PASS（通过），才SYSTEM_PASSED（系统通过）。
任何FAIL/UNKNOWN（失败/未知）都进入SYSTEM_ABNORMAL（系统异常）。

正式precheck（预审）：
- 追加GraduationEvaluationRun（毕业评估运行）；
- 保存input snapshot/hash（输入快照/哈希）；
- mutable projection（可变投影）只指向最新运行；
- 不覆盖历史运行。

这些都是正确的。

### 真实P0
终审逻辑当前允许：

`SYSTEM_ABNORMAL（系统异常） + conclusion=GRADUATED/COMPLETED（毕业/完成）`

只要：
`review_note（审核备注）长度 >= 5`

就继续通过。

更关键的是：
`test_aa_graduation.py（毕业测试）`
明确把：
“人工核验，确认异常或未知项不影响毕业”
作为当前成功路径进行测试。

### 本质
这不是bug（程序错误）偶发，而是**当前政策设计本身允许普通备注绕过不可变评估**。

### 为什么不符合生产级正式记录治理
一个正式毕业例外至少要区分：
- 哪一条requirement（要求）被豁免；
- 为什么；
- 哪个制度允许；
- 哪个证据；
- 谁申请；
- 谁批准；
- 是否两级审批；
- 是否可撤销；
- 最终DecisionFact（决策事实）是NORMAL（正常）还是OVERRIDE（例外）。

五字备注不具备这些属性。

### 最终施工
普通final（终审）：
- 最新run必须SYSTEM_PASSED（系统通过）；
- 否则409 DATA_CONFLICT（数据冲突）。

如果目标学校存在特批：
建立独立Graduation Override（毕业例外）正式流程：
- 只针对具体ruleCode（规则码）；
- 强证据；
- 强权限；
- 独立审批；
- append-only（只追加）；
- DecisionFact引用批准例外；
- 页面明确显示“例外毕业”，不伪装正常通过。

### RED（先失败测试）
- SYSTEM_ABNORMAL+5字备注必须失败。
- SYSTEM_ABNORMAL+500字备注也必须失败。
- 无批准override不能毕业。
- 正常PASS终审继续成功。
- 历史EvaluationRun永不变。

---

## D-P0-02 R11 PRE_TERM（开学准备）与真实选课课生命周期冲突

### 当前代码
R11 PRE_TERM阶段：
- 查TeachingTask（教学任务）；
- 查TeachingClass（教学班）；
- 统计current locked roster versions（当前锁定名单版本）；
- **如果锁定名单数量 != 教学班数量，阻断。**

### 这个规则对行政固定课正确
ADMIN_FIXED（固定行政班）：
开学准备阶段就应该有正式名单。

### 但对SELECTABLE（自主选课）不正确
真实流程可能是：
`Task READY（任务可排） → 正式课表发布 → 开选 → 抽签/补选 → LOCK（锁名单） → Roster Ready（名单就绪）`

在PRE_TERM（开学准备）某个时间点：
- 课表已经正式；
- 选课还没结束；
- 名单合理地未锁。

R11不能因此要求伪造行政名单。

### 最终Readiness（准备度）四态
对每个TeachingClass/Task（教学班/任务）：
- SCHEDULE_READY（课表就绪）
- ROSTER_PENDING_SELECTION（等待选课名单）
- ROSTER_READY（名单就绪）
- DOWNSTREAM_READY（下游可运行）

PRE_TERM：
- ADMIN_FIXED必须至少ROSTER_READY；
- SELECTABLE可处于ROSTER_PENDING_SELECTION，只要正式课表/选课批次已准备。

IN_TERM（教学运行）：
- 真正开始考勤前必须ROSTER_READY；
- Attendance/Exam/Grade（考勤/考试/成绩）硬门不放松。

### Gold
固定课+可选课在同一真实学期都能通过正确阶段，不为过R11造假名单。

---

## D-P0-03 Archive（归档）毕业域存在“未知范围=通过”

### 当前代码
`academic_affairs_archive_domain_policy.py（归档域策略）`
的graduation evaluator（毕业域评估）：

如果没有term_id（学期编号）：
返回 `passed = true（通过）`

如果term start/end（学期起止日期）不完整：
也返回 `passed = true（通过）`

理由是：
避免用全校历史毕业批次错误阻断当前学期。

### 原意正确，结果错误
原意：
“不能拿全历史乱阻断当前学期。”

但实现变成：
“如果我不知道当前学期范围，就当当前学期毕业域没问题。”

### 这是false green（假绿）
ArchiveManifest（归档清单）是学校正式学期证据。
**UNKNOWN（未知）不能等价PASS（通过）。**

### 最终语义
每个Archive domain（归档域）统一：
- PASS（通过）
- BLOCKED（阻断）
- NOT_APPLICABLE（不适用）
- UNKNOWN（未知）

缺term/date（学期/日期）：
UNKNOWN/BLOCKED（未知/阻断）

明确不是毕业学期：
只有正式school policy/term context（学校策略/学期上下文）证明后才NOT_APPLICABLE（不适用）。

### RED
- 缺termId不能PASS。
- 起止日期不完整不能PASS。
- 非毕业学期按明确规则NOT_APPLICABLE。
- 有未完毕业批次必须BLOCKED。

---

## D-P0-04 评教：正确性很强，规模热点必须“先测再改”

### 当前正确性
`academic_affairs_evaluation_public_service.py（评教公开服务）`：
- 学生本人唯一身份；
- 必须在当前正式Roster（名单）；
- 学生批次必须anonymous（匿名）；
- HMAC（消息认证码）生成匿名submission token（提交凭证）；
- 审计只写ANONYMOUS_STUDENT（匿名学生），不写明文学生；
- 重复提交被拒绝；
- submitted_count（提交人数）受正式Roster人数上限保护。

这些全部KEEP（保留）。

### 当前规模热点
每个学生submit（提交）：
- `AaEvaluationTask（评教任务）` `FOR UPDATE（行锁）`；
- 在answers_json（答案配置）中用LIKE（模糊匹配）找匿名token；
- 同一个Task的所有学生还要更新同一个submitted_count。

### 真实高峰
一个300人公共课：
300个学生会竞争同一Task行锁。

全校评教截止前：
多个大课同时高峰。

### 专业施工逻辑
**不要先拍脑袋改表。先做MySQL压测。**

测试：
- 同Task 50并发；
- 100并发；
- 200并发；
- 多Task混合并发；
- p50/p95/p99（50/95/99分位延迟）；
- lock wait（锁等待）；
- deadlock（死锁）；
- 重复记录数；
- submitted_count对账。

只有SLO（服务目标）不达标才迁移：
- 不可逆submission_digest（提交摘要）专列或子表；
- database unique（数据库唯一）；
- submitted_count改安全计数/投影；
- EvaluationRecord（评价记录）继续唯一真值。

匿名边界绝不能因性能优化退化。

---

## D-P0-05 新学校切换必须有T0/T+1事实，而不是“导完就算”

### 当前强底座
Academic File Exchange（教务文件交换中心）已经能：
- 安全文件；
- 预检；
- 错误行；
- 确认；
- 重新读源文件；
- rowDigest（行摘要）；
- expectedVersion（预期版本）。

### 当前实施缺口
课程/培养方案导入由A线补齐后，D线还需要学校Cutover Ledger（切换台账）：

每个域记录：
- 源系统；
- source digest（源摘要）；
- 第一次全量行数；
- 冲突数；
- 最终增量；
- T0切换结果；
- T+1对账；
- 差异；
- 责任人；
- 学校签字。

### 新旧系统规则
T0后：
**新系统成为新业务唯一writer（写入口）**
旧系统：
**只读历史**

不能双写。

国内真实高校2026年新系统切换公开通知已经验证这种切换模式是现实业务，而不是理论设计。

---

## D-P0-06 Archive（业务归档）绝不等于Backup/Restore（备份恢复）

### 你当前的强项
ArchiveManifest（归档清单）可以证明：
“业务在某时点封存了什么。”

PostArchiveCorrectionCase（归档后纠错）可以证明：
“封存后如何合法追加更正。”

### 它不能证明
- 数据库磁盘损坏能恢复；
- binlog（数据库日志）能恢复到指定时间；
- FileObject（文件对象）附件能恢复；
- 密钥/配置能恢复；
- 恢复后业务关系还一致。

### 最终学校上线门
至少一次隔离环境真实恢复：
1. MySQL full backup（数据库全备）；
2. binlog/PITR（日志时间点恢复）；
3. FileObject（文件对象）；
4. 配置/密钥；
5. 恢复后运行对账：
   - AaTerm（学期）
   - ScopeHead（正式课表头）
   - Roster hash（名单哈希）
   - EffectiveGrade（有效成绩）
   - GraduationEvaluationRun（毕业评估运行）
   - ArchiveManifest（归档清单）

没有恢复演练：
不能对学校签RPO/RTO（恢复点/恢复时间目标）。

---

## D-P1-07 Archive（归档）部分域仍全量.all()处理

### 当前模式
部分域：
`.all()`
然后Python分组/统计。

### 短期正确，长期规模风险
多年数据以后：
- 学籍异动；
- 考试；
- 成绩；
- 毕业；
- 归档历史；
可能非常大。

### 施工原则
语义不动，只改查询：
- count（计数）
- exists（存在）
- group by（分组）
- limited evidence ids（有限证据编号）

随机抽样对账：
新SQL结果=旧Python语义结果。

---

## D-P1-08 R11（真实学校完整学期试点）必须成为唯一上线Gold（最终验收），不是又一个CI演练

### 当前R11强点
必须：
- production（生产环境）
- DB enabled（数据库启用）
- mock login off（模拟登录关闭）
- real data confirmed（真实数据确认）
- 六阶段全部通过

而且R11服务不生成学生/课程/任务/成绩等业务事实，只读真实事实。

### 当前工程风险
PR #96（拉取请求）另有semester rehearsal（学期演练）工作流。

它可以是优秀CI（持续集成）门禁，
**但绝不能被叫做真实学校Gold。**

### 最终签字
只有：
- R11 COMPLETED（完成）
- P0=0
- 本轮P1=0
- 20K规模通过
- 权限负向通过
- 消息补偿通过
- Backup/Restore（备份恢复）通过
- clean tenant（全新租户）通过
- migrated tenant（迁移租户）通过

才能叫“学校可上线”。

---

# D-1 当前Authority（权威真值）地图

## 毕业
- EvaluationRun（评估运行）：证据和规则计算事实
- DecisionFact（决策事实）：最终正式结论
- 普通mutable result（可变结果）：只做工作队列/当前投影

## Archive（归档）
- ArchiveManifest（归档清单）：不可变封存证据
- PostArchiveCorrectionCase（归档后纠错）：合法追加纠错

## Evaluation（评教）
- EvaluationRecord（评价记录）：正式答卷事实
- submitted_count（提交数）：统计/守卫，不得成为第二记录真值

## R11（真实学校完整学期试点）
- 只读验证器
- 不生成正式业务数据
- evidence hash（证据哈希）绑定真实阶段

---

# D-2 六个持续施工波次

## D-W0 Graduation Policy（毕业政策）红线
第一刀就修：
SYSTEM_ABNORMAL（系统异常）不能被普通备注终审通过。

如果学校需要特批，单独做Override（例外）正式流程。

输出：
`D-C1 Graduation Decision Contract（毕业决策合同）`

## D-W1 Archive（归档）四态语义
统一：
PASS/BLOCKED/NOT_APPLICABLE/UNKNOWN（通过/阻断/不适用/未知）

UNKNOWN绝不假绿。

输出：
`D-C2 Archive Gate Contract（归档门禁合同）`

## D-W2 R11 + SELECTABLE（可选课程）生命周期
加入：
- SCHEDULE_READY（课表就绪）
- ROSTER_PENDING_SELECTION（等待选课名单）
- ROSTER_READY（名单就绪）
- DOWNSTREAM_READY（下游就绪）

输出：
`D-C3 Semester Pilot Contract（学期试点合同）`

## D-W3 评教与20K规模
- 先压测；
- 再决定是否迁匿名digest（摘要）；
- Archive/Stats（归档/统计）SQL化；
- 选课/成绩/课表复用A/B/C已经形成的性能证据。

## D-W4 Migration/Outbox/Restore（迁移/消息/恢复）
- T0唯一writer；
- T+1对账；
- Outbox pending/dead/lag（消息等待/死信/延迟）；
- MySQL PITR；
- FileObject恢复；
- release evidence package（发布证据包）。

## D-W5 INT Final Gold（总集成最终验收）
顺序固定：
A Contract Freeze（A合同冻结）
→ B Contract Freeze（B合同冻结）
→ C Gold（C最终验收）
→ D Delivery Seal（D交付封板）
→ INT exact-head（总集成精确提交头）
→ R11
→ 学校签字。

INT不再开发新业务。

---

# D-3 真实学校Gold（最终验收基线）

1. SYSTEM_ABNORMAL+普通备注不能毕业。
2. 正式毕业例外有独立审批和证据。
3. GraduationEvaluationRun历史不变。
4. 成绩更正后产生新run，旧run仍可回放。
5. SELECTABLE课程PRE_TERM可等待选课名单。
6. SELECTABLE进入IN_TERM前必须LOCK名单。
7. ADMIN_FIXED固定课PRE_TERM已有正式名单。
8. Archive缺termId不能PASS。
9. Archive学期日期不完整不能PASS。
10. 明确非毕业学期可NOT_APPLICABLE。
11. Selection未启用可不阻断归档。
12. Selection已启用未LOCK必须阻断归档。
13. 评教100同Task并发0重复。
14. 评教200同Task记录p95/p99。
15. 匿名token不能被教师反查。
16. 20K学生课表查询达到SLO。
17. 成绩统计无N+1（逐条查询）。
18. Archive多年历史不全量内存扫描。
19. 课程/方案迁移重复confirm不双写。
20. T0以后旧系统只读。
21. T+1对账发现漏增量。
22. Outbox provider（消息提供商）失败后业务事实不回滚。
23. dead delivery（死信）可被运维发现并重试。
24. MySQL PITR隔离恢复通过。
25. FileObject附件恢复通过。
26. ScopeHead/Roster/EffectiveGrade/ArchiveManifest恢复后对账一致。
27. R11 mock login开时不能complete。
28. R11 realData未确认不能complete。
29. 任一stage有blocker不能complete。
30. 同一真实学期固定课和选课课都跑到考勤、考试、成绩、毕业、归档。
31. 学院A不能读B敏感数据。
32. 邻租户sentinel（哨兵数据）永不泄漏。
33. clean tenant与migrated tenant各一套最终Gold。

---

# D-4 自行纠错与反证

1. **纠正“毕业已经完全fail-closed”**：评估器确实严格，但普通终审仍有五字备注绕过。
2. **纠正“R11已经完全适配真实学期”**：当前PRE_TERM仍按行政班思维要求所有名单锁定。
3. **纠正“避免跨历史阻断就可以PASS”**：无法确定范围应该UNKNOWN，不应该假绿。
4. **不把评教行锁直接判成要重构**：正确性很强，先用真实MySQL压测证明是否达到迁移阈值。
5. **把业务归档和基础设施恢复彻底分开**：ArchiveManifest不能代替数据库/附件恢复演练。
6. **把实施工具提升为核心交付能力**：代码再成熟，课程/方案迁不进来、T+1不能对账，也不能说真实学校可上线。

---

# D-5 最终签字

只有以下同时满足：
- 毕业普通路径无旁路；
- 例外路径正式可审计；
- Archive 0 false-green（假绿）；
- R11贴合ADMIN/SELECTABLE两类课程；
- 评教/20K规模达标；
- 消息失败可补偿；
- 真实MySQL恢复演练完成；
- 文件对象恢复完成；
- T0/T+1迁移证据完成；
- 权限/数据范围负向全绿；
- R11 COMPLETED；
- P0=0；
- 本轮P1=0；
- INT exact-head没有新的跨线红灯；

才允许给出：
**“真实学校可上线教务系统”** 的最终结论。

---

# 附录：V1.5 D线详细业务设计

> 以下保留V1.5的毕业、学位、What-if（模拟规划）、成绩单、评教、20K、消息、迁移、恢复、R11和学校交付详细设计。若与V2.1当前代码裁决冲突，以V2.1为准。

# D — Graduation/Delivery：毕业·学位·认定·归档·性能·运维·R11·交付 — V1.5 四线并行深审增强唯一施工总册

> 仓库：`penghaibin9/saas`  
> 代码审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 日期：2026-08-16  
> 来源：**当前 GitHub 代码 + 仓库历史大设计资产 + 2026 成熟 SIS / 国内高校真实业务对标**。  
> 每次真实施工前必须重新读取 exact `main`、本线 HEAD、open PR collision；本文中的基线不是未来永恒事实。

## V1.5 直接裁决

V1.4 的主链 Authority 方向保留，但详细度不够。V1.5 不再只写“模块应该做什么”，而是把：
`制度场景 → 当前代码事实 → 历史设计 → 唯一 Authority → 数据/API/UI/权限/事务/导入/通知/迁移 → RED → MySQL/E2E → DoD`
写成可逐卡持续施工的任务。

本线新增专题施工卡：**20 张**。  
本线页面施工矩阵：**18 个工作区/页面任务**。  
本线真实学校验收场景：**64 条最低场景**。

状态分布：
- `CURRENT-KEEP + VERIFY-FIRST(degree)`：1
- `CURRENT-HARDEN`：1
- `BENCHMARK-GAP / VERIFY-FIRST`：1
- `EXISTS-KEEP/HARDEN`：1
- `EXISTS-HARDEN + VERIFY-FIRST(enrollment verification)`：1
- `OPTIONAL-INSTITUTION-POLICY`：1
- `CURRENT-KEEP`：1
- `CURRENT-SCALE-BLOCKER`：1
- `GO-LIVE-GATE`：3
- `CURRENT-OPS-HARDEN`：1
- `OPS-BLOCKER`：1
- `IMPLEMENTATION-GATE`：1
- `DELIVERY-GATE`：1
- `CURRENT-MIXED`：1
- `EXISTS-HARDEN/VERIFY-FIRST`：1
- `OPS-GATE`：1
- `CURRENT-KEEP/HARDEN`：1
- `FINAL-GATE`：1



# Ⅰ. 2026 成熟教务 / SIS 对标证据层

本册对标采用“能力抽象”，不复制竞品界面、代码、数据库或专有实现。外部能力只有在与中国学校制度相符、且能复用当前 Authority 时才进入施工。

## 1. Oracle PeopleSoft Campus Solutions / Student Records
公开官方文档体现的成熟能力包括：
- Course Catalog、Schedule of Classes、Repeat Checking、Instructor Workload；
- Enrollment Appointments、Add / Drop / Swap、Waitlist、Reserve Capacity；
- prerequisite / corequisite / enrollment edits；
- Transfer Credit、Attendance、Grading、Transcripts、Enrollment Verification、Graduation；
- Student Planner、Enrollment Shopping Cart；
- Academic Advisement：requirements、requirement groups、degree progress、what-if；
- Faculty Center：课表、名单、成绩、考试等教师自助。

V1.5 吸收规则：
- `WAITLIST ≠ LOTTERY ≠ 补选申请`；
- `SWAP` 若落地必须是原子动作，不能前端先退后选；
- Planner / Shopping Cart 只能是草稿计划，不能占正式容量、不能进入 TeachingRoster；
- Enrollment Appointment 首先映射为现有 Selection Batch / Round / Scope 的分批准入能力，禁止再造独立选课引擎。

## 2. Workday Student
官方资料体现：
- registration date controls：open enrollment / last add / drop without record / withdraw；
- registration appointments；
- academic plan / saved schedules；
- course eligibility troubleshooting；
- waitlist policy：自动晋级、通知后确认、过期、人工管理；
- reserve capacity；
- registration restriction overrides；
- academic progress / academic requirement overrides；
- course demand / staffing visibility。

V1.5 吸收规则：
- 资格排查应形成统一后端 Preflight / Troubleshooting；
- waitlist 的 offer / expiry / promotion 必须可审计；
- registration appointment 既是公平治理，也是高峰流量分散手段；
- saved schedule 不得成为 SelectionRecord；
- academic progress / what-if 不得成为 GraduationDecisionFact 的第二结论。

## 3. Ellucian Student / Student Success
公开资料强调：
- degree auditing；
- smart planning & registration；
- personalized academic plans；
- major change 后重新评估完成路径；
- real-time degree progress；
- credential discovery。

V1.5 吸收规则：
- 先复用现有 Program + EffectiveGrade + Graduation evaluator；
- what-if 只能输出 `SIMULATION`；
- 不引入“AI 推荐即正式方案”的新真值。

## 4. 国内高校正方真实业务证据
2025–2026 高校公开上线/选课通知体现的真实业务包括：
- 课程信息、新开课申请、课组；
- 培养方案、修读要求、方案变更；
- 主修、通识选修、体育分项、英语板块、特殊课程；
- 排课、调停课、按周换教师、课表打印；
- 按年级/课程性质分批选课；
- 正式选课后补选申请；
- 先修、同修、学分上下限；
- 必修教学班取消后重新分配；
- 选修教学班取消后补改选；
- 跟班重修、单开班重修、补修、提前修读、免修；
- 集中/分散考试、监考、考试名单打印；
- 毕业预审、毕业审核、学位审核、成绩单打印；
- 教学进程维护申请/审核/监控；
- 教师工作量与结算；
- 新旧教务切换时新系统成为唯一新业务入口，旧系统保留只读历史查询。

这些内容在 V1.5 中优先转化成“真实学校验收场景”和“制度参数”，而不是机械增加菜单。


# Ⅱ. 三层 Reconciliation 方法

每个专题开工前必须完成三层判真：

## CURRENT CODE FACT
从 exact-head 的 model / migration / router / public-final service / frontend / student-portal / miniapp / tests / workflows 判定：
- `CURRENT-KEEP`
- `CURRENT-HARDEN`
- `CURRENT-REWIRE`
- `CURRENT-BLOCKER`

## HISTORICAL DESIGN RECONCILIATION
必须重新读取仓库既有大设计资产，而不是只看 V1.4：
- `13B-教务中心全业务流程设计总册.md`
- `13B-教务中心页面级交互与按钮动作矩阵.md`
- `13B-教务中心状态机与权限矩阵.md`
- `13B-教务中心表单字段与校验规则.md`
- `13B-教务中心页面树与路由设计.md`
- `13B-教务中心API契约草案.md`
- `13B-教务中心-商业化对标审计与补丁建议（第一轮）.md`
- `教务中心产品深度补强10份整改文档-V2-代码对齐与页面施工版/*`
- `施工包/*`
- `三级施工卡/*`
- `外部对标证据/*`

历史结论只能标为：
- `HISTORICAL-VALID`
- `HISTORICAL-MERGED`
- `OBSOLETE_BY_CURRENT_CODE`
- `NEEDS_RETEST`

## MATURE-SIS BENCHMARK
外部能力只能标：
- `BENCHMARK-PARITY`
- `BENCHMARK-GAP`
- `VERIFY-FIRST`
- `OPTIONAL-INSTITUTION-POLICY`

外部系统有，不等于本系统就要新建。

# Ⅲ. 新表 / 新 Authority 七问门禁

任何 AI 想新增表、持久化实体或新 writer，必须先回答：
1. 当前代码是否已有同语义事实？
2. 历史设计是否已经被现有 Authority 吸收？
3. 能否只做现有 Authority 的字段、子表、版本或 read projection？
4. 唯一 writer 是谁？
5. 历史数据如何 inventory / backfill / dual-read / cutover / rollback？
6. Attendance / Exam / Grade / Graduation / Archive 如何保证不产生双真值？
7. 是否有真实学校制度场景证明“必须持久化”，而不是只需 UI / projection？

任一问题答不清：`NO MIGRATION`。

# Ⅳ. 四线共同安全边界

- 不新建第二套 OpeningPlan / TeachingTask / OfficialSchedule / TeachingRoster / EffectiveGrade / Graduation Truth。
- stable ID 是业务身份；名称只做 snapshot/display。
- 正式写继续受 `tenant + RBAC + dataScope + archive guard + audit`。
- 页面不能自行计算选课资格、毕业资格、正式名单或正式成绩。
- shared file、Alembic、Permission Catalog、route registration、Data Exchange 公共层统一交 INT 单 Owner。
- PR #96 当前与 academic registry / `services/__init__.py` / 教师小程序成绩页存在碰撞风险。
- PR #133 当前占用 Control Plane Permission Catalog / Data Exchange / identity / Alembic / route registration 等共享面。
- 任何旧设计与当前代码冲突时，current exact-head 优先。
- queued / pending / in-progress 不算 success。
- 禁止 skip / xfail / ignore / mock 正式事实假绿。
- 禁止 force push；未经明确授权不合并 main。


# Ⅴ. 历史大设计资产重新纳管裁决

V1.4 最大不足不是方向错误，而是没有把仓库既有的大量详细设计重新归并进当前 Authority。

## 必须重新吸收的价值
1. 旧全业务流程总册的角色、状态、异常、通知、统计、归档、实施确认项；
2. 页面动作矩阵的按钮→API→状态→权限→失败路径；
3. 状态机/权限矩阵中的业务职责；
4. 表单字段与校验规则中的字段级边界；
5. 页面树中的“一个页面一个主任务”；
6. 旧商业化对标中的批量、打印、台账、工作量、移动端、实施交付；
7. 三级施工卡中的验收步骤。

## 必须明确废弃的旧假设
- 旧文档曾认为 TeachingClass / 成员 Authority 尚需从零迁移；当前 `AaTeachingClass + RosterVersion + Member` 已成熟，此假设 `OBSOLETE_BY_CURRENT_CODE`。
- 旧文档曾要求 Selection LOCK 后“等待独立成员表上线”再接名单；当前 LOCK→`SELECTION_LOCK` TeachingRoster 已存在，改为 `CURRENT-KEEP/HARDEN`。
- 旧具体表名、旧接口名、旧行号不得压过当前 ORM / formal router / public-final service。
- 旧“V1/P2/P3=做/不做”的缩水表达废弃，改为：成熟底座 / 本轮补强 / 学校可选能力。
- Waitlist 在旧 V2 中被明确放到 LATER；V1.5 仍然坚持先封正式 Selection 主链，只有真实学校需求 + exact-head 精审后才启用。


# Ⅵ-D. D线 Current Repo Evidence Inventory

- `GraduationEvaluationRun / GraduationDecisionFact`：append-only正式毕业事实，决定引用exact evaluation run。
- `ArchiveManifest / PostArchiveCorrectionCase`：不可变归档与归档后正式纠错。
- 13-domain Archive policy已经区分PASS / BLOCKED / NOT_APPLICABLE。
- `0090_aa_grade_recognition.py + academic_affairs_recognition_public_service.py + recognition_service + 管理/学生页面`：学分/成绩认定是已有能力，不得再造TransferCredit第二套。
- Transcript已有管理PC、学生端、小程序和“成绩单打印”三级施工卡：成绩单不是新增模块。
- Evaluation业务正确性已经较强，但同task行锁是规模热点候选。
- 20K SQL分页/production audit guard、Outbox/Delivery/Scheduler、R11都已经存在基础。
- 独立“学位审核”current证据不足：必须VERIFY-FIRST，并按学校类型OPTIONAL。
- R11只有在production + DB enabled + mock off + realDataConfirmed + 六阶段全绿时才允许COMPLETED；PR#96 rehearsal不能替代。

# Ⅶ. 市场对标 → 当前仓库差距矩阵

| 能力 | 成熟系统/国内场景 | 当前裁决 | V1.5动作 |
|---|---|---|---|
| 毕业审核 | PeopleSoft/Workday/Ellucian/正方 | CURRENT-KEEP | immutable evaluation/decision |
| 学位审核 | 国内正方 | VERIFY-FIRST/OPTIONAL | 按学校类型启用 |
| Academic Progress | PeopleSoft/Workday/Ellucian | CURRENT-HARDEN | 逐项证据 |
| What-if | PeopleSoft/Workday/Ellucian | BENCHMARK-GAP | 纯读SIMULATION |
| 学分认定/置换 | PeopleSoft transfer credit/正方 | EXISTS-KEEP/HARDEN | Recognition已有 |
| 成绩单 | PeopleSoft/正方 | EXISTS-HARDEN | 已有页面/施工卡 |
| 在读证明 | PeopleSoft | VERIFY-FIRST | Document issuance边界 |
| 评教高峰 | 学校集中业务 | CURRENT-SCALE-BLOCKER | 真实MySQL压测 |
| 统计/状态数据 | PeopleSoft/正方 | EXISTS-HARDEN | 统一metric口径 |
| 十三域归档 | 本系统强能力 | CURRENT-KEEP | 语义封存 |
| 归档后纠错 | 审计治理 | CURRENT-KEEP | PostArchiveCorrectionCase |
| 新旧系统切换 | 国内高校真实上线 | IMPLEMENTATION-GATE | 新系统唯一writer+旧只读 |
| Backup/PITR | 商业运维必需 | OPS-BLOCKER | 恢复演练 |
| R11 | 本系统最终Gate | GO-LIVE-GATE | 真实完整学期 |
| 交付证据/培训 | 商业实施必需 | DELIVERY-GATE | 版本化交付包 |

# Ⅵ. V1.5 深度施工卡


---

## D15-01 — 毕业资格 Audit 与学位审核分层

**优先级：** `P0/P1`  
**V1.5 裁决：** `CURRENT-KEEP + VERIFY-FIRST(degree)`  
**外部成熟度信号：** PeopleSoft Academic Advisement/Workday/Ellucian均有degree progress；国内正方真实上线明确区分毕业审核与学位审核。

### 1. 学校业务问题
- 部分高校毕业资格与学位授予资格规则不同。
- 中职/不授学位学校又不应被强制启用。

### 2. 当前 exact-head 事实
- GraduationEvaluationRun/GraduationDecisionFact已append-only且强。
- current独立Degree Audit/Decision Authority证据不足。

### 3. 历史设计 Reconciliation
- 旧毕业设计须以current immutable facts为准；若旧文档把毕业/学位混为一谈，拆语义不复制系统。

### 4. 唯一 Authority 决策
- GraduationDecisionFact继续毕业正式结论；学位若启用，优先复用generic evaluation framework的不同ruleSet/decisionType。
- 学校不启用时明确NOT_APPLICABLE。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- provider缺失却PASS RED。
- 不授学位租户被degree blocker阻断RED。
- 旧GraduationDecision被覆盖RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-02 — 毕业逐项 Requirement Evidence / Remediation

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 成熟degree audit核心是逐项解释已满足/未满足，而不是一个总PASS。

### 1. 学校业务问题
- 学生和教务必须知道缺哪门课、哪类学分、哪个跨域证据。
- 审核要能重放当时依据。

### 2. 当前 exact-head 事实
- EvaluationRun保存input snapshot/hash；DecisionFact引用exact run。

### 3. 历史设计 Reconciliation
- 历史逐项毕业证据设计重新纳管，但不回退mutable单行结果。

### 4. 唯一 Authority 决策
- 每项返回ruleCode/result/evidence/evidenceAt/source/howToResolve。
- 跨域provider异常必须UNKNOWN/BLOCKED。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- provider timeout变PASS RED。
- evidence source丢失RED。
- 旧run随新事实变化RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-03 — Academic Progress / What-if 学业规划

**优先级：** `P1`  
**V1.5 裁决：** `BENCHMARK-GAP / VERIFY-FIRST`  
**外部成熟度信号：** PeopleSoft/Workday/Ellucian都提供academic progress、what-if或smart planning。

### 1. 学校业务问题
- 学生不应等毕业前才知道缺口。
- 转专业时需要模拟新方案但不能影响正式结论。

### 2. 当前 exact-head 事实
- Credits/Graduation页面、Program requirements、EffectiveGrade已有强输入。
- 完整what-if current production证据不足。

### 3. 历史设计 Reconciliation
- 学生门户旧毕业进度设计可复用；模拟不得成为新正式方案。

### 4. 唯一 Authority 决策
- 只读SIMULATION：Program version + current facts + hypothetical choices。
- 不写GraduationDecision，不承诺一定毕业。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 模拟结果被当正式PASS RED。
- 使用未生效Program却不标simulation RED。
- 缓存未随事实版本失效RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-04 — 转专业 / 学分认定 / 课程置换 → Graduation Provider

**优先级：** `P0`  
**V1.5 裁决：** `EXISTS-KEEP/HARDEN`  
**外部成熟度信号：** PeopleSoft有transfer credit；国内高校有创新创业学分认定、课程置换和转专业按已获学分规划。

### 1. 学校业务问题
- 认定必须进入EffectiveGrade/Credit/Graduation且不能双计。

### 2. 当前 exact-head 事实
- 0090_aa_grade_recognition、recognition public/service、管理/学生页面已存在。
- StudentAcademicFact支持历史身份。

### 3. 历史设计 Reconciliation
- 旧‘认定/置换’设计标HISTORICAL-MERGED，不再造TransferCredit第二套。

### 4. 唯一 Authority 决策
- Recognition继续唯一事实；Credits/Graduation消费effective result。
- 转专业通过StudentAcademicFact+Program binding/exception表达。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 同一证据重复认定RED。
- 撤销后仍计入RED。
- Recognition与原成绩双计学分RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-05 — 成绩单 / 查询件 / 在读证明 / 学籍证明

**优先级：** `P1`  
**V1.5 裁决：** `EXISTS-HARDEN + VERIFY-FIRST(enrollment verification)`  
**外部成熟度信号：** PeopleSoft支持Transcript/Enrollment Verification；国内正方把成绩单打印列为毕业业务交付。

### 1. 学校业务问题
- 学校正式服务不仅是页面查成绩，还要可打印/下载/验证的查询件。

### 2. 当前 exact-head 事实
- AaTranscriptView、miniapp transcript、grade_read_router、成绩单打印三级施工卡均存在。
- 独立在读证明闭环仍需精审。

### 3. 历史设计 Reconciliation
- 历史打印模板/下载/水印设计可纳管；成绩单不是新增。

### 4. 唯一 Authority 决策
- 查询件是StudentAcademicFact+EffectiveGrade+Program的projection。
- 电子证明发行/验证码若存在复用document service，不复制成绩数据。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 未发布成绩进入正式成绩单RED。
- 跨学生下载RED。
- 撤销文件仍可下载RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-06 — Academic Standing / Honors / Milestones 可选 Provider

**优先级：** `P2`  
**V1.5 裁决：** `OPTIONAL-INSTITUTION-POLICY`  
**外部成熟度信号：** PeopleSoft Student Records包含academic standing/milestones/honors；不同中国学校需求差异较大。

### 1. 学校业务问题
- 部分毕业/学位规则可能引用学业状态或里程碑。
- 但不应为所有职校强行扩模型。

### 2. 当前 exact-head 事实
- StudentAcademicFact、AcademicWarning、学工奖励等事实分布在正式域中。

### 3. 历史设计 Reconciliation
- 旧跨模块融合设计只作为provider边界参考。

### 4. 唯一 Authority 决策
- D线只定义只读provider，不复制学工/学生域主事实。
- 未启用规则=NOT_APPLICABLE。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 未启用provider却block毕业RED。
- 跨域敏感信息无授权暴露RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-07 — 十三域 Archive 语义封板

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-KEEP`  
**外部成熟度信号：** 正式学期需要业务语义封存，而不是‘表有数据’。

### 1. 学校业务问题
- 归档前要判断所有正式流程是否结束。
- 可选模块没启用不能误阻断。

### 2. 当前 exact-head 事实
- ArchiveService/DomainPolicy/ArchiveManifest/PostArchiveCorrectionCase已成熟。
- Selection未启用PASS等语义已经存在。

### 3. 历史设计 Reconciliation
- 旧mutable归档设计已被current immutable架构超越。

### 4. 唯一 Authority 决策
- 13-domain evaluator→ArchiveManifest唯一；业务Archive≠基础设施backup。
- confirmed后普通写全部fail-closed。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- NOT_APPLICABLE误判BLOCKED RED。
- 归档后普通写成功RED。
- 旧manifest被覆盖RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-08 — 学生评教集中高峰 / 匿名幂等

**优先级：** `P0/P1`  
**V1.5 裁决：** `CURRENT-SCALE-BLOCKER`  
**外部成熟度信号：** 集中评教是学校典型瞬时高峰，正确性和规模必须同时成立。

### 1. 学校业务问题
- 同一task几十/上百学生同时提交，全校截止前会集中访问。

### 2. 当前 exact-head 事实
- current评教已校验本人、formal Roster、匿名HMAC去重；同EvaluationTask FOR UPDATE可能热点。

### 3. 历史设计 Reconciliation
- 旧‘可重复评教’欠账应标RESOLVED_BY_CODE；性能欠账仍STILL_OPEN。

### 4. 唯一 Authority 决策
- EvaluationRecord继续唯一truth；性能优化只能改变digest/unique/counter机制。
- 先压测再迁移。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 100/200并发重复RED。
- Roster外提交RED。
- 锁超时产生半写RED。
- submitted_count漂移RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-09 — 20K 学校规模 / 查询与并发 SLO

**优先级：** `P0`  
**V1.5 裁决：** `GO-LIVE-GATE`  
**外部成熟度信号：** 成熟SIS必须承载真实学校规模；Workday还通过registration appointments帮助管理高峰。

### 1. 学校业务问题
- 模块单测绿不代表2万学生能用。
- 课表、Selection、成绩、归档都可能高负载。

### 2. 当前 exact-head 事实
- production audit guard已有20K SQL分页/PII治理基础；V1.3已有p95/p99建议。

### 3. 历史设计 Reconciliation
- 旧性能欠账必须逐条Reconciliation，不重复计算已解决问题。

### 4. 唯一 Authority 决策
- 这是性能证据层，不新增业务真值。
- 指标必须绑定exact SHA、DB版本/参数、数据集版本。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- Python全量materialize RED。
- N+1 RED。
- Selection超卖RED。
- 大导出阻塞Web RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-10 — Outbox / Delivery / Scheduler 教务关键消息矩阵

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-OPS-HARDEN`  
**外部成熟度信号：** 商业系统关键业务不仅要事务成功，还要能发现通知失败并补偿。

### 1. 学校业务问题
- 调课、选课结果、考试改期、成绩发布不送达会直接影响学校运行。

### 2. 当前 exact-head 事实
- repo已有scheduler、Outbox/Delivery、pending/dead/oldestPendingAge/lag指标。

### 3. 历史设计 Reconciliation
- 历史通知清单可以吸收受众/时机，但全部统一当前Outbox。

### 4. 唯一 Authority 决策
- business fact先commit，Outbox同事务，Delivery异步。
- 各Domain禁止自建消息真值。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 业务成功但Outbox缺失RED。
- 重复消息轰炸RED。
- dead无告警RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-11 — Backup / PITR / FileObject 恢复演练

**优先级：** `P0`  
**V1.5 裁决：** `OPS-BLOCKER`  
**外部成熟度信号：** 业务Archive永远不能替代数据库和附件灾备。

### 1. 学校业务问题
- 学校数据事故后必须恢复到可继续工作的状态。
- 只有备份没有恢复演练不能签字。

### 2. 当前 exact-head 事实
- V1.3已要求MySQL full+binlog/PITR、FileObject、配置/密钥备份。
- 部署runbook需与真实生产环境核对。

### 3. 历史设计 Reconciliation
- 历史运维runbook只作操作起点。

### 4. 唯一 Authority 决策
- 基础设施恢复后用业务count/hash/ScopeHead/Roster/Grade/ArchiveManifest验真。
- 不新增业务backup表。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 只备不恢复RED。
- 恢复后ArchiveManifest/hash不一致RED。
- FileObject缺失RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-12 — R11 真实学期 Pilot 最终签字

**优先级：** `P0`  
**V1.5 裁决：** `GO-LIVE-GATE`  
**外部成熟度信号：** 可交付系统必须证明同一真实学期连续跑通，不是各模块测试拼图。

### 1. 学校业务问题
- fixed与selectable课程必须在同一学期进入后半链。
- 异常、归档和恢复都要有证据。

### 2. 当前 exact-head 事实
- R11已有BASELINE→PRE_TERM→IN_TERM→EXAM→GRADE→ARCHIVE，并要求production/mock off/realDataConfirmed。

### 3. 历史设计 Reconciliation
- PR#96 rehearsal是辅助测试，不得替代R11 production gate。

### 4. 唯一 Authority 决策
- R11只读真实事实并冻结evidence hash；不造数据。
- SELECTABLE允许SCHEDULE_READY/ROSTER_PENDING_SELECTION，Attendance/Exam/Grade仍要求正式Roster。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- mock on仍complete RED。
- 任一stage blocked仍complete RED。
- demo tenant冒充realData RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-13 — 学校切换：T0新系统唯一Writer + 旧系统只读

**优先级：** `P0`  
**V1.5 裁决：** `IMPLEMENTATION-GATE`  
**外部成熟度信号：** 2026高校新版教务上线公开实践显示：新业务切新系统，旧系统保留历史只读。

### 1. 学校业务问题
- 上线当天不能双写新旧教务。
- 历史又不能突然不可查。

### 2. 当前 exact-head 事实
- V1.3已有T-14/T-7/T-2/T-1/T0/T+1/T+7迁移顺序。
- School Onboarding/File Exchange已有基础。

### 3. 历史设计 Reconciliation
- 历史迁移设计的mapping/rollback/readonly思想重新纳管。

### 4. 唯一 Authority 决策
- T0后新系统唯一writer；旧系统仅readonly。
- T+1主动run reconciliation，不等用户报错。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- T0后旧系统仍可写RED。
- 漏最终增量RED。
- 同学生两身份RED。
- 无rollback plan RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-14 — 学校角色 / dataScope / 邻租户负向矩阵

**优先级：** `P0`  
**V1.5 裁决：** `GO-LIVE-GATE`  
**外部成熟度信号：** 商业SIS功能再多，只要越权就不能上线。

### 1. 学校业务问题
- 教务处、学院教务、教师、学生、学校管理员职责不同。
- 多租户/跨院泄漏是最高级事故。

### 2. 当前 exact-head 事实
- PR#133正在统一Permission Catalog/EffectiveAccess；教务services已有RBAC/dataScope。

### 3. 历史设计 Reconciliation
- 历史权限矩阵只保留业务职责，permission code由Control Plane当前Authority裁决。

### 4. 唯一 Authority 决策
- D线只建立验收矩阵，不复制IAM。
- 页面按钮隐藏不能替代服务端鉴权。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 学院A读取B数据RED。
- 教师改他人Task RED。
- 学生读他人记录RED。
- neighbor tenant泄漏RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-15 — 学校交付证据包 / 培训 / 支持路径

**优先级：** `P0`  
**V1.5 裁决：** `DELIVERY-GATE`  
**外部成熟度信号：** 正式启用不仅是代码发布，还需要参数确认、迁移报告、操作手册和故障升级路径。

### 1. 学校业务问题
- 老师学生需要知道怎么完成阶段性任务。
- 实施和售后要能拿出证据。

### 2. 当前 exact-head 事实
- repo已有帮助中心、流程帮助、部署runbook、学校试点文档；V1.3已有交付包要求。

### 3. 历史设计 Reconciliation
- 历史帮助/页面文档要按current routes重对齐，过时截图/入口标废弃。

### 4. 唯一 Authority 决策
- 文档绑定release SHA/template version；故障反馈带traceId/businessRef。
- 不在业务DB保存巨型文档真值。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 帮助链接404 RED。
- 指南状态机与current冲突RED。
- P0/P1已知限制被隐藏RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-16 — 非主链功能成熟度再验收

**优先级：** `P1`  
**V1.5 裁决：** `CURRENT-MIXED`  
**外部成熟度信号：** 成熟教务还包括教材、等级考试、专业分流、评价、预警、统计等，但‘存在’不等于‘成熟可卖’。

### 1. 学校业务问题
- 这些功能关系招投标，但不能抢主链P0资源。

### 2. 当前 exact-head 事实
- repo已有教材、等级考试、评教、专业分流、recognition、warning、workload、stats等大量代码。

### 3. 历史设计 Reconciliation
- 旧‘存在即保护’升级为保护+成熟度证据。

### 4. 唯一 Authority 决策
- 每域保留原Authority；D只维护CURRENT/HISTORICAL/Gold evidence矩阵。
- 销售清单只把通过Gold的能力标生产成熟。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 只有页面无服务/测试仍标成熟RED。
- 历史欠账未销账却忽略RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-17 — 官方统计 / 状态数据 / 指标口径

**优先级：** `P1`  
**V1.5 裁决：** `EXISTS-HARDEN/VERIFY-FIRST`  
**外部成熟度信号：** 国内正方上线把状态数据和统计报表列为正式业务，成熟SIS也提供academic statistics。

### 1. 学校业务问题
- 同一指标不同页面不能出现不同口径。
- 大报表不能拖垮在线交易。

### 2. 当前 exact-head 事实
- stats_core_router/stats_service/AaStatsOverviewView已存在。
- 具体状态数据上报/统计口径完整度需精审。

### 3. 历史设计 Reconciliation
- 历史教务统计施工包/三级卡可作为指标清单。

### 4. 唯一 Authority 决策
- 统计只读正式Authority；metric definition带code/version/asOf。
- snapshot只为性能，不成为业务writer。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 同指标两页面数值不同RED。
- 跨scope统计RED。
- 空数据除零RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-18 — RPO / RTO / SLO 商业承诺证据

**优先级：** `P1`  
**V1.5 裁决：** `OPS-GATE`  
**外部成熟度信号：** 学校招投标和生产运维会问并发、恢复、可用性；不能无证据承诺。

### 1. 学校业务问题
- SLO/RPO/RTO必须与真实部署能力一致。

### 2. 当前 exact-head 事实
- V1.3建议p95≤800ms等性能目标、RPO≤30min、RTO≤4h；实际环境需验证。

### 3. 历史设计 Reconciliation
- 历史runbook不是SLA证据。

### 4. 唯一 Authority 决策
- 这属于运维合同证据，不改业务Authority。
- 每release保存环境、DB参数、build digest和测试结果。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 无测试证据却宣称SLO达标RED。
- 监控断档仍签字RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-19 — 归档后纠错 / 法务审计证据

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN`  
**外部成熟度信号：** 正式学生记录必须能纠错，但不能抹去历史。

### 1. 学校业务问题
- 成绩、毕业结论可能在归档后更正。
- 学校必须解释谁、为什么、基于什么证据。

### 2. 当前 exact-head 事实
- PostArchiveCorrectionCase已有，当前覆盖GRADE/GRADUATION；ArchiveManifest追加版本。

### 3. 历史设计 Reconciliation
- 旧unfreeze式设计全部OBSOLETE。

### 4. 唯一 Authority 决策
- 唯一合法路径=CorrectionCase→正式domain writer→新事实→新manifest。
- 绝不unlock旧历史原地UPDATE。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- 直接UPDATE archived row RED。
- double execute RED。
- 旧manifest hash变化RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。


---

## D15-20 — 最终‘学校真的能用’签字矩阵

**优先级：** `P0`  
**V1.5 裁决：** `FINAL-GATE`  
**外部成熟度信号：** 成熟SIS最终价值不是功能数量，而是不同角色能完成端到端任务。

### 1. 学校业务问题
- 必须证明教务处、学院、教师、学生、学校管理员都能实际工作。
- 任何P0/P1已知缺口都不能隐藏。

### 2. 当前 exact-head 事实
- A/B/C/D各有Gold；R11、20K、恢复、迁移、权限都有当前基座。

### 3. 历史设计 Reconciliation
- 历史页面动作矩阵转成最终验收步骤库。

### 4. 唯一 Authority 决策
- 不新增任何Authority，只收集exact-head证据。
- clean tenant和migrated tenant各至少一套。

### 5. 数据模型施工准则
- 先按 model / migration / unique key / FK / effective dating / immutable history 逐项核现状。
- 若现有表能表达，只允许扩字段、子表或 projection；不得平行造同语义主表。
- 所有正式引用使用 stable ID；文本名称只用于展示快照。
- 涉及历史事实必须保留 `version / effectiveAt / source / reason / createdBy` 或现有等价证据。
- 任何 schema 变更先做 dirty-data inventory，再提交 INT migration 请求；不得先改 NOT NULL 再处理脏数据。
- 新增 JSON policy 必须有 schemaVersion / validation / fail-closed；坏 JSON 不能降级成“无限制”。

### 6. Service / API 契约
- 先定位 formal/public/final owner；legacy/facade 只能作为兼容，不新增写 Authority。
- 写 API 必须服务端重新校验 tenant、scope、状态机、版本、归档 guard。
- 纯 Preflight / eligibility / readiness 方法不得 `commit()`。
- 所有拒绝返回稳定 `businessCode + message + evidence + howToResolve`；不能只返回“操作失败”。
- 列表必须 SQL 分页，禁止大数据全量 materialize 后 Python filter。
- 更新正式事实使用 expectedVersion / CAS 或现有行锁协议。
- 新接口若只是聚合，优先 read projection，不持久化“仪表盘状态”。

### 7. 管理 / 教师 PC
- 页面必须有唯一主任务，复杂规则、名单、编排、审核详情、影响分析使用独立页面而不是 Drawer。
- 首屏固定回答：当前阶段、是否正常、阻断数量、责任人、截止/窗口、下一动作。
- 对正式批次/名单/课表/成绩显示关键版本或 evidence identity。
- 任何高风险动作先 preview impact，再二次确认。
- 允许保留旧路由 redirect/alias；禁止一次重写整个 console。

### 8. 学生 PC / 小程序 / 教师小程序
- 只消费同一后端状态与 allowedActions，不在端侧重新计算正式资格。
- 移动端优先：今日/本周 → 我的待办 → 风险/结果更新 → 常用服务 → 全部服务。
- 失败必须给中文原因和下一步，不能用技术异常替代业务解释。
- 刷新、重登、换端后正式事实必须一致。
- 没有该角色业务职责时，不造“看起来完整”的伪入口。

### 9. 状态机 / allowedActions
- 先读取 current 枚举，禁止因为竞品状态名更好看就改现有状态机。
- 状态推进只通过 canonical service。
- UI 按后端 `allowedActions` 渲染，不使用本地 if/else 重建状态机。
- 归档/冻结后的普通动作必须 fail-closed。
- 退回、撤销、更正都保留历史原因，不 delete 正式事实。

### 10. RBAC / dataScope / 审计
- Permission Catalog 由 Control Plane / INT Authority 管理，本线只声明所需业务能力。
- 教务处、学院教务、任课教师、学生、学校管理员按真实角色验收。
- 学院范围必须 SQL/object scope fail-closed；空 scope 不能变全校。
- 高风险 override / publish / correction / archive 必须审计 before/after/reason。
- 敏感导出与页面查看使用相同 dataScope，不允许“页面看不到但Excel能导出”。

### 11. 幂等 / 事务 / 并发
- 所有创建/推进操作定义重复点击语义。
- 涉及共享容量、唯一 current head、名单换版、正式发布时使用真实 MySQL 验证。
- 固定锁顺序，避免不同入口互锁。
- deadlock/retry 不能产生半写、双写或重复通知。
- 事务成功与消息送达分离：业务事实先成功，通知 Outbox 异步补偿。

### 12. 导入 / 导出 / 打印 / 对账
- 新增批量导入一律优先扩展 Academic File Exchange：scan → dry-run → error xlsx → confirm → reread。
- 禁止模块自己造第二 UploadJob / parser / download ticket。
- 正式导出带生成时间、学期/批次、数据范围、必要版本/水印。
- 导入后必须形成 imported/reused/rejected/conflict/count/hash/relationship reconciliation。
- 纸面/电子打印件是正式事实的 projection，不成为第二数据库真值。

### 13. Event / Outbox / 通知
- 先定义 `business fact → event → audience resolver → delivery → retry/dead`。
- 消息失败不得回滚已成功业务事实。
- 同一业务事件使用 dedupe key 防重复轰炸。
- 关键通知必须能在运维侧看 pending/dead/lag。
- 是否通知家长、短信、邮件等由学校策略决定，不在 Domain 硬编码。

### 14. 迁移 / 兼容 / 脏数据
- 先 inventory：当前行数、空值、重复键、旧状态、孤儿引用、legacy caller。
- 若迁移必须给 `backfill → dual-read/compat → cutover → reconciliation → retire` 顺序。
- 旧历史无法证明的新语义不得反推伪造。
- COMPAT 退役必须 repo search 零调用 + 四端 Gold + exact-head canonical 通过。
- 任一 open PR 触碰同文件时重新做 collision audit。

### 15. RED tests
- mock/network fake RED。
- console error RED。
- P0/P1>0却签字RED。
- R11未COMPLETED却上线RED。
- 必须新增至少一个跨租户/跨学院越权负向。
- 必须新增重复提交或错误状态负向。
- 必须新增数据损坏 fail-closed 负向。
- 不允许通过弱化现有断言让新功能变绿。

### 16. Real MySQL / E2E / Gold
- 涉及锁、唯一约束、容量、ScopeHead、RosterVersion、publish 的路径必须跑真实 MySQL。
- E2E 不 mock 正式网络写链，不忽略 console error。
- 写后必须 `reread → refresh → re-login/换端` 仍成立。
- 对所有被修改的 KEEP 模块跑 no-regression。
- 证据绑定 exact HEAD；新 commit 后重新判断旧 Gold 是否仍有效。

### 17. Definition of Done
- 真实角色能完成本专题主任务，不需要 SQL 或管理员手工改库。
- 业务失败可解释，有责任人和下一步。
- 没有新增第二 Authority / 第二状态机 / 第二名单 / 第二正式成绩。
- 数据可导入、可对账、可追溯；需要打印/导出时有正式入口。
- 至少一条 Happy Gold + 一条 Negative Gold + 必要并发证据。
- 本专题 P0 blocker = 0，P1 若保留必须有明确学校策略或后续 owner。

### 18. 明确禁止
- 禁止“竞品有，所以直接建表”。
- 禁止为了页面方便放松后端 gate。
- 禁止名称匹配替代 stable ID。
- 禁止 client-side 正式资格计算。
- 禁止 shared file 被本线抢写。
- 禁止本专题之外顺手重构成熟模块。
- 禁止把 queued/pending 当成功。

# Ⅷ. D 线页面级施工矩阵

## D-PAGE-01 — 毕业审核总览
- **页面唯一主任务**：围绕“毕业审核总览”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-02 — 学生毕业详情与逐项证据
- **页面唯一主任务**：围绕“学生毕业详情与逐项证据”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-03 — 学位审核（按学校启用）
- **页面唯一主任务**：围绕“学位审核（按学校启用）”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-04 — 学生学业进度
- **页面唯一主任务**：围绕“学生学业进度”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-05 — What-if模拟
- **页面唯一主任务**：围绕“What-if模拟”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-06 — 学分/成绩认定
- **页面唯一主任务**：围绕“学分/成绩认定”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-07 — 成绩单/查询件
- **页面唯一主任务**：围绕“成绩单/查询件”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-08 — 十三域归档总览
- **页面唯一主任务**：围绕“十三域归档总览”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-09 — 归档域详情
- **页面唯一主任务**：围绕“归档域详情”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-10 — 归档后纠错
- **页面唯一主任务**：围绕“归档后纠错”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-11 — 评教运行健康
- **页面唯一主任务**：围绕“评教运行健康”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-12 — 20K性能证据
- **页面唯一主任务**：围绕“20K性能证据”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-13 — 消息运维
- **页面唯一主任务**：围绕“消息运维”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-14 — 备份恢复演练
- **页面唯一主任务**：围绕“备份恢复演练”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-15 — 迁移切换Readiness
- **页面唯一主任务**：围绕“迁移切换Readiness”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-16 — R11完整学期Pilot
- **页面唯一主任务**：围绕“R11完整学期Pilot”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-17 — 学校交付证据包
- **页面唯一主任务**：围绕“学校交付证据包”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## D-PAGE-18 — 权限/数据范围验收矩阵
- **页面唯一主任务**：围绕“权限/数据范围验收矩阵”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。


# Ⅸ. D 线真实学校验收场景目录

每个场景施工时展开成 Given / When / Then，并绑定 exact SHA、角色、tenant、term、business IDs、API结果、必要MySQL/Playwright和对账查询。

## D-SC-001 — 正常毕业PASS
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-002 — 学分不足FAIL
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-003 — 必修未过FAIL
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-004 — provider缺失BLOCKED
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-005 — 补考后新EvaluationRun PASS
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-006 — 成绩更正后新run
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-007 — 实习证据缺失
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-008 — 毕设证据缺失
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-009 — Recognition后毕业进度重算
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-010 — 毕业PASS但学位FAIL
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-011 — 不授学位学校NOT_APPLICABLE
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-012 — what-if转专业模拟不得写正式结论
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-013 — 正式成绩单生成
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-014 — 非正式成绩单
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-015 — 成绩单不含未发布成绩
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-016 — 成绩单跨学生下载负向
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-017 — 在读证明VERIFY-FIRST
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-018 — 评教100并发
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-019 — 评教200并发
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-020 — 评教重复提交
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-021 — Roster外评教拒绝
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-022 — 20K学生课表查询
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-023 — 20K成绩统计
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-024 — Selection 1k burst证据归档
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-025 — 大导出异步
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-026 — Outbox dead告警
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-027 — 调课消息补偿
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-028 — 考试改期消息补偿
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-029 — 成绩发布消息补偿
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-030 — ImportJob卡SCANNING告警
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-031 — 数据库PITR恢复
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-032 — FileObject恢复
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-033 — 恢复后ScopeHead对账
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-034 — 恢复后Roster hash对账
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-035 — 恢复后EffectiveGrade对账
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-036 — 恢复后ArchiveManifest对账
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-037 — 十三域全部PASS
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-038 — Selection未启用NOT_APPLICABLE
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-039 — Selection启用未LOCK阻断Archive
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-040 — 归档后普通写409
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-041 — 归档后成绩纠错
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-042 — 归档后毕业纠错
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-043 — 旧manifest保持不变
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-044 — T-14第一次迁移dry-run
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-045 — T-1最终增量
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-046 — T0新系统唯一writer
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-047 — 旧系统只读
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-048 — T+1业务reconciliation
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-049 — 学院A读B学院负向
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-050 — 邻租户sentinel
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-051 — 教师越权负向
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-052 — 学生越权负向
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-053 — R11 BASELINE
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-054 — R11 PRE_TERM
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-055 — R11 IN_TERM
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-056 — R11 EXAM
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-057 — R11 GRADE
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-058 — R11 ARCHIVE
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-059 — R11 mock-on禁止complete
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-060 — R11 realData未确认禁止complete
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-061 — R11六阶段全绿complete
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-062 — clean tenant最终验收
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-063 — migrated tenant最终验收
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## D-SC-064 — 学校交付包known P0/P1=0
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。


# Ⅹ. V1.4 完整基线保留区


> 以下完整保留 V1.4 原文，防止 V1.5 新增对标设计时丢失 00/00A/00B/00C、01–13、00D–G 与 INT 规则。发生明确冲突时，以 V1.5 的 CURRENT 代码事实与 Reconciliation 裁决为准。


# D — Graduation/Delivery：毕业·归档·非主链·性能·运维·R11 — V1.4 四线并行唯一施工总册

> 仓库：`penghaibin9/saas`  
> 审计来源基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 文档来源：V1.3 详细模块文档 + 总控/四端/文件台账/安全边界  
> 目标：**一份文档即可驱动该施工线持续施工，同时遵守全局 INT Authority。**


# 四线并行施工共同 Integration Authority

> 整理版本：V1.4 四线并行施工版  
> 来源基线：V1.3 全套详细审计文档  
> 审计代码基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 整理时间：2026-08-16 21:50 +08:00  
> 原则：**V1.4 只重排施工组织，不改变 V1.3 的业务 Authority 裁决，不降低任何 KEEP/BLOCKER/Go-Live 标准。**

## 1. 四线与 INT 的关系

本轮只有四个长期施工智能体：

| 施工线 | 业务范围 | 写权限 |
|---|---|---|
| A — Semester/Core | 01–04 + 新校实施/迁移 | 上游教务 Domain owner |
| B — Schedule/Selection | 05–07 | 排课/选课/Roster 主链 owner |
| C — Teaching Execution | 08–10 | 教学运行/考务/成绩 owner |
| D — Graduation/Delivery | 11–13 + Go-Live/性能/运维 | 毕业/归档/验证封板 owner |

`INT — Integration Authority` **不是第五个业务施工体**。  
INT 是四线共用的单 Owner 规则：凡涉及 shared file、Alembic、权限 Catalog、route registration、公共 Data Exchange、最终 Gold，必须进入 INT 队列，由唯一集成 Owner 修改或裁决。

## 2. 不可改变的 Authority 主链

```text
AaTerm / Calendar / TimeSlot
        ↓
AaCourse(versioned)
        ↓
AaProgram + ProgramCourse + Binding
        ↓
Opening Projection（derived，不建第二套表）
        ↓
AaTeachingTaskBatch + AaTeachingTask
        ↓                     ↓
TeachingClass/Roster       Scheduling
        ↓                     ↓
TeachingRoster       ScopeHead → Published Schedule Truth
        │                     │
        ├──────────┬──────────┘
        │          │
        │          ▼
        │   教师/学生正式课表
        │
        ├─ ADMIN_CLASS
        ├─ SELECTION_LOCK
        ├─ MANUAL
        └─ RETAKE
        ↓
Attendance / Exam / Grade RosterConsumerSnapshot
        ↓
Effective Grade
        ↓
Credits / GraduationEvaluationRun / GraduationDecisionFact
        ↓
13-domain Archive / ArchiveManifest
```

铁律：
- Selection 不是固定行政班课程的必经步骤。
- TeachingRoster 是“谁正式修这门课”的唯一汇流 Authority。
- Scheduling 只回答“什么时候、在哪里”，Roster 回答“谁参加”。
- 不新造 OpeningPlan、OfficialSchedule、Roster、EffectiveGrade 第二真值。
- stable ID 是业务身份；名称仅 snapshot/display。
- 正式事实写操作必须继续受 tenant + RBAC + dataScope + archive guard + audit 约束。

## 3. GLOBAL SINGLE OWNER：四线禁止直接抢写

以下文件/文件族默认由 INT 单 Owner：

```text
backend/app/api/v1/route_registration.py
backend/app/core/permissions.py
backend/app/core/permission_catalog.py
backend/app/models/data_exchange.py
backend/app/services/data_exchange_confirm_service.py

backend/app/modules/academic_affairs/services/__init__.py
backend/app/models/academic_affairs_registry.py

backend/alembic/versions/**
Alembic heads / migration merge

frontend/src/config/navPlan.js
shared/contracts/** permission / IAM / cross-domain contracts
```

规则：
1. A/B/C/D 发现确需改 shared file，只提交“集成变更请求 + 最小 patch 需求 + RED test”。
2. INT 先做 collision audit，再由单 Owner 落 shared change。
3. shared change 一旦进入集成线，所有依赖它的旧 exact-head 证据失效，必须重新验证。
4. 禁止四条线各自复制 Permission Registry、Data Exchange、route registration 或 migration head。

## 4. 当前开放 PR Collision Ledger

### PR #96 — academic semester rehearsal
已知触碰：
```text
.github/workflows/academic-semester-rehearsal.yml
backend/app/models/academic_affairs_registry.py
backend/app/modules/academic_affairs/services/__init__.py
backend/tests/test_aa_mobile_grade_entry_v2.py
miniapp/src/pages/teacher/academic-affairs/grade-entry.vue
scripts/check/academic-semester-rehearsal.sh
```

影响：
- C 线改教师小程序成绩页前必须先 re-audit #96。
- A/B/C/D 不得把 #96 未合并内容当 main 已有事实。
- `services/__init__.py`、`academic_affairs_registry.py` 由 INT 控制。

### PR #133 — Control Plane Option B
当前大范围触碰：
- `route_registration.py`
- `permissions.py` / `permission_catalog.py`
- system/platform IAM
- identity import / Data Exchange shared jobs
- Alembic
- shared permission contracts

影响：
- A 线课程/培养方案导入若扩展 Data Exchange，只能复用现有 Academic File Exchange，涉及共享 Data Exchange schema/service 时必须交 INT。
- 四线不得在教务里复制 Control Plane Permission Catalog。
- 新迁移必须先与 #133 当前 migration head 做碰撞审计。

## 5. 四线分支与集成线建议

```text
agent/academic-v14-a-semester-core
agent/academic-v14-b-schedule-selection
agent/academic-v14-c-teaching-execution
agent/academic-v14-d-graduation-delivery

integration/academic-v14-school-gold
```

集成线只承担：
- shared files；
- cross-line contract；
- migration owner；
- 权限/路由 owner；
- 四线按顺序回收；
- exact-head canonical Gold；
- R11 最终签字证据。

## 6. 每一刀强制施工协议

修改前：

```text
exact main SHA
→ 本线 HEAD
→ open PR collision
→ 文件 owner
→ upstream/downstream contract
→ existing tests
→ RED contract
```

修改后：

```text
targeted unit/service
→ API/DTO contract
→ 本线前端真实入口
→ MySQL concurrency（涉及锁/唯一/状态才跑）
→ KEEP no-regression
→ exact-head evidence
→ commit
→ 自动进入本线下一施工批
```

禁止：
- `git add -A` 式不审范围提交；
- skip/xfail/ignore 假绿；
- 为了修 CI 放宽业务约束；
- 用 SQLite 代替 MySQL 并发 Gold；
- 在本线之外“顺手重构”成熟模块；
- queued/pending 当 success；
- force push；
- 未经最终明确授权直接合并 `main`。

## 7. 跨线 Contract Freeze 顺序

```text
A：Term/Course/Program/TeachingTask Formation Contract
        ↓ freeze
B：Published Schedule + Selection Projection + TeachingRoster Contract
        ↓ freeze
C：Attendance/Exam/Grade RosterConsumer Contract
        ↓ freeze
D：Graduation Provider + Archive + R11/Go-Live Contract
        ↓
INT：四端完整学期 Gold
```

允许并行，但**下游只能提前做审计/RED/UX/测试 harness，不能在上游 Contract 未 freeze 前自行发明字段或 Authority**。

## 8. 四端统一要求

四端固定：
1. 管理/教师 PC：`frontend/`
2. 学生 PC：`student-portal/`
3. 教师小程序：`miniapp/` teacher
4. 学生小程序：`miniapp/` student

每个正式页面首屏必须回答：
- 当前状态；
- 能做什么；
- 为什么不能做；
- 下一步；
- 管理/教师页的重要事实来自哪个批次/版本/名单版本。

允许 UI 密度不同；不允许业务真值不同。

## 9. Merge / 回收顺序

子线可以持续施工并持续 commit，但进入 integration 的回收顺序固定：

```text
A Contract Freeze
→ 回收 A
→ B rebase/sync + collision
→ B Contract Freeze
→ 回收 B
→ C sync + mature-chain regression
→ 回收 C
→ D sync + delivery gates
→ 回收 D
→ INT exact-head Gold
```

如果某线需要依赖尚未回收的上游代码，可在本线使用明确 dependency commit/branch 做验证，但**最终回收前必须基于 integration exact head 重放**。

---



---


# D — Graduation/Delivery 学校交付封板施工总控

## D.1 责任边界

D 负责：
- 11 学分 / 毕业资格；
- 12 十三域归档；
- 13 非主链成熟度再验收；
- 00D R11 Go-Live；
- 00F 性能并发；
- 00G 运维/恢复/交付证据。

D 是**验证、封板、交付 Owner**，不是第四套 Domain Writer。

如果 D 发现 A/B/C 域业务缺口：
- 记录 blocker；
- 指派回对应 line；
- 不在 D 里复制一套业务 writer 绕过去。

## D.2 施工批次

### D0 — Delivery Baseline Freeze
拿 A/B/C freeze contract，冻结：
- exact HEAD；
- migration head；
- permission matrix；
- four-end routes；
- R11 current evidence；
- archive current policy；
- 20K baseline。

### D1 — Graduation Provider Audit
每个 graduation condition：
- rule；
- source provider；
- evidence timestamp；
- evidence identity；
- PASS/FAIL/UNKNOWN；
- remediation route。

任何 provider 缺失：
`UNKNOWN/BLOCKED`，不能 PASS。

场景：
- 正常毕业；
- 学分不足；
- 必修未过；
- 补考后转 PASS；
- 成绩更正后重算；
- 实习/毕设证据缺失；
- 费用/离校类证据缺失（若规则启用）；
- 延毕。

### D2 — Graduation Immutable Replay
证明：
`FAIL evaluation run → 修复证据 → new run → PASS decision`

要求：
- Decision 引 exact run；
- correction 追加；
- 客户端不重算；
- 旧 run 可重放。

### D3 — 13-domain Archive Semantic Seal
每域：
- PASS；
- NOT_APPLICABLE；
- BLOCKED；
- ruleCode；
- count；
- deepLink。

特别：
- Selection 本学期未启用 ≠ blocker；
- 启用但未终结 = blocker；
- archive 后普通 write = 409；
- correction 只能走 PostArchiveCorrectionCase。

### D4 — 非主链成熟度 Reconciliation
逐项审：
- registration；
- status change；
- evaluation；
- textbook；
- level exam；
- major split；
- warning；
- certificate/query copy；
- makeup/retake/exemption/clearance；
- dashboard/readiness。

每项四态：
`RESOLVED_BY_CODE / STILL_OPEN / OBSOLETE_BY_ARCHITECTURE / NEEDS_RETEST`

保护 ≠ 自动判成熟。

### D5 — Evaluation Peak / Other Scale Hotspots
学生评教已具备：
- 本人；
- formal roster；
- anonymous HMAC；
- duplicate protection。

但同 EvaluationTask row lock 可能热点。

做真实 MySQL：
- 50/100/200 同任务并发；
- school-wide deadline burst；
- lock wait/deadlock；
- p95/p99；
- submitted_count；
- duplicate proof。

不达标再最小 harden，不建第二 Evaluation Truth。

### D6 — 20K / Performance SLO
最低建议：
- 20k students；
- 2k staff；
- 500–1000 classes；
- 5k+ TeachingTask；
- 100k+ schedule occurrences；
- multi-term grade/archive history。

关注：
- SQL pagination；
- no Python full materialize；
- p95/p99；
- DB connections；
- slow SQL；
- CPU/memory；
- lock waits。

### D7 — Message / Outbox / Scheduler Delivery Matrix
覆盖：
- schedule publish；
- schedule change；
- selection open/deadline/win/lose/cancel/reselect/LOCK；
- exam publish/change/defer；
- grade publish/recheck；
- registration/status change。

每种事件：
`business fact → outbox → audience → delivery → retry/dead → receipt/ops`

消息失败不回滚正式事实。

### D8 — Backup / Restore Drill
ArchiveManifest ≠ backup。

必须验证：
- MySQL backup + binlog/PITR or equivalent；
- FileObject backup；
- config/key backup；
- restore to isolated environment；
- migration head；
- key counts/hashes；
- ScopeHead；
- Roster versions；
- Exam snapshot；
- Effective Grade；
- GraduationDecisionFact；
- ArchiveManifest；
- files readable；
- R11 can reread.

### D9 — R11 Semantic Hardening
R11：
`BASELINE → PRE_TERM → IN_TERM → EXAM → GRADE → ARCHIVE`

SELECTABLE 校正：
- schedule 可先 ready；
- final roster 等 LOCK；
- PRE_TERM 区分
  `SCHEDULE_READY / ROSTER_PENDING_SELECTION / ROSTER_READY / DOWNSTREAM_READY`。

不能降低 Attendance/Exam/Grade final roster gate。

### D10 — Four-end Complete Semester Gold
同一真实/正式测试租户同一学期：
- ADMIN_FIXED 课程；
- SELECTABLE 课程；
- attendance；
- schedule change；
- exam；
- grade；
- makeup/defer；
- graduation precheck；
- archive。

四端：
- 教务处；
- 学院教务；
- teacher PC/miniapp；
- student PC/miniapp。

必须无 mock/no network fake/no console error，写后 reread/refresh 生存。

### D11 — R11 Real School Pilot
只有：
- production；
- DB enabled；
- mock off；
- realDataConfirmed；
- six stages pass；
才允许 `COMPLETED`。

R11 不造数据，只冻结真实 evidence hash。

### D12 — School Release Evidence Package
至少：
1. exact SHA/build digest；
2. migration head；
3. data dictionary；
4. permission matrix；
5. school parameter confirmation；
6. migration reconciliation；
7. four-end acceptance；
8. performance/concurrency；
9. security/data-scope negative；
10. backup/restore；
11. R11 pilot；
12. ops/runbook；
13. known limitations P0/P1 = 0。

## D.3 D 线禁止事项
- 不复制 A/B/C writer；
- 不把缺 provider 当 PASS；
- 不以 ArchiveManifest 冒充灾备；
- 不用 demo/seed 签 R11；
- 不用单用户测试签性能；
- 不把 message enqueue 当 delivered；
- 不为了 R11 绿降低业务门禁；
- 不在 shared permission/route/migration 文件抢写。

## D.4 Final INT 回收 Gate
四线回收后，INT 最终顺序：
```text
migration/schema
→ Permission/route
→ A contracts
→ B schedule/selection/roster
→ C execution
→ D delivery
→ targeted
→ MySQL concurrency
→ 20K
→ four-end E2E
→ archive replay
→ R11
→ release evidence
```

任何一项新 commit 进入 exact HEAD 后，旧的最终 Gold 证据必须重新判断是否仍有效。


---

# 原 V1.3 详细施工内容完整整编：本线专项详细施工原文


---

## 来源文档：`11_学分与毕业资格_真实学校交付施工文档_V1.3.md`

# 11 — 学分 / 毕业资格：现有代码逐行审计 + 真实学校交付校正版 V1.3

> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 1. 当前成熟度

**🟢/🟡 事实层强，跨域供数继续硬化**

当前 Authority：`Effective Grade + Program requirements + cross-domain providers → GraduationEvaluationRun → GraduationDecisionFact`

## 2. 标记规则


| 标记 | 含义 | 施工约束 |
|---|---|---|
| **[KEEP]** | 已经是正式 Authority / 生产级强基座 | 禁止重写；只能补测试、补展示、补索引或局部修 bug |
| **[HARDEN]** | 当前可用，但存在边界、审计、性能或可解释性欠账 | 小步加固，保持 API/数据兼容 |
| **[REWIRE]** | 已有能力，但主链连接方式不正确或仍走旁路 | 优先“改连接”而不是“重建模块” |
| **[COMPAT]** | 兼容层 / facade / legacy 路由桥 | 等价替换与回归门禁完成前必须保留 |
| **[RETIRE-LATER]** | 可在未来退役 | 必须先证明无调用、无历史数据依赖、无路由合同依赖 |
| **[BLOCKER]** | 不修会让真实学校业务走不通或产生错误正式事实 | 上线前必须修；不得以 UI 隐藏、默认值或 mock 绕过 |


## 3. 数据结构审计

| 模型/事实 | 标记 | 当前代码结论 |
|---|---|---|
| GraduationEvaluationRun | [KEEP] | 每次正式预审 append-only，保存 input snapshot/hash/evaluator version |
| GraduationDecisionFact | [KEEP] | 决定引用 exact evaluation run，纠错追加新版本而不覆盖 |
| StudentAcademicFact | [KEEP] | 历史学籍身份按 as_of 重放 |

## 4. Router / Service / Guard 审计

| 文件 | 标记 | 逐函数/关键分支结论 |
|---|---|---|
| backend/app/modules/academic_affairs/routers/graduation_core_router.py | [KEEP] | 批次/生成/预审/学院审核/终审/归档完整 |
| backend/app/models/academic_affairs_stage_c3.py | [KEEP] | immutable graduation/archive facts |
| backend/app/modules/academic_affairs/services/__init__.py | [COMPAT/KEEP] | graduation evaluator/immutable truth 安装仍有兼容依赖 |

## 5. 四端前端审计

| 页面/客户端 | 标记 | 当前情况 |
|---|---|---|
| student-portal/src/views/academic/StudentGraduationAuditView.vue | [KEEP] | 只展示共享 evaluator 结果，不在页面重算 |
| student-portal/src/views/academic/StudentAcademicReadOnlyView.vue | [KEEP] | 学分只读投影 |
| miniapp/src/pages/student/academic-affairs/index.vue | [KEEP/HARDEN] | 毕业/学分入口已存在 |

## 四端定义

本总册中的“四端”固定指：

1. **管理 / 教师 PC：`frontend/`**  
   同一 PC 客户端，由 `RBAC + dataScope + navPlan` 决定教务处、学院教务、任课教师看到的工作区。
2. **学生 PC：`student-portal/`**
3. **教师小程序：`miniapp/` teacher side**
4. **学生小程序：`miniapp/` student side**

四端必须共享同一后端状态机、同一 TeachingTask、同一 Schedule Truth、同一 TeachingRoster、同一正式成绩事实。  
**允许 UI 密度不同，不允许业务真值不同。**


## 6. 真实学校使用前 BLOCKER

当前未发现需要推翻本模块才能使用的结构性 blocker；保留跨模块 Gold 验收。

## 7. HARDEN / REWIRE 清单

- 所有毕业 provider 缺事实必须 UNKNOWN/BLOCKED，不得“有记录即PASS”。
- 学生端显示适用培养方案版本与证据来源，但最终结论仍归正式审核。
- 修正成绩后通过 PostArchiveCorrectionCase 形成新 evaluation/decision，不重开学期。

## 8. 最小安全施工方式

immutable fact 结构禁止改成 mutable 单行结论。

## 本模块施工铁律

1. 不因为存在 legacy/facade 就直接删除；先证明 route shape、response DTO、权限、历史数据、四端调用全部等价。
2. 不新建第二套课程、计划、TeachingTask、Schedule、Roster、Grade、Graduation Truth。
3. 正常链使用 stable ID；名称只做 snapshot / display。
4. 数据损坏必须 fail-closed；不得用空 scope、默认规则、默认学期、默认名单假装成功。
5. 对正式事实的写操作继续受 `tenant + RBAC + dataScope + archive guard + audit` 约束。
6. 改 UI 优先让它消费现有强后端，而不是为了迁就旧 UI 放松后端。
7. MySQL 并发验证只在涉及行锁/唯一约束/状态推进的模块执行。


## 9. 必须补/保留的测试证据

- 现有 targeted unit/service tests：不得删、不得改弱断言。
- Router contract：method/path/permission/response envelope 不漂移。
- 四端至少覆盖本模块真实入口；没有本端业务职责的端必须验证“无错误入口/无伪按钮”。
- 若修改行锁、状态推进、唯一约束：真实 MySQL targeted concurrency。
- 只有 targeted 全绿后，才进入跨模块 semester flow / Playwright Gold。

---

# V1.3 真实学校交付增强层

> 本节是 V1.3 在 V1.2“保护成熟 Authority、修主链焊点”之上新增的**学校交付层**。  
> 任何开发智能体不得把这里的“上线准入”误解为重建业务模型；优先复用现有 Authority、File Exchange、R11 Semester Pilot、RBAC/DataScope、Outbox/Audit。

## 学校上线必须同时满足的 8 类证据

1. **业务正确**：状态机、权限、名单、课表、考试、成绩的 Authority 无旁路。
2. **可实施**：新学校可通过导入/配置而不是人工逐条录入完成基础数据建设。
3. **可操作**：教务处、学院教务、任课教师、学生在各自端能完成真实任务。
4. **可解释**：任何 BLOCKED 都有原因、责任角色、下一步、下钻入口。
5. **可对账**：导入、名单、排课、考试、成绩、归档均有 before/after、数量、hash/版本或可复核摘要。
6. **可承载**：真实 MySQL 下通过学校规模峰值测试，不能只跑单用户功能测试。
7. **可运维**：异步任务、消息、导入任务、归档、后台调度有 lag/dead/pending 指标和故障处置。
8. **可恢复**：数据库、文件对象、配置、迁移具备恢复演练证据；没有恢复演练不得签“可给学校正式上线”。

## V1.3 新增标记

| 标记 | 含义 |
|---|---|
| `[GO-LIVE-BLOCKER]` | 业务功能可能可跑，但不满足真实学校上线签字 |
| `[IMPLEMENTATION-BLOCKER]` | 新学校初始化/数据迁移无法低风险完成 |
| `[SCALE-BLOCKER]` | 小数据可用，但学校高峰/大数据量未经证明或有热点 |
| `[OPS-BLOCKER]` | 故障、异步任务、备份恢复、告警没有可操作闭环 |
| `[VERIFY-FIRST]` | 代码检索未能证明能力存在；先核 exact-head，确认缺失后才施工 |

## 真实学校增强：毕业资格与跨域证据

- R11/毕业预审必须使用真实 provider；任何 provider 缺失不是 PASS。
- 对每一项毕业条件显示：规则、结果、证据时间、证据来源、处理入口。
- 至少覆盖：正常毕业、学分不足、必修未过、补考后转 PASS、成绩更正后重算、实习/毕设证据缺失、费用未结清、延毕。
- 归档后纠错只允许 PostArchiveCorrectionCase 追加新事实。

**Go-Live DoD**
- 同一学生从 FAIL → 修复证据 → 新 EvaluationRun → PASS 可重放；
- 决定引用 exact evaluation run；
- 无客户端自行计算毕业结论；
- 证据缺失/冲突全部 fail-closed。

---

## 来源文档：`12_十三域归档与学期封存_真实学校交付施工文档_V1.3.md`

# 12 — 十三域归档 / 学期封存：现有代码逐行审计 + 真实学校交付校正版 V1.3

> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 1. 当前成熟度

**🟢 架构成熟**

当前 Authority：`13 domain semantic evaluators → ArchiveBatch → ArchiveManifest; archived term immutable; corrections append new manifest`

## 2. 标记规则


| 标记 | 含义 | 施工约束 |
|---|---|---|
| **[KEEP]** | 已经是正式 Authority / 生产级强基座 | 禁止重写；只能补测试、补展示、补索引或局部修 bug |
| **[HARDEN]** | 当前可用，但存在边界、审计、性能或可解释性欠账 | 小步加固，保持 API/数据兼容 |
| **[REWIRE]** | 已有能力，但主链连接方式不正确或仍走旁路 | 优先“改连接”而不是“重建模块” |
| **[COMPAT]** | 兼容层 / facade / legacy 路由桥 | 等价替换与回归门禁完成前必须保留 |
| **[RETIRE-LATER]** | 可在未来退役 | 必须先证明无调用、无历史数据依赖、无路由合同依赖 |
| **[BLOCKER]** | 不修会让真实学校业务走不通或产生错误正式事实 | 上线前必须修；不得以 UI 隐藏、默认值或 mock 绕过 |


## 3. 数据结构审计

| 模型/事实 | 标记 | 当前代码结论 |
|---|---|---|
| AaArchiveBatch / AaArchiveItem | [KEEP] | 操作批次/实时结果投影 |
| ArchiveManifest | [KEEP] | 版本化不可变归档清单 |
| PostArchiveCorrectionCase | [KEEP] | 归档后唯一正式写入口，目前 GRADE/GRADUATION |

## 4. Router / Service / Guard 审计

| 文件 | 标记 | 逐函数/关键分支结论 |
|---|---|---|
| backend/app/modules/academic_affairs/routers/archive_core_router.py | [KEEP] | create/check/confirm/precheck/download log |
| backend/app/modules/academic_affairs/services/academic_affairs_archive_service.py | [KEEP] | 13域语义 + operational policy 编排 |
| backend/app/modules/academic_affairs/services/academic_affairs_archive_domain_policy.py | [KEEP] | 明确 Selection 未启用时 PASS，不把可选模块缺席当故障 |
| backend/app/models/academic_affairs_stage_c3.py | [KEEP] | manifest/correction append-only |

## 5. 四端前端审计

| 页面/客户端 | 标记 | 当前情况 |
|---|---|---|
| frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue | [KEEP/HARDEN] | 应把 13 域 result/ruleCode/blockingCount/route 做成可下钻工作台 |
| frontend/src/modules/academicAffairs/views/AaDashboardView.vue | [KEEP] | 学期 readiness/阻断/风险已有结论优先结构 |

## 四端定义

本总册中的“四端”固定指：

1. **管理 / 教师 PC：`frontend/`**  
   同一 PC 客户端，由 `RBAC + dataScope + navPlan` 决定教务处、学院教务、任课教师看到的工作区。
2. **学生 PC：`student-portal/`**
3. **教师小程序：`miniapp/` teacher side**
4. **学生小程序：`miniapp/` student side**

四端必须共享同一后端状态机、同一 TeachingTask、同一 Schedule Truth、同一 TeachingRoster、同一正式成绩事实。  
**允许 UI 密度不同，不允许业务真值不同。**


## 6. 真实学校使用前 BLOCKER

当前未发现需要推翻本模块才能使用的结构性 blocker；保留跨模块 Gold 验收。

## 7. HARDEN / REWIRE 清单

- 归档页不能只显示有/无数据，要显示 PASS/BLOCKED/NOT_APPLICABLE 的语义。
- Selection/Evaluation 等本学期未启用时不阻断；未终结才阻断。
- 禁止通过普通 unfreeze 绕过 immutable guard。

## 8. 最小安全施工方式

保留 13-domain policy 与 immutable manifest；只加强展示与 provider 证据。

## 本模块施工铁律

1. 不因为存在 legacy/facade 就直接删除；先证明 route shape、response DTO、权限、历史数据、四端调用全部等价。
2. 不新建第二套课程、计划、TeachingTask、Schedule、Roster、Grade、Graduation Truth。
3. 正常链使用 stable ID；名称只做 snapshot / display。
4. 数据损坏必须 fail-closed；不得用空 scope、默认规则、默认学期、默认名单假装成功。
5. 对正式事实的写操作继续受 `tenant + RBAC + dataScope + archive guard + audit` 约束。
6. 改 UI 优先让它消费现有强后端，而不是为了迁就旧 UI 放松后端。
7. MySQL 并发验证只在涉及行锁/唯一约束/状态推进的模块执行。


## 9. 必须补/保留的测试证据

- 现有 targeted unit/service tests：不得删、不得改弱断言。
- Router contract：method/path/permission/response envelope 不漂移。
- 四端至少覆盖本模块真实入口；没有本端业务职责的端必须验证“无错误入口/无伪按钮”。
- 若修改行锁、状态推进、唯一约束：真实 MySQL targeted concurrency。
- 只有 targeted 全绿后，才进入跨模块 semester flow / Playwright Gold。

---

# V1.3 真实学校交付增强层

> 本节是 V1.3 在 V1.2“保护成熟 Authority、修主链焊点”之上新增的**学校交付层**。  
> 任何开发智能体不得把这里的“上线准入”误解为重建业务模型；优先复用现有 Authority、File Exchange、R11 Semester Pilot、RBAC/DataScope、Outbox/Audit。

## 学校上线必须同时满足的 8 类证据

1. **业务正确**：状态机、权限、名单、课表、考试、成绩的 Authority 无旁路。
2. **可实施**：新学校可通过导入/配置而不是人工逐条录入完成基础数据建设。
3. **可操作**：教务处、学院教务、任课教师、学生在各自端能完成真实任务。
4. **可解释**：任何 BLOCKED 都有原因、责任角色、下一步、下钻入口。
5. **可对账**：导入、名单、排课、考试、成绩、归档均有 before/after、数量、hash/版本或可复核摘要。
6. **可承载**：真实 MySQL 下通过学校规模峰值测试，不能只跑单用户功能测试。
7. **可运维**：异步任务、消息、导入任务、归档、后台调度有 lag/dead/pending 指标和故障处置。
8. **可恢复**：数据库、文件对象、配置、迁移具备恢复演练证据；没有恢复演练不得签“可给学校正式上线”。

## V1.3 新增标记

| 标记 | 含义 |
|---|---|
| `[GO-LIVE-BLOCKER]` | 业务功能可能可跑，但不满足真实学校上线签字 |
| `[IMPLEMENTATION-BLOCKER]` | 新学校初始化/数据迁移无法低风险完成 |
| `[SCALE-BLOCKER]` | 小数据可用，但学校高峰/大数据量未经证明或有热点 |
| `[OPS-BLOCKER]` | 故障、异步任务、备份恢复、告警没有可操作闭环 |
| `[VERIFY-FIRST]` | 代码检索未能证明能力存在；先核 exact-head，确认缺失后才施工 |

## 真实学校增强：归档与恢复

归档业务模型继续 `[KEEP]`，但“可给学校用”必须加两个维度：

### 业务封存
13 域必须按语义 PASS/NOT_APPLICABLE/BLOCKED；所有 blocker 可下钻。
确认 ARCHIVED 后普通业务写全部拒绝。

### 基础设施恢复
`[OPS-BLOCKER]` 业务 ArchiveManifest 不是数据库备份，也不是灾备。
上线前必须另有：
- MySQL 自动备份 + binlog/PITR 或等价能力；
- FileObject/附件备份；
- 配置/密钥备份策略；
- 恢复演练；
- 恢复后 ArchiveManifest / row counts / hashes 对账。

**Go-Live DoD**
- 至少一次“从备份恢复到隔离环境”的演练报告；
- 归档后正常写 409；
- 合法更正追加新 Manifest，不改旧 Manifest；
- 恢复后 13 域关键 count/hash 一致。

---

## 来源文档：`13_非主链功能保护与成熟度再验收_V1.3.md`

# 13 — 非主链功能保护清单：不要为了打通主链把现有教务功能做没 — V1.3


> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 当前已经存在、应默认保护的功能池

这些能力不是本轮“主链焊接”的重写对象：

- 学籍名册 / 敏感字段 reveal / 导入导出；
- 学期注册、资格核验、未注册学生、暂缓注册、注册归档；
- 学籍信息更正与学籍异动；
- 课程材料、启停、版本、引用；
- 培养方案版本/审核/绑定/实践段/学分要求/毕业要求；
- 教学任务教师分配、教师确认、合班/拆班、学院/教务审核；
- 教室资源与借用；
- 班级/教师/学生/教室/教学班多视角课表；
- 调停课与审批；
- Selection FCFS、LOTTERY、补退选、低人数、冲突报表、统计、归档；
- 考勤与统计；
- 考务自动定时/排考、考场、座位、监考、巡考、异常、缓考；
- 补考/重修/免修/清考；
- 成绩固定三段、动态成绩项、Excel、学院审核、教务发布、复查、更正、认定；
- 学生评教；
- 教材征订/发放/费用；
- 等级考试；
- 专业分流；
- 学业预警；
- 学分/GPA；
- 毕业资格审核；
- 证书/查询件；
- 十三域归档、归档后正式纠错；
- 教务 dashboard/readiness/stats snapshot。

## 学生 PC 保护

`student-portal/src/router/academicRoutes.js` 的独立页面结构默认 `[KEEP]`。  
尤其 registration / selection / evaluation / recheck / exam / makeup 已有专门页面和真实 server call，禁止“统一 UI”时退回大综合页。

## 教师端保护

- 教师 TeachingTask 本人确认；
- 教师正式课表；
- 教师考勤 Task-first；
- 教师成绩录入 + roster + quality；
- 调停课与审批；
- 待办深链。

## 本轮允许改的范围

只允许为主链打通做：
- 稳定 ID / DTO 接线；
- allowedActions / blockers projection；
- UI 状态解释；
- fail-closed；
- transaction/lock bug；
- 数据治理/对账；
- targeted performance；
- E2E / contract test。

**禁止用“重构”为名删功能。**

---

# V1.3 真实学校交付增强层

> 本节是 V1.3 在 V1.2“保护成熟 Authority、修主链焊点”之上新增的**学校交付层**。  
> 任何开发智能体不得把这里的“上线准入”误解为重建业务模型；优先复用现有 Authority、File Exchange、R11 Semester Pilot、RBAC/DataScope、Outbox/Audit。

## 学校上线必须同时满足的 8 类证据

1. **业务正确**：状态机、权限、名单、课表、考试、成绩的 Authority 无旁路。
2. **可实施**：新学校可通过导入/配置而不是人工逐条录入完成基础数据建设。
3. **可操作**：教务处、学院教务、任课教师、学生在各自端能完成真实任务。
4. **可解释**：任何 BLOCKED 都有原因、责任角色、下一步、下钻入口。
5. **可对账**：导入、名单、排课、考试、成绩、归档均有 before/after、数量、hash/版本或可复核摘要。
6. **可承载**：真实 MySQL 下通过学校规模峰值测试，不能只跑单用户功能测试。
7. **可运维**：异步任务、消息、导入任务、归档、后台调度有 lag/dead/pending 指标和故障处置。
8. **可恢复**：数据库、文件对象、配置、迁移具备恢复演练证据；没有恢复演练不得签“可给学校正式上线”。

## V1.3 新增标记

| 标记 | 含义 |
|---|---|
| `[GO-LIVE-BLOCKER]` | 业务功能可能可跑，但不满足真实学校上线签字 |
| `[IMPLEMENTATION-BLOCKER]` | 新学校初始化/数据迁移无法低风险完成 |
| `[SCALE-BLOCKER]` | 小数据可用，但学校高峰/大数据量未经证明或有热点 |
| `[OPS-BLOCKER]` | 故障、异步任务、备份恢复、告警没有可操作闭环 |
| `[VERIFY-FIRST]` | 代码检索未能证明能力存在；先核 exact-head，确认缺失后才施工 |

## V1.3 对“非主链功能保护”的修正

V1.2 的“存在即保护”要升级为“存在能力先保护，但成熟度另验”。

特别是：
- **学生评教**：当前 main 已做到学生本人、正式 TeachingRoster、匿名 HMAC 去重，业务正确性明显成熟；但同一 EvaluationTask 提交使用任务行 `FOR UPDATE` 串行化，且匿名 token 在 JSON 中查询。全校集中评教可能形成热点，因此改标：
  **`[KEEP correctness / SCALE-HARDEN]`**。
- 教材、等级考试、专业分流、证书等：继续禁止误删，但在宣称“学校生产成熟”前必须各自至少有真实数据、权限、导入/导出、异常流、E2E 证据。
- 历史欠账文件不能直接当当前事实；V1.3 增加“历史欠账 reconciliation”：
  `RESOLVED_BY_CODE / STILL_OPEN / OBSOLETE_BY_ARCHITECTURE / NEEDS_RETEST` 四态，每条必须有代码或测试证据。

**保护 ≠ 自动判定成熟。**

---

# 原 V1.3 详细施工内容完整整编：本线横向交付/实施原文


---

## 来源文档：`00D_真实学校上线准入_Gate与R11完整学期试点_V1.3.md`

# 00D — 真实学校上线准入 Gate 与 R11 完整学期试点 — V1.3

> 基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 目标：这份文件是“能否交给真实学校”的最终签字规则，不是开发进度表。

## 一、上线准入分四层

### Gate A：环境真实
- production deployment；
- DB enabled；
- mock login disabled；
- 目标 tenant 为真实学校；
- tenant 状态允许业务写；
- 正式域名/HTTPS/认证链正常。

### Gate B：数据真实
- 学校组织、专业、班级；
- 师生唯一身份绑定；
- 正式学期；
- 课程库；
- 生效培养方案及绑定；
- 教室/作息；
- 教务角色与 dataScope；
- 无危险 demo seed / 跨租户 seed。

### Gate C：业务真实
至少同一真实学期跑：
1. ADMIN_FIXED 课程完整链；
2. SELECTABLE 课程完整链；
3. 一次真实考勤；
4. 一次调停课；
5. 一次考试发布/座位/监考；
6. 一次教师成绩提交→学院审核→教务发布；
7. 一次补考/重修或缓考；
8. 一次毕业预审；
9. 十三域归档。

### Gate D：运营真实
- 关键消息投递可观测；
- 导入/导出有 FileObject/Job/审计；
- scheduler 无长期 lag/dead；
- 备份恢复演练通过；
- 20K + 峰值测试通过；
- 校方验收账号按真实角色验证。

## 二、R11 必须升级为最终签字 Gate

当前 main 已有：
`BASELINE → PRE_TERM → IN_TERM → EXAM → GRADE → ARCHIVE`

R11 只读取真实事实并冻结 evidence hash，不负责造数据。  
**只有六阶段全绿 + production + mock off + realDataConfirmed 才允许 COMPLETED。**

V1.3 要求：
- 管理 PC 增加“真实学期上线验收”工作区，直接消费 semester-pilot API；
- 显示每阶段 blocker/warning/evidenceHash；
- BLOCKER 必须下钻到业务页；
- 完成动作必须二次确认；
- R11 的 `COMPLETED` 记录进入学校交付证据包。

## 三、R11 语义需要再校正的一点

对于 SELECTABLE 课程：
- **课表可以先发布**；
- **正式学生名单要等 Selection LOCK**；
- 因此 PRE_TERM 不应简单要求所有 TeachingClass 在排课时就有最终 roster；
- 应区分：
  - `SCHEDULE_READY`
  - `ROSTER_PENDING_SELECTION`
  - `ROSTER_READY`
  - `DOWNSTREAM_READY`

实施时先写 RED 证明 ADMIN_FIXED 不退化，再调整 R11 readiness 语义，不降低最终 Attendance/Exam/Grade 对正式 roster 的强门禁。

## 四、最终验收证据

每所学校至少保存：
- exact git SHA；
- migration head；
- tenantId（交付报告中脱敏）；
- R11 pilot id / evidence hashes；
- 关键 E2E run；
- MySQL concurrency report；
- performance report；
- migration reconciliation report；
- backup/restore drill report；
- permission matrix；
- known limitations = 0 P0/P1。

---

## 来源文档：`00F_学校规模性能_并发与稳定性SLO_V1.3.md`

# 00F — 学校规模性能、并发与稳定性 SLO — V1.3

> 基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 本文中的数值是**建议验收目标**，不是对当前代码现状的声明；最终可按目标学校合同规模调整，但不得取消峰值测试。

## 一、基础数据规模

最低生产验证建议：
- 20,000 学生；
- 2,000 教职工/账号；
- 500–1,000 行政班/教学班；
- 5,000+ TeachingTask/学期；
- 100,000+ 课表 occurrence 级读取量；
- 多学期历史成绩与归档数据。

当前 main 已有面向 20K 的 SQL 分页/统计 hardening，应作为 KEEP 基线，不得退回 Python 全量 materialize。

## 二、响应目标

建议：
- 普通列表/详情：p95 ≤ 800ms，p99 ≤ 1.5s；
- 普通业务写：p95 ≤ 1.5s；
- 大型报表/导出：异步 Job，不阻塞 Web 请求；
- 学生课表首页：p95 ≤ 1s；
- 教师今日任务：p95 ≤ 1s；
- 后台 scheduler/outbox：持续有 last_success/lag/pending/dead 指标。

## 三、必须做的并发专项

### Selection
- 最后一名额 100+ 并发；
- 同学生多端重复提交；
- 1k 级突发请求；
- OPEN/CLOSE 与 enroll 并发；
- LOCK 与 drop/reselect 并发；
- LOTTERY draw 并发/重试。

### Evaluation
当前学生匿名提交会锁 EvaluationTask 行。  
必须对“同一任务几十/上百学生集中提交”和“全校集中截止”压测：
- lock wait；
- deadlock；
- p95/p99；
- duplicate proof；
- submitted_count consistency。

若热点不达标，优先把“匿名去重”落成专用不可逆 digest + DB unique constraint 或等价方案，仍只保留一套 Evaluation Record Truth。

### Grade
- 同任务教师多端重复保存；
- Excel confirm 与 roster 换版；
- submit/review/publish 双击并发。

### Exam/Schedule
- 两批次并发抢同资源；
- 大批量 XLSX dry-run/confirm；
- ScopeHead 并发发布。

## 四、失败标准

以下任何一项发生即 RED：
- 超卖；
- 重复正式记录；
- deadlock 未自动/业务可理解地处理；
- 串班/跨租户；
- 长事务导致正常读取不可用；
- 同一正式事实两端不一致；
- 异步队列积压无告警；
- 大列表因全量 Python 物化内存爆涨。

## 五、证据产物

每次 release 保存：
- 数据规模；
- DB 版本/参数；
- exact SHA；
- 测试脚本 SHA；
- QPS/concurrency；
- p50/p95/p99；
- error/deadlock/lock wait；
- CPU/memory/DB connections；
- 慢 SQL Top N；
- 结果一致性查询。

---

## 来源文档：`00G_学校运维_消息可达_备份恢复与交付证据包_V1.3.md`

# 00G — 学校运维、消息可达、备份恢复与交付证据包 — V1.3

> 基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 原则：学校正式业务不能只有“数据库事务成功”，还必须可观察、可补偿、可恢复。

## 一、消息与后台任务

当前仓库已有独立 scheduler：
- Outbox/Delivery 高频处理；
- pending/dead/oldestPendingAge/lag 指标；
- tenant effective-state fail-closed；
- 学籍未来生效任务；
- 定时消息等。

V1.3 要求建立**教务关键事件消息矩阵**：
- 课表首次发布；
- 调停课；
- 选课开选/截止/中签/落签/停开/补选；
- 考试发布/改期/缓考结果；
- 成绩发布/复查结果；
- 注册/学籍异动关键结果。

每种事件必须定义：
`business fact → outbox event → audience resolver → delivery jobs → retry/dead → user-visible receipt/ops`.

消息失败不能回滚已经成功的正式业务事实；必须可补偿、可查死信、可重试。

## 二、监控最小集

- API 5xx / latency；
- DB connection pool；
- MySQL deadlock/lock wait；
- scheduler last success / lag；
- Outbox pending/dead；
- ImportJob SCANNING/PARSING 卡住；
- ExportJob failure；
- file scan failure；
- R11 stage blockers；
- archive check blockers；
- tenant state skip count。

## 三、备份与恢复

`[OPS-BLOCKER]` 当前教务 ArchiveManifest 是业务封存证据，不等于灾备。

商业上线建议最低目标：
- DB：自动全量 + 增量/binlog/PITR；
- FileObject：对象存储/文件备份；
- 配置与密钥：安全备份；
- 备份加密、保留周期、恢复权限；
- 每个 release / 每季度至少一次恢复演练（频率按合同调整）。

建议目标：
- RPO ≤ 30 分钟；
- RTO ≤ 4 小时。

如果实际部署能力达不到，必须在学校 SLA/实施方案中明确，不能在产品文档里假装达到。

## 四、恢复验收

恢复到隔离环境后检查：
- migration head；
- tenant count；
- student/course/program/task counts；
- ScopeHead；
- Roster current versions/hashes；
- Exam snapshots；
- Grade identity/effective grade；
- GraduationDecisionFact；
- ArchiveManifest hashes；
- FileObject 可读取；
- R11 可重新读取证据。

## 五、学校交付证据包

每校交付至少包含：
1. 系统版本 / exact SHA / build digest；
2. 数据字典；
3. 权限角色矩阵；
4. 学校参数确认单；
5. 导入模板与迁移对账报告；
6. 四端验收用例；
7. 性能报告；
8. 安全/数据范围负向报告；
9. 备份恢复演练报告；
10. R11 完整学期 Pilot 报告；
11. 运维手册与故障升级路径；
12. 已知限制（正式上线要求 P0/P1=0）。

---

# Shared INT 详细来源完整附录


## Shared 来源：`00_教务中心_真实学校交付总审计与施工总控_V1.3.md`

# 教务中心现状代码、前后端与数据结构总审计 — main@414216c4 — V1.3


> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 一句话判断

**当前教务中心不是“功能少”，而是已经形成了相当多的生产级功能与强 Authority；最安全的路线是保护约 80% 已成熟能力，只修“开课形态 → TeachingTask → 排课 UI → Selection 配置/Projection → 学生四端状态”这几处主链焊点。**

## 审计方法

本轮按以下顺序逐函数、逐关键条件分支核对：

1. ORM 模型 / 唯一约束 / 时间版本事实；
2. canonical Router owner 与 legacy/bundle 去重关系；
3. public/final Service、facade、install guard；
4. 事务边界、`FOR UPDATE`、CAS、archive guard；
5. `frontend` 管理/教师 PC；
6. `student-portal` 学生 PC；
7. `miniapp` 教师/学生双端；
8. 已有 pytest / 静态前端 contract；
9. 当前 main 与开放 PR 的 collision risk。


| 标记 | 含义 | 施工约束 |
|---|---|---|
| **[KEEP]** | 已经是正式 Authority / 生产级强基座 | 禁止重写；只能补测试、补展示、补索引或局部修 bug |
| **[HARDEN]** | 当前可用，但存在边界、审计、性能或可解释性欠账 | 小步加固，保持 API/数据兼容 |
| **[REWIRE]** | 已有能力，但主链连接方式不正确或仍走旁路 | 优先“改连接”而不是“重建模块” |
| **[COMPAT]** | 兼容层 / facade / legacy 路由桥 | 等价替换与回归门禁完成前必须保留 |
| **[RETIRE-LATER]** | 可在未来退役 | 必须先证明无调用、无历史数据依赖、无路由合同依赖 |
| **[BLOCKER]** | 不修会让真实学校业务走不通或产生错误正式事实 | 上线前必须修；不得以 UI 隐藏、默认值或 mock 绕过 |


## 当前真实主链


```text
AaTerm / Calendar / TimeSlot
        ↓
AaCourse（版本化课程库）
        ↓
AaProgram + AaProgramCourse + AaProgramBinding
        ↓
学期开课执行投影（Opening Projection，不新建第二套计划真值）
        ↓
AaTeachingTaskBatch + AaTeachingTask
        ↓                       ↓
TeachingClass / Roster          Scheduling
        ↓                       ↓
正式 TeachingRoster       ScheduleBatch → ScopeHead → Published Schedule Truth
        │                       │
        ├──────────┬────────────┘
        │          │
        │          ▼
        │    学生/教师正式课表
        │
        ├─ ADMIN_CLASS：行政班固定修读
        ├─ SELECTION_LOCK：自主选课锁定
        ├─ MANUAL：经正式影响预览的人工版本
        └─ RETAKE：重修名单
        ↓
Attendance / Exam / Grade 的 RosterConsumerSnapshot
        ↓
Effective Grade
        ↓
Credits / GraduationEvaluationRun / GraduationDecisionFact
        ↓
13-domain Archive + ArchiveManifest
```

**关键校正：**
- Selection 不是所有课程必经步骤；
- TeachingRoster 是所有“谁正式修这门课”的汇流 Authority；
- Scheduling 回答“何时何地上课”，Roster 回答“谁上课”，二者不能互相替代；
- “开课计划”在当前代码里应理解为 **培养方案/绑定/课程与 TeachingTask 的执行投影**，禁止为了文档漂亮另建第二套持久化 OpeningPlan 真值。


## 十二模块成熟度

| 模块 | 当前成熟度 | 结论 |
|---|---|---|
| 01 学期/校历/作息 | 🟢/🟡 | 状态机、当前学期、校历、节次齐；保护为主 |
| 02 课程库 | 🟢/🟡 | 版本化 courseCode/courseId 已进入 Selection/Grade |
| 03 培养方案/开课执行投影 | 🟡 | “无第二套计划真值”正确；但投影偏行政班固定课 |
| 04 TeachingTask | 🟡 | Service/审核/TeachingClass sync 强；生成形态需扩展 |
| 05 排课/正式课表 | 后端🟢、PC🟠 | backend 已 Task-first，PC 仍 course+teacher 自由拼 |
| 06 Selection | 核心🟡/🟢、UI🟠/🔴 | 行锁/AcademicFact/Roster投影强；term/task/preflight/projection 有 P0 |
| 07 TeachingRoster | 🟢 | 本轮最应该保护的 Authority 之一 |
| 08 教学运行/考勤 | 🟢/🟡 | 正常教师链 Task-first + roster snapshot；admin compatibility 需显式隔离 |
| 09 考务 | 🟢 | roster snapshot、铺位、发布完整性、冲突锁都较强 |
| 10 成绩 | 🟢 | course identity + roster snapshot + effective grade + xlsx 完整 |
| 11 学分/毕业 | 🟢/🟡 | immutable evaluation/decision 已有，继续硬化 provider |
| 12 归档 | 🟢 | 13-domain semantic policy + immutable manifest 已有 |

## 绝对不要改崩的六个强基座

### 1. Router Bundle 去重兼容
`academic_affairs_bundle.py` 先挂 formal owner，再挂 legacy 并按 method/path shape 去重。  
**[COMPAT]** 在所有正式路由等价迁完以前，禁止“为了清理大文件”直接删 `academic_affairs.py`。

### 2. Services `__init__.py` 安全安装器
当前有 selection read、schedule student facade、effective grade、object scope、graduation truth、archive immutable 等安装/兼容。  
**[COMPAT]** 只能逐项退出，不能一把删除。

### 3. StudentAcademicFact
`StudentProfile` 是 current hot projection；历史资格必须按 `as_of` 读 `StudentAcademicFact`。  
**[KEEP]** Selection Final 已经使用这一事实，禁止退回 current-profile-only。

### 4. TeachingRoster
`TeachingClass + RosterVersion + Member + roster_hash` 已是正式名单版本 Authority。  
**[KEEP]** Selection LOCK、Attendance、Exam、Grade 都已接入。

### 5. RosterConsumerSnapshot
Attendance/Exam/Grade 会冻结并验证名单版本。  
**[KEEP]** 这是防“选课后名单变了但成绩/考试偷偷换学生”的关键保护。

### 6. Immutable Graduation / Archive
`GraduationEvaluationRun / GraduationDecisionFact / ArchiveManifest / PostArchiveCorrectionCase` 已能历史重放。  
**[KEEP]** 禁止把它们改回一行 mutable status。

## 当前最值得施工的 6 个真实断点

1. **[BLOCKER] Selection 批次 UI 可不带 termId 创建，但 Final 写链要求正式 termId。**
2. **[BLOCKER] SelectionCourse 仍允许 teachingTaskId 为空，无法稳定进入 Roster / Schedule / Exam / Grade。**
3. **[BLOCKER] Selection conflict slots 未统一走 `ScheduleScopeHead` 当前正式课表真值。**
4. **[BLOCKER] 管理 PC 排课还在自由选课程+教师，没直接消费已经成熟的 Task-first backend。**
5. **[REWIRE] TeachingTask generation 主要按行政班生成，自主选修/公共选修需要在现有 Program→Task 链里补“名单形成方式”，不能新造 OpeningPlan 表。**
6. **[REWIRE] 学生 PC/小程序 Selection 只把 SELECTED 当有效，LOCKED/PENDING_LOTTERY/LOTTERY_LOST/COURSE_CANCELLED 表达不完整。**

## 功能保护结论

当前系统已经具备并应保护：注册、学籍异动、课程库、培养方案、教学任务、教师确认、教学班、名单版本、排课、班级/教师/学生/教室课表、选课轮次/抽签/补退选、考勤、调停课、考务、缓考、补考重修免修、成绩录入/Excel/审核/发布/复查/更正、评教、教材、等级考试、专业分流、学分、预警、毕业审核、十三域归档等大量能力。

本轮不能用“大重构”把这些能力重新做一遍；应按 V1.3 的 `[KEEP]/[REWIRE]` 台账小步焊接。

## 推荐施工顺序（只修主链，不重建功能）

```text
G0  exact-head + collision audit + existing contract freeze
→ G1 Opening Projection/Task 的固定课 vs SELECTABLE 表达
→ G2 Schedule PC Task-first（后端不改）
→ G3 Selection batch/task/preflight fail-closed
→ G4 Schedule Truth + Selection Student Projection
→ G5 学生 PC + 学生小程序 Selection 状态统一
→ G6 TeachingRoster / Attendance / Exam / Grade 回归证明“不被改坏”
→ G7 四端 semester E2E：固定课 + 自主选课各走一条
→ G8 真实 MySQL concurrency targeted
→ G9 13域归档 + immutable replay
→ exact-head canonical gate
```

## 最终业务 Gold

同一学生同一学期至少真实跑通两门课：

```text
A 固定行政班课：
Program → TeachingTask(ADMIN) → ADMIN_CLASS Roster
→ Published Schedule → Student Schedule
→ Attendance → Exam → Grade → Credit

B 自主选课：
Program/Offering → TeachingTask(SELECTION)
→ Published Schedule → Selection → LOCK
→ SELECTION_LOCK Roster → Student Schedule
→ Attendance → Exam → Grade → Credit
```

必须证明：
- 固定课从未出现在“可选课程”；
- 选修课 LOCK 前不能被考勤/考务/成绩当正式名单；
- LOCK 后两种来源在下游消费方式一致；
- 学生 PC/小程序状态一致；
- 教师 PC/小程序看到同一 Task/Roster；
- 成绩只进入一次有效学分；
- 归档时 Selection 未启用可 `NOT_APPLICABLE/PASS`，启用了但未锁定则 BLOCKED。

---

# V1.3 真实学校交付增强层

> 本节是 V1.3 在 V1.2“保护成熟 Authority、修主链焊点”之上新增的**学校交付层**。  
> 任何开发智能体不得把这里的“上线准入”误解为重建业务模型；优先复用现有 Authority、File Exchange、R11 Semester Pilot、RBAC/DataScope、Outbox/Audit。

## 学校上线必须同时满足的 8 类证据

1. **业务正确**：状态机、权限、名单、课表、考试、成绩的 Authority 无旁路。
2. **可实施**：新学校可通过导入/配置而不是人工逐条录入完成基础数据建设。
3. **可操作**：教务处、学院教务、任课教师、学生在各自端能完成真实任务。
4. **可解释**：任何 BLOCKED 都有原因、责任角色、下一步、下钻入口。
5. **可对账**：导入、名单、排课、考试、成绩、归档均有 before/after、数量、hash/版本或可复核摘要。
6. **可承载**：真实 MySQL 下通过学校规模峰值测试，不能只跑单用户功能测试。
7. **可运维**：异步任务、消息、导入任务、归档、后台调度有 lag/dead/pending 指标和故障处置。
8. **可恢复**：数据库、文件对象、配置、迁移具备恢复演练证据；没有恢复演练不得签“可给学校正式上线”。

## V1.3 新增标记

| 标记 | 含义 |
|---|---|
| `[GO-LIVE-BLOCKER]` | 业务功能可能可跑，但不满足真实学校上线签字 |
| `[IMPLEMENTATION-BLOCKER]` | 新学校初始化/数据迁移无法低风险完成 |
| `[SCALE-BLOCKER]` | 小数据可用，但学校高峰/大数据量未经证明或有热点 |
| `[OPS-BLOCKER]` | 故障、异步任务、备份恢复、告警没有可操作闭环 |
| `[VERIFY-FIRST]` | 代码检索未能证明能力存在；先核 exact-head，确认缺失后才施工 |

# 二次重审裁决：V1.2 为什么还不能直接签“可卖给学校”

V1.2 已经足够作为**安全重构/主链焊接总册**，但还不是完整的**学校交付规格**。原因不是核心业务 Authority 弱，而是缺以下横向门禁：

1. `[IMPLEMENTATION-BLOCKER]` 新校数据初始化：课程库、培养方案、组织/师生、学期参数如何批量进入系统并对账。
2. `[GO-LIVE-BLOCKER]` R11 真实学期试点没有被提升为最终签字 Gate。
3. `[SCALE-BLOCKER]` Selection、集中评教、成绩导入、全校课表/考试周等峰值没有统一 SLO/压测标准。
4. `[OPS-BLOCKER]` Outbox/Delivery/Scheduler 虽有基础能力，但教务关键事件的“事实成功 ≠ 通知送达”缺统一消息矩阵和业务巡检。
5. `[OPS-BLOCKER]` 业务归档已经成熟，但数据库/文件恢复演练不是 ArchiveManifest 能替代的。
6. `[GO-LIVE-BLOCKER]` 角色/数据范围需要按“教务处 / 学院教务 / 任课教师 / 学生 / 学校管理员”做端到端权限矩阵；权限 Catalog 由 Control Plane Authority 持有，教务不得复制一套。
7. `[GO-LIVE-BLOCKER]` 历史欠账必须重新与当前代码对账，不能把旧问题当现状，也不能因为代码新就默认销账。
8. `[IMPLEMENTATION-BLOCKER]` 学校切换时需要旧系统数据迁移、数量/主键/业务关系/历史成绩对账和可回滚切换计划。

# V1.3 最终施工顺序

```text
G0 exact-head + open PR collision + route/service/model owner freeze
→ G0.5 历史欠账 reconciliation
→ G1 新校实施基线：租户/组织/身份/学期/课程/培养方案导入与对账
→ G2 Opening Projection + Task formation mode
→ G3 Schedule PC Task-first + File Exchange 统一导入
→ G4 Selection P0 + Student Projection + MySQL concurrency
→ G5 TeachingRoster 统一对账
→ G6 教师日常链：课表/考勤/调停课
→ G7 考务/成绩/毕业成熟链回归 + 异常场景
→ G8 通知/Outbox/Scheduler 业务送达矩阵
→ G9 20K 数据 + 峰值压测 + 锁竞争
→ G10 13 域归档 + 备份恢复演练
→ G11 四端完整学期 Gold
→ G12 R11 真实学校六阶段 Pilot = COMPLETED
→ G13 学校上线证据包签字
```

# V1.3 的最终目标

不再以“代码很多 / 页面能打开 / CI 全绿”为交付结论，而是必须同时回答：

- 教务处今天能不能完成工作？
- 学院教务能不能只看到本学院、正确审批？
- 任课教师能不能从课表走到考勤和成绩，不需要找管理员补数据？
- 学生能不能在 PC/小程序完成注册、选课、查课表、考试、成绩、毕业进度？
- 旧学校数据能不能安全迁进来？
- 选课/评教高峰会不会锁死？
- 消息失败能不能发现和补发？
- 数据错了能不能追溯？
- 服务崩了能不能恢复？
- 一学期结束能不能真实归档并回放？

## Shared 来源：`00A_四端业务旅程_API_Authority_学校可用矩阵_V1.3.md`

# 四端页面 × API × 数据结构真实映射总表 — V1.3


> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。



## 四端定义

本总册中的“四端”固定指：

1. **管理 / 教师 PC：`frontend/`**  
   同一 PC 客户端，由 `RBAC + dataScope + navPlan` 决定教务处、学院教务、任课教师看到的工作区。
2. **学生 PC：`student-portal/`**
3. **教师小程序：`miniapp/` teacher side**
4. **学生小程序：`miniapp/` student side**

四端必须共享同一后端状态机、同一 TeachingTask、同一 Schedule Truth、同一 TeachingRoster、同一正式成绩事实。  
**允许 UI 密度不同，不允许业务真值不同。**


## 主链映射

| 业务节点 | 数据 Authority | 后端 owner / service | 管理/教师 PC | 学生 PC | 教师小程序 | 学生小程序 | 标记 |
|---|---|---|---|---|---|---|---|
| 学期/校历/作息 | AaTerm/CalendarEvent/TimeSlot/TimeBand | `term_calendar_router.py` | AcademicYear/Calendar/Term workspace | Schedule/Calendar | MySchedule | Academic home/Schedule | KEEP |
| 课程库 | AaCourse version | `course_program_task_router.py` | `AaCourseConsoleView` | 通过课表/成绩读 | Task/Grade读 | 通过课表/成绩读 | KEEP |
| 培养方案 | AaProgram/ProgramCourse/Binding | program service/governance | Program console/editor | Credits/Graduation只读 | Task显示来源即可 | Credits/Graduation | KEEP |
| 开课执行投影 | Derived projection | `academic_affairs_program_governance_service.py` | `AaOpeningPlanDiffView` | 不直接展示正式课 | 不直接管理 | 不直接展示 | HARDEN |
| TeachingTask | AaTeachingTaskBatch/Task | `academic_affairs_task_service.py` | Task batch/workbench/teacher confirm | 不直接写 | academic-task | 不直接写 | KEEP/REWIRE generation |
| TeachingClass/Roster | TeachingClass + RosterVersion/Member | teaching_class_service | class list/detail | 间接消费 | attendance/grade | schedule/exam/grade间接消费 | KEEP |
| 排课 | ScheduleBatch/Item | schedule_final_service | **ScheduleMaintain 需 task-first** | 不看 draft | 不改 | 不看 draft | PC REWIRE |
| 正式课表 | ScheduleScopeHead | schedule final/read | class/teacher/student/room views | `StudentScheduleView` | `my-schedule` | `schedule.vue` | KEEP/HARDEN |
| Selection | SelectionBatch/Course/Round/Record | selection final/public/read | SelectionConsole | StudentSelection | 只读 roster | selection.vue | REWIRE |
| 考勤 | AttendanceSession + roster snapshot | attendance_public_service | stats | read-only attendance | attendance.vue | read-only | KEEP |
| 考务 | Exam* + EXAM_COURSE snapshot | exam_facade/core_router | ExamConsole | StudentExam | related approval | exam pages | KEEP |
| 成绩 | GradeTask/Record + GRADE_TASK snapshot | grade_service/core_router | GradeEntry/Review | StudentGrades | grade-entry.vue | transcript | KEEP |
| 学分/毕业 | effective grade + eval/decision facts | graduation services | graduation console | GraduationAudit/Credits | task-only | graduation/credits | KEEP/HARDEN |
| 归档 | ArchiveBatch/Item + Manifest | archive service | ArchiveConsole | 无写入口 | 无普通写入口 | 无普通写入口 | KEEP |

## 学生 PC 已有独立路由（禁止收回“大综合页”）

`student-portal/src/router/academicRoutes.js` 当前已有：
- `/academic/schedule`
- `/academic/grades`
- `/academic/registration`
- `/academic/selection`
- `/academic/evaluation`
- `/academic/recheck`
- `/academic/exam`
- `/academic/makeup`
- `/academic/attendance`
- `/academic/calendar`
- `/academic/clearance`
- `/academic/credits`
- `/academic/warning`
- `/academic/textbook`
- `/academic/level-exam`
- `/academic/major-split`
- `/academic/graduation`

`status/recognition/all` 仍保留兼容工作区。  
**[KEEP]** 现有 `test_aa_frontend_p0_contracts.py` 已防止多个专门页面退回兼容综合页。

## 用户真正应该看到的课程来源

| 技术来源 | 学生/教师文案 | 是否可在选课页操作 |
|---|---|---|
| `ADMIN_CLASS` / classType ADMIN | 学校安排 | 否 |
| `SELECTION_LOCK` / classType SELECTION | 自主选课 | 只有 Selection 生命周期允许时 |
| `MERGED` | 合班教学 | 否，除非其名单来源本身由 Selection 管理 |
| `RETAKE` | 重修 | 走重修正式流程 |
| `MANUAL` | 教务调整 | 只读解释，必须有原因/审计 |

## 四端统一状态合同（Selection）

不得再各端手写一套：

```text
PENDING_LOTTERY → 待抽签
SELECTED        → 已选，尚未形成最终名单
LOCKED          → 已锁定，已进入正式教学名单
DROPPED         → 已退
LOTTERY_LOST    → 未中签
COURSE_CANCELLED→ 课程停开，待补选
```

按钮由后端 `allowedActions` 决定，而不是 PC/小程序根据 capacity/status 猜。

---

# V1.3 真实学校交付增强层

> 本节是 V1.3 在 V1.2“保护成熟 Authority、修主链焊点”之上新增的**学校交付层**。  
> 任何开发智能体不得把这里的“上线准入”误解为重建业务模型；优先复用现有 Authority、File Exchange、R11 Semester Pilot、RBAC/DataScope、Outbox/Audit。

## 学校上线必须同时满足的 8 类证据

1. **业务正确**：状态机、权限、名单、课表、考试、成绩的 Authority 无旁路。
2. **可实施**：新学校可通过导入/配置而不是人工逐条录入完成基础数据建设。
3. **可操作**：教务处、学院教务、任课教师、学生在各自端能完成真实任务。
4. **可解释**：任何 BLOCKED 都有原因、责任角色、下一步、下钻入口。
5. **可对账**：导入、名单、排课、考试、成绩、归档均有 before/after、数量、hash/版本或可复核摘要。
6. **可承载**：真实 MySQL 下通过学校规模峰值测试，不能只跑单用户功能测试。
7. **可运维**：异步任务、消息、导入任务、归档、后台调度有 lag/dead/pending 指标和故障处置。
8. **可恢复**：数据库、文件对象、配置、迁移具备恢复演练证据；没有恢复演练不得签“可给学校正式上线”。

## V1.3 新增标记

| 标记 | 含义 |
|---|---|
| `[GO-LIVE-BLOCKER]` | 业务功能可能可跑，但不满足真实学校上线签字 |
| `[IMPLEMENTATION-BLOCKER]` | 新学校初始化/数据迁移无法低风险完成 |
| `[SCALE-BLOCKER]` | 小数据可用，但学校高峰/大数据量未经证明或有热点 |
| `[OPS-BLOCKER]` | 故障、异步任务、备份恢复、告警没有可操作闭环 |
| `[VERIFY-FIRST]` | 代码检索未能证明能力存在；先核 exact-head，确认缺失后才施工 |

# V1.3 角色业务旅程矩阵

| 角色 | 每日/阶段核心任务 | 正式事实 |
|---|---|---|
| 教务处管理员 | 学期参数、方案治理、教学任务、排课发布、选课批次、考务、成绩终审、归档 | Term/Program/Task/Schedule/Selection/Exam/Grade/Archive |
| 学院教务 | 任务核对、教师确认跟踪、学院范围选课/考务/成绩审核 | DataScope-scoped Task/Roster/Exam/Grade |
| 任课教师 | 确认教学任务、看课表、点名、调课申请、录成绩 | TeachingTask + Published Schedule + Roster Snapshot |
| 学生 | 注册、看课表、选课、看考试、查成绩、申请补考/复查、看毕业进度 | StudentAcademicFact + Roster Membership + Official Projections |
| 学校管理员 | 账号/角色/范围、实施开局、系统运行/审计 | Control Plane Authority，不由教务复制 |

## 四端可用性新原则

每个页面必须首屏回答：
1. 我现在是什么状态；
2. 我能做什么；
3. 为什么不能做；
4. 下一步去哪里；
5. 当前数据来自哪个正式版本/批次（对管理/教师页尤其重要）。

禁止只给“表格 + 操作按钮”而不解释业务阶段。

## Shared 来源：`00B_文件级保护与上线风险总台账_V1.3.md`

# 文件级 KEEP / HARDEN / REWIRE / COMPAT / BLOCKER 总台账 — V1.3


> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。



| 标记 | 含义 | 施工约束 |
|---|---|---|
| **[KEEP]** | 已经是正式 Authority / 生产级强基座 | 禁止重写；只能补测试、补展示、补索引或局部修 bug |
| **[HARDEN]** | 当前可用，但存在边界、审计、性能或可解释性欠账 | 小步加固，保持 API/数据兼容 |
| **[REWIRE]** | 已有能力，但主链连接方式不正确或仍走旁路 | 优先“改连接”而不是“重建模块” |
| **[COMPAT]** | 兼容层 / facade / legacy 路由桥 | 等价替换与回归门禁完成前必须保留 |
| **[RETIRE-LATER]** | 可在未来退役 | 必须先证明无调用、无历史数据依赖、无路由合同依赖 |
| **[BLOCKER]** | 不修会让真实学校业务走不通或产生错误正式事实 | 上线前必须修；不得以 UI 隐藏、默认值或 mock 绕过 |


| 文件 | 标记 | 原因/施工限制 |
|---|---|---|
| backend/app/modules/academic_affairs/routers/academic_affairs_bundle.py | COMPAT/KEEP | formal owner 先注册，legacy 后挂并去重；禁止直接删除 |
| backend/app/modules/academic_affairs/routers/academic_affairs.py | COMPAT/RETIRE-LATER | 254KB legacy 大 Router；仍提供 DTO/兼容 svc 注入点和未迁端点 |
| backend/app/modules/academic_affairs/services/__init__.py | COMPAT/KEEP | 多项安全 installer/facade；逐项替换 |
| backend/app/models/academic_affairs_registry.py | KEEP | 增强模型集中注册，含 fresh schema 元数据修正 |
| backend/app/models/academic_affairs_student_fact.py | KEEP | 有效期学籍事实 |
| backend/app/models/academic_affairs_teaching_class.py | KEEP | TeachingClass/Teacher/RosterVersion/Member |
| backend/app/models/academic_affairs_roster_consumer.py | KEEP | 下游名单快照 |
| backend/app/models/academic_affairs_stage_c3.py | KEEP | 毕业/归档 immutable facts |
| backend/app/modules/academic_affairs/services/academic_affairs_program_governance_service.py | KEEP | Opening Projection，不建第二套真值 |
| backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py | REWIRE | 固定行政班生成强；selectable offering表达不足 |
| backend/app/modules/academic_affairs/services/academic_affairs_task_service.py | KEEP | 教学任务主公开 service |
| backend/app/modules/academic_affairs/services/academic_affairs_teaching_class_service.py | KEEP | 正式教学班/名单版本 |
| backend/app/modules/academic_affairs/services/academic_affairs_schedule_final_service.py | KEEP | Task-first 排课 |
| backend/app/modules/academic_affairs/services/academic_affairs_schedule_gate_service.py | KEEP | 课表发布 gate |
| backend/app/modules/academic_affairs/services/academic_affairs_schedule_facade.py | COMPAT/REWIRE-LATER | 学生课表：admin class + locked selection |
| frontend/src/modules/academicAffairs/views/AaScheduleMaintainView.vue | BLOCKER/REWIRE | 旧 UI 未发送 taskId；文本导入 teacherName=teacherKey |
| backend/app/modules/academic_affairs/services/academic_affairs_selection_service.py | HARDEN | scope/rule fail-closed + schedule truth |
| backend/app/modules/academic_affairs/services/academic_affairs_selection_final_service.py | KEEP/HARDEN | 行锁/AcademicFact/LOCK→Roster强；publish preflight补强 |
| backend/app/modules/academic_affairs/services/academic_affairs_selection_read_service.py | HARDEN | SQL分页/学院scope强；学生 projection需增强 |
| backend/app/modules/academic_affairs/services/academic_affairs_selection_round_service.py | KEEP/HARDEN | SHA256确定抽签+锁序；可补manifest |
| frontend/src/modules/academicAffairs/views/AaSelectionConsoleView.vue | BLOCKER/REWIRE | term/window/scope缺失，Task选填 |
| student-portal/src/views/academic/StudentSelectionView.vue | REWIRE | SELECTED-only/窗口字段/本地allowedActions |
| miniapp/src/pages/student/academic-affairs/selection.vue | REWIRE | SELECTED-only状态 |
| backend/app/modules/academic_affairs/services/academic_affairs_roster_consumer_service.py | KEEP | Attendance/Exam/Grade名单冻结协议 |
| backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py | KEEP/HARDEN | 正常Task-first；admin手工class path需隔离 |
| backend/app/modules/academic_affairs/services/academic_affairs_exam_facade.py | KEEP | Exam roster freeze/seat/publish complete |
| backend/app/modules/academic_affairs/services/academic_affairs_grade_service.py | KEEP | course identity/roster/xlsx/workflow/effective grade |
| backend/app/modules/academic_affairs/services/academic_affairs_archive_service.py | KEEP | 13域语义归档 |
| backend/app/modules/academic_affairs/services/academic_affairs_archive_domain_policy.py | KEEP | Selection未启用不阻断等语义规则 |
| student-portal/src/router/academicRoutes.js | KEEP | 学生独立教务页面路由 |
| backend/tests/test_aa_frontend_p0_contracts.py | KEEP | 学生/PC可信边界静态合同 |

## 使用方式

施工智能体每次准备修改文件前必须先查本表：

- `KEEP`：默认不改结构；
- `COMPAT`：默认不删；
- `REWIRE`：优先修改调用连接和 DTO；
- `BLOCKER`：先补 RED test，再最小修复；
- 若某文件同时属于开放 PR（当前尤其 PR #96 的 `services/__init__.py`、教师小程序成绩页等），必须重新做 collision audit。

---

# V1.3 真实学校交付增强层

> 本节是 V1.3 在 V1.2“保护成熟 Authority、修主链焊点”之上新增的**学校交付层**。  
> 任何开发智能体不得把这里的“上线准入”误解为重建业务模型；优先复用现有 Authority、File Exchange、R11 Semester Pilot、RBAC/DataScope、Outbox/Audit。

## 学校上线必须同时满足的 8 类证据

1. **业务正确**：状态机、权限、名单、课表、考试、成绩的 Authority 无旁路。
2. **可实施**：新学校可通过导入/配置而不是人工逐条录入完成基础数据建设。
3. **可操作**：教务处、学院教务、任课教师、学生在各自端能完成真实任务。
4. **可解释**：任何 BLOCKED 都有原因、责任角色、下一步、下钻入口。
5. **可对账**：导入、名单、排课、考试、成绩、归档均有 before/after、数量、hash/版本或可复核摘要。
6. **可承载**：真实 MySQL 下通过学校规模峰值测试，不能只跑单用户功能测试。
7. **可运维**：异步任务、消息、导入任务、归档、后台调度有 lag/dead/pending 指标和故障处置。
8. **可恢复**：数据库、文件对象、配置、迁移具备恢复演练证据；没有恢复演练不得签“可给学校正式上线”。

## V1.3 新增标记

| 标记 | 含义 |
|---|---|
| `[GO-LIVE-BLOCKER]` | 业务功能可能可跑，但不满足真实学校上线签字 |
| `[IMPLEMENTATION-BLOCKER]` | 新学校初始化/数据迁移无法低风险完成 |
| `[SCALE-BLOCKER]` | 小数据可用，但学校高峰/大数据量未经证明或有热点 |
| `[OPS-BLOCKER]` | 故障、异步任务、备份恢复、告警没有可操作闭环 |
| `[VERIFY-FIRST]` | 代码检索未能证明能力存在；先核 exact-head，确认缺失后才施工 |

# V1.3 新增横向风险台账

| 能力/文件族 | 新标记 | 裁决 |
|---|---|---|
| `academic_affairs_semester_pilot_service.py` + router | KEEP / GO-LIVE-GATE | 升级为最终真实学校签字 Gate |
| `academic_file_exchange_router.py` + `academic_file_exchange_service.py` | KEEP / REUSE | 学籍/成绩/排课导入统一入口；课程/方案若需新增导入也扩展此链 |
| `academic_affairs_schedule_final_service.py` | KEEP / COMPAT-HARDEN | taskId-first；名称唯一匹配只作兼容 |
| `academic_affairs_evaluation_public_service.py` | KEEP correctness / SCALE-BLOCKER | 匿名/名单/幂等强；同 task 行锁可能成为集中评教热点 |
| `academic_affairs_production_audit_guard.py` | KEEP | 20K SQL 分页、scope fail-closed、PII redaction 等不得回退 |
| `backend/scripts/run_scheduled_jobs.py` | KEEP / OPS-HARDEN | 已有 outbox/delivery/scheduler metrics；需对教务关键事件形成业务送达矩阵 |
| `school_onboarding_service.py` + identity import | KEEP / IMPLEMENTATION-DEPENDENCY | 新学校组织/账号开局基座；教务实施总册必须引用 |
| Control Plane Permission Catalog（PR #133） | DEPENDENCY-BLOCKER | 教务只声明所需能力，不复制 permission registry |
| DB/File backup + restore | OPS-BLOCKER | 当前业务归档不能替代基础设施恢复证据 |

## Shared 来源：`00C_施工安全边界_上线防崩与回归门禁_V1.3.md`

# 教务施工安全边界：禁止误删与回归门禁 — V1.3


> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 目的

这份文件专门防止“为了重构主链，把已经能用的教务系统改崩”。

## 禁止动作

1. 禁止直接删除 `academic_affairs.py` legacy 大 Router。
2. 禁止直接清空 `services/__init__.py` installers。
3. 禁止新建第二套 OpeningPlan / TeachingRoster / OfficialSchedule / EffectiveGrade。
4. 禁止把 `AaTeachingClassRosterVersion` 换回 current student list 动态查询。
5. 禁止为了方便 Selection 把 TeachingTask 变回可选。
6. 禁止为方便排课 UI 放宽 backend Task-first gate。
7. 禁止把学生专门页面重新塞回 `AcademicLegacySafeView`。
8. 禁止让 PC/miniapp 自己重新计算毕业资格、选课资格、考试资格。
9. 禁止归档后普通 unfreeze 改历史。
10. 禁止用 SQLite 证明 FCFS/LOTTERY/roster version/Exam publish 并发。

## 每刀修改前

```text
exact main SHA
→ 当前施工 branch SHA
→ open PR collision
→ route owner
→ model owner
→ public/final service owner
→ frontend caller
→ existing tests
→ RED contract
```

## 每刀修改后

```text
targeted unit/service
→ API contract
→ 四端受影响页面
→ MySQL concurrency（若涉及锁/唯一约束）
→ no-regression for KEEP areas
→ exact-head evidence
```

## 特别保护测试

至少保留并扩展：
- `backend/tests/test_aa_frontend_p0_contracts.py`
- `backend/tests/test_aa_teaching_roster_unification.py`
- `backend/tests/test_aa_roster_consumer_lock_protocol.py`
- `backend/tests/test_aa_roster_consumers_r9.py`
- `backend/tests/test_aa_grade_course_identity_v2.py`
- Selection round concurrency tests
- Schedule gate/ScopeHead tests
- Semester pilot/rehearsal（注意 PR #96 尚未合入 current main）

## 破坏性变化必须满足

只有同时满足以下条件才允许退役 COMPAT：
- repo search 零调用；
- Router shape 已由 formal owner 等价覆盖；
- 历史数据迁移/读取经过 fresh + upgrade + downgrade/rollback 评估；
- 四端 E2E 不依赖；
- exact-head canonical 全绿；
- 有可回退 commit。

---

# V1.3 真实学校交付增强层

> 本节是 V1.3 在 V1.2“保护成熟 Authority、修主链焊点”之上新增的**学校交付层**。  
> 任何开发智能体不得把这里的“上线准入”误解为重建业务模型；优先复用现有 Authority、File Exchange、R11 Semester Pilot、RBAC/DataScope、Outbox/Audit。

## 学校上线必须同时满足的 8 类证据

1. **业务正确**：状态机、权限、名单、课表、考试、成绩的 Authority 无旁路。
2. **可实施**：新学校可通过导入/配置而不是人工逐条录入完成基础数据建设。
3. **可操作**：教务处、学院教务、任课教师、学生在各自端能完成真实任务。
4. **可解释**：任何 BLOCKED 都有原因、责任角色、下一步、下钻入口。
5. **可对账**：导入、名单、排课、考试、成绩、归档均有 before/after、数量、hash/版本或可复核摘要。
6. **可承载**：真实 MySQL 下通过学校规模峰值测试，不能只跑单用户功能测试。
7. **可运维**：异步任务、消息、导入任务、归档、后台调度有 lag/dead/pending 指标和故障处置。
8. **可恢复**：数据库、文件对象、配置、迁移具备恢复演练证据；没有恢复演练不得签“可给学校正式上线”。

## V1.3 新增标记

| 标记 | 含义 |
|---|---|
| `[GO-LIVE-BLOCKER]` | 业务功能可能可跑，但不满足真实学校上线签字 |
| `[IMPLEMENTATION-BLOCKER]` | 新学校初始化/数据迁移无法低风险完成 |
| `[SCALE-BLOCKER]` | 小数据可用，但学校高峰/大数据量未经证明或有热点 |
| `[OPS-BLOCKER]` | 故障、异步任务、备份恢复、告警没有可操作闭环 |
| `[VERIFY-FIRST]` | 代码检索未能证明能力存在；先核 exact-head，确认缺失后才施工 |

# V1.3 上线前新增禁止项

11. 禁止把 R11 的“测试/演练脚本成功”当成真实学校 Pilot COMPLETED。
12. 禁止用 demo/seed 数据签学校上线证据。
13. 禁止另造课程/方案/课表 Excel 导入框架；优先扩展 Academic File Exchange。
14. 禁止以业务 ArchiveManifest 代替数据库/文件恢复演练。
15. 禁止在教务里复制 Control Plane 的角色/权限 Catalog。
16. 禁止用单用户性能证明 Selection/评教/成绩导入高峰。
17. 禁止把消息写入成功当作师生“已送达”；必须查 Delivery/Outbox 状态。
18. 禁止没有 rollback/cutover plan 就把旧学校历史数据一次性切换。
19. 禁止把历史欠账直接删除；每条必须有销账证据。
20. 禁止对 `[KEEP]` 模块做“顺手重构”。

# 生产上线变更纪律

- 业务迁移必须可 forward + rollback/compensate；
- 数据迁移前做 count/hash/key relationship 基线；
- 上线窗口冻结 schema/permission/shared router 的并行写；
- 所有上线证据绑定 exact HEAD + migration head + image/build digest；
- 上线后第一天必须跑业务 reconciliation，不等用户报错。

# Ⅺ. V1.5 外部研究来源（2026-08-16复核）

> 以下来源只支持“成熟系统存在何种制度能力 / 真实高校如何运作”的判断；不代表本系统直接复制其产品结构。

## Oracle PeopleSoft Campus Solutions / Student Records（官方）
- Student Records Overview  
  `https://docs.oracle.com/en/applications/peoplesoft/campus-solutions/9.2.038/student-records/student-records-overview.html`
- Campus Self Service Business Processes（Student Planner / Shopping Cart / Add / Drop / Swap）  
  `https://docs.oracle.com/en/applications/peoplesoft/campus-solutions/9.2.038/campus-self-service/campus-self-service-business-processes.html`
- Setting Up Self-Service Features for Student Records（Waitlist / Swap）  
  `https://docs.oracle.com/en/applications/peoplesoft/campus-solutions/9.2.038/campus-self-service/setting-self-service-features-student-records.html`
- Managing Wait Lists  
  `https://docs.oracle.com/en/applications/peoplesoft/campus-solutions/9.2.038/student-records/managing-wait-lists.html`
- Enrollment / Validation Appointments  
  `https://docs.oracle.com/en/applications/peoplesoft/campus-solutions/9.2.038/student-records/setting-enrollment-validation-appointments.html`
- Swapping Classes  
  `https://docs.oracle.com/en/applications/peoplesoft/campus-solutions/9.2.038/campus-self-service/swapping-classes.html`
- Campus Solutions Overview（workload / transfer credit / attendance / grading / transcripts / graduation / LMS / Academic Advisement）  
  `https://docs.oracle.com/en/applications/peoplesoft/campus-solutions/9.2.038/campus-solutions-application-fundamentals/campus-solutions-overview.html`

## Workday Student（官方）
- Concept: Student Registration（date controls / registration appointments / saved schedules / troubleshooting）  
  `https://doc.workday.com/admin-guide/en-us/student/student-records/student-registration/jai1465000066192.html`
- Concept: Waitlists（auto/manual promotion / notification / expiry / reserve capacity）  
  `https://doc.workday.com/admin-guide/en-us/student/student-records/student-registration/rgm1622826555664.html`
- Steps: Set Up Student Registration  
  `https://doc.workday.com/admin-guide/en-us/student/student-records/student-registration/student-registration-setup/jai1458328672371.html`
- Reference: Date Controls（add / drop / withdraw / last waitlist date）  
  `https://doc.workday.com/admin-guide/en-us/student/academic-foundation/date-controls/fpb1580786053033.html`
- Student Records & Advising Overview / Academic Advising  
  `https://doc.workday.com/workday-education/en-us/course-manuals/student-for-administrators/student-records-advising-overview.html`
- Student Academic Records System  
  `https://www.workday.com/en-us/products/student/student-records.html`

## Ellucian（官方）
- Student Success / Degree Auditing / Smart Planning & Registration  
  `https://www.ellucian.com/products/student/student-success`
- 2026 Student Success Planning and Credential Pathways announcement  
  `https://www.ellucian.com/newsroom/ellucian-wins-2026-edtech-award-best-student-success-planning-and-credential-pathways`

## 国内高校真实教务运行 / 新系统切换
- 广州南方学院：2026-2027学年第一学期选课，正式选课 + 补选申请、分批选课  
  `https://jw.nfu.edu.cn/info/1191/29742.htm`
- 广州华立学院：2026新版正方教务正式启用，新业务切新系统，旧系统停止更新仅保留查询  
  `https://www.hualixy.edu.cn/jwc/tzgg/jwgl/content_80670`
- 广州华立学院：切换前数据校对，新系统体验、旧强智仍承担正式业务  
  `https://www.hualixy.edu.cn/xb/ybtz__xwzx/tzgg/content_78665`
- 东北大学：2026新本科教务系统，旧系统停止数据输入、保留查询  
  `https://aao.neu.edu.cn/2026/0227/c9405a450413/pagem.htm`
- 浙江水利水电学院：正方教务系统功能模块分阶段上线交付（工作量/实践等阶段交付）  
  `https://jwc.zuwe.edu.cn/2e/a2/c3201a143010/page.htm`

# Ⅻ. GitHub 内部深审资产清单

V1.5 施工 Agent 不能只读本总册；专题动刀前应按符号重新定位并核对这些现有资产：

- `docs/03-业务模块设计/教务中心/13B-教务中心全业务流程设计总册.md`
- `docs/03-业务模块设计/教务中心/13B-教务中心页面级交互与按钮动作矩阵.md`
- `docs/03-业务模块设计/教务中心/13B-教务中心状态机与权限矩阵.md`
- `docs/03-业务模块设计/教务中心/13B-教务中心表单字段与校验规则.md`
- `docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md`
- `docs/03-业务模块设计/教务中心/13B-教务中心API契约草案.md`
- `docs/03-业务模块设计/教务中心/13B-教务中心-商业化对标审计与补丁建议（第一轮）.md`
- `docs/03-业务模块设计/教务中心/教务中心产品深度补强10份整改文档-V2-代码对齐与页面施工版/`
- `docs/03-业务模块设计/教务中心/施工包/`
- `docs/03-业务模块设计/教务中心/施工包/**/三级施工卡/`
- `backend/app/modules/academic_affairs/`
- `backend/app/models/academic_affairs*.py`
- `backend/tests/test_aa_*.py`
- `frontend/src/modules/academicAffairs/`
- `student-portal/src/views/academic/`
- `miniapp/src/pages/student/academic-affairs/`
- `miniapp/src/pages/teacher/academic-affairs/`

**施工优先级永远是：current exact-head 代码事实 > V1.5裁决 > 历史设计 > 外部竞品启发。**
