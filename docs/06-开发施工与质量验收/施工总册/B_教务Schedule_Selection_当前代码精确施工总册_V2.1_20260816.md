<!-- normalized repository copy; authoritative source is the user-provided V2.1 attachment -->
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



# 0A-B. B线一键开工总控提示词（直接复制到B施工窗口）

```text
@GitHub

你现在接管教务中心 V2.1 四线并行施工：

B — Schedule/Selection（排课与选课线）

仓库：
penghaibin9/saas

固定施工分支：
agent/academic-b-schedule-selection

建立 Draft PR（草稿拉取请求），禁止合并 main（主分支），禁止 force push（强制推送）。

唯一当前施工总册：
《B_教务Schedule_Selection_当前代码精确施工总册_V2.1_20260816.md》

当前代码事实 > V2.1 当前裁决 > 文档内 V1.5 附录 > 历史文档。

第一笔必须在PR分支建立：

docs/06-开发施工与质量验收/施工记录/
2026-08-16-教务B线-Schedule-Selection-V2.1-施工顺序与文档读取地图.md

地图必须记录：
main/B exact HEAD、PR #96/#132/#133及新增教务PR碰撞、B独占文件、INT共享禁区、B-W0～B-W6、每Wave读取文档/代码/测试、A-C1～A-C4输入依赖、B-C1～B-C3输出、RED、MySQL、Frontend Impact Matrix、截图视觉证据、真实点击E2E、exact-head证据和下一入口。

首先完整读取本总册：
B-0
B-P0-01～B-P0-08
B-P1-09
B-W0～B-W6
B-C1～B-C3
0B/0C-B前后端硬门
自行纠错
最终签字。
进入具体批次时再读V1.5附录。

B-W0：
读取V2.1强底座、V1.5 Official Schedule/TeachingRoster（正式课表/正式名单），以及仓库“教学任务教学班排课课表调停课考勤”代码对齐文档。
源码：
schedule_truth_service
schedule_final_service
teaching_roster_service
TeachingClass/Roster models
selection final service
相关MySQL/真值测试。
只证明并保护 ScopeHead（正式课表头）、TeachingRoster（正式名单）、Selection LOCK→Roster，不重写。

B-W1：
读取 B-P0-04/B-P0-07、Selection rules/eligibility（选课规则/资格）。
源码：
selection_core_service
selection_final_service
selection router/models
audit/DecisionTrace
tests。
先RED：
坏JSON不得fail-open；validator不得commit；一个拒绝只记一次；SelectionPreflight必须纯读。
后端变化后同步选课控制台的预检/阻断UI并截图+真实点击。

B-W2：
读取A线已冻结的A-C1/A-C2/A-C3/A-C4；如果尚未冻结，不伪造合同，继续B独立工作。
再读取 B-P0-05/B-P0-06 和C线EffectiveGrade正式读取合同/当前服务。
源码：
selection_core_service
effective_grade_policy_service
AcademicGrade legacy
schedule_truth_service
ScopeHead
tests。
替换：
AcademicGrade/name → EffectiveGrade Provider；
EFFECTIVE schedule rows → ScopeHead active batch。
冻结 B-C1 Published Schedule Contract、B-C2 Selection Eligibility Contract。
同步学生资格提示、冲突提示、正式课表消费者UI，截图视觉复审+真实点击。

B-W3：
读取 B-P0-01 和排课UI附录。
源码：
AaScheduleMaintainView.vue
AaSchedulingConsoleView.vue
academic-affairs.api
schedule final service
Task picker
Term picker
Academic File Exchange。
必须：
管理PC Task-first；
新排课显式taskId；
课程/教师/班级只读回显；
去18周；
去文本CSV正式writer；
批量导入走File Exchange；
name fallback仅legacy计量。
这批必须有修改前/后截图；视觉识别检查排课表格、弹窗、冲突态、窄屏；再用真实浏览器点击“选择Task→排课→冲突→刷新→回读”。

B-W4：
读取 B-P0-02/B-P0-03、A-C4、Selection batch/course附录。
源码：
AaSelectionConsoleView.vue
selection core/final service
Selection models
TeachingTask
tests。
收口term/window/scope/rule version/hash，SelectionCourse必须绑定同学期、同课程、合法formationMode的Task。
数据库约束按“盘点→应用层先封→回填→对账→INT迁移”。
同步选课控制台新建/发布/课程供给UI；截图正常/阻断/只读；真实点击生命周期。

B-W5：
读取 B-P0-08、Lottery/reselect/course cancel（抽签/补选/停开）附录。
源码：
AaSelectionStudentView.vue
学生小程序选课页
studentCourses/mySelections/reselectGuide
final projection。
后端返回 status/statusLabel/phase/allowedActions/reason/howToResolve/window/lottery/reselect。
PC和小程序只渲染allowedActions。
必须截图并识别：
OPEN、PENDING_LOTTERY、LOTTERY_LOST、COURSE_CANCELLED、LOCKED至少对应关键场景；
真实点击选课/退课/补选/刷新/换端。
冻结 B-C3 Student Selection Projection Contract。

B-W6：
读取V1.5 peak/FCFS/lottery（高峰/先到先得/抽签）和并发测试。
真实MySQL：
最后1名额100+并发；
1k burst；
双Lottery draw；
LOCK/drop竞态；
Selection↔Roster人数/hash；
deadlock retry；
邻租户。
完成 B Contract Freeze，通知C只消费正式TeachingRoster。

禁止：
重建ScopeHead/OfficialSchedule/TeachingRoster；
课程名称做正式资格；
旧AcademicGrade做先修；
旧EFFECTIVE行做当前课表；
坏JSON降级不限；
validator内部commit；
前端自己算allowedActions；
SelectionCourse无Task；
无term正式发布；
抢共享迁移/权限/公共路由；
skip/xfail/ignore；
SQLite替代MySQL；
force；
合并main。

Waitlist/Swap/Saved Schedule/Reserve Capacity（候补/换课/保存课表/定向容量）全部排在当前P0之后。

固定循环：
文档 → exact-head源码 → CURRENT FACT → RED → 后端修根因 → targeted → MySQL
→ Frontend Impact Review
→ UI同步
→ before/after截图
→ 实际打开截图做视觉识别
→ 修视觉问题并重截图
→ 真实浏览器可见控件点击E2E
→ refresh/relogin/跨端
→ KEEP regression
→ exact-head证据
→ 回写B施工地图
→ 下一安全Wave。

后端绿但UI/截图/真实点击未完成时只能标 BACKEND_GREEN_UI_OPEN，禁止COMPLETED。

现在：
新建固定分支 → Draft PR → 写B线施工地图 → B-W0。
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



## 0C-B. B线后端变化对应的前端同步重点

B线是前后端同步最重的一线。必须重点复查：
- AaScheduleMaintainView（课表维护）；
- AaSchedulingConsoleView（排课控制台）；
- 排课批次/规则/冲突/导入页面；
- AaSelectionConsoleView（选课控制台）；
- AaSelectionStudentView（学生电脑端选课）；
- 学生小程序选课；
- 学生正式课表；
- 教师正式课表；
- Selection roster（选课名单）与正式TeachingRoster展示。

特别要求：
- 后端 Task-first（教学任务优先）后，管理PC必须同步Task-first，课程/教师/班级只读回显。
- 后端 ScopeHead（正式课表头）成为唯一课表真值后，所有“当前课表”UI必须使用同一正式批次，旧EFFECTIVE行不得继续决定页面。
- SelectionPreflight（选课预检）新增 blocker（阻断）后，教务端必须能在OPEN（开放）前看到同一个阻断。
- 学生端必须覆盖 PENDING_LOTTERY（待抽签）、LOTTERY_LOST（未中签）、COURSE_CANCELLED（课程停开）、LOCKED（已锁名单）等状态。
- 学生按钮只消费 allowedActions（允许动作）；PC和小程序必须一致。


---

# B（排课选课线）— 当前代码精确审计与最终施工裁决

## B-0 当前真实成熟度

**当前代码生产成熟度：73/100。目标：99/100。**

B线是本轮最重要的主阻断线。不是因为底层全部弱，恰恰相反：**正式课表和正式名单内核很强，但选课资格和管理界面还在消费旧真值。**

### 当前必须保护的强能力
- `academic_affairs_schedule_truth_service.py（正式课表真值服务）` 已建立 `(term, scope) → ScopeHead.activeBatch（学期范围→正式课表当前批次）`。
- ScopeHead（正式课表头）发布有行锁、版本、并发创建保护、SUPERSEDED（被替代）历史和跨批次资源冲突。
- `academic_affairs_schedule_final_service.py（排课最终服务）` 已Task-first（任务优先），校验READY（可排）、同学期、周次、教室类型/容量、教师/班级/教室冲突和教学任务周学时。
- `AaTeachingClass（教学班） + RosterVersion（名单版本） + Member（成员）` 已成熟。
- `academic_affairs_teaching_roster_service.py（正式教学名单服务）` 已做到Selection（选课）存在时不回退行政班旧名单；LOCK（锁名单）时同事务生成正式名单。
- FCFS（先到先得）容量条件更新和Lottery（抽签）确定性基础较强。

### 当前真正P0（最高优先级）
1. 排课管理PC（电脑端）仍自由拼课程/教师/班级，不传taskId（教学任务编号）。
2. 页面还硬编码18周，并保留文本CSV式导入writer（写入口）。
3. Selection批次可缺term（学期）、时间窗、scope（范围）。
4. SelectionCourse（可选课程）可缺TeachingTask（教学任务）。
5. 坏rule_json/apply_scope_json/prerequisite_json（规则/范围/先修配置）会fail-open（失败放行）。
6. 先修/重修仍读旧AcademicGrade（旧成绩投影），而且按课程名称判断。
7. 时间冲突仍扫旧EFFECTIVE（有效）课表行，不读ScopeHead（正式课表头）。
8. validator（校验器）内部commit（提交事务），同一冲突存在双审计路径。
9. 学生PC（电脑端）没有canonical allowedActions（正式允许动作），抽签状态投影不完整。
10. 部分列表全量 `.all()` 后Python分页，学院批次元数据范围也仍有旧宽松语义。

---

## B-P0-01 后端已经Task-first（任务优先），管理PC（电脑端）却仍旧

### 当前代码事实
`AaScheduleMaintainView.vue（课表维护页面）`：
- 先选行政班；
- 空格点击后让用户自由选Course（课程）、Teacher（教师）、Classroom（教室）；
- `doAdd（新增排课）` 发送courseName（课程名称）、teacherName/key（教师名称/键）、classId（班级编号）；
- **没有taskId（教学任务编号）**；
- `endWeek（结束周）` 默认18；
- 内置文本导入，格式是“星期,节次,课程,教师,教室,起止周”；
- 文本导入里甚至存在 `teacherKey = teacherName（教师键等于教师姓名）`。

而后端最终服务已经支持：
- taskId；
- READY Task（可排教学任务）；
- 稳定Task身份；
- 课程/教师/班级由Task解析；
- 正式冲突和周学时检查。

### 本质
这是“新内核 + 旧UI（界面）”合同分裂。当前生产系统仍靠后端名称fallback（兼容回退）兜住旧页面。

### 施工
1. AaScheduleMaintainView（课表维护）首要对象改成TeachingTask（教学任务）。
2. Course/teacher/class（课程/教师/班级）改只读回显。
3. 新建排课payload（载荷）必须显式taskId。
4. 周次从A-C1 Term Context Contract（学期上下文合同）读取。
5. 页面级文本导入writer删除；批量导入跳Academic File Exchange（教务文件交换中心）。
6. 后端name fallback（名称回退）保留为legacy（历史兼容）并计量调用量，归零后再退役。

### RED（先失败测试）
- 正式页面新增排课没有taskId必须失败。
- 17周学期不能产生18周默认。
- 同名课程两个Task不能靠名称误匹配。
- 同名教师不能以姓名作为稳定身份。
- 文本导入不得绕开File Exchange（文件交换）。

---

## B-P0-02 Selection（选课）批次创建合同太松

### 当前代码
`AaSelectionConsoleView.vue（选课控制台）` 新建批次只有：
- batchName（批次名）
- maxCredits（最大学分）
- remark（备注）

没有：
- termId（学期编号）
- selectStart/selectEnd（选课开始/结束）
- applyScope（适用范围）

后端 `create_batch（创建批次）` 同样允许termId为空，非法日期还可能解析成None（空值）。

### 结果
系统允许创建“看起来存在，但无法作为正式学校选课制度实例”的死批次。

### 最终合同
DRAFT（草稿）可以不完整，但PUBLISH（发布）之前必须：
- formal term（正式学期）
- valid window（有效窗口）
- frozen scope（冻结适用范围）
- rule schema/hash（规则模式/哈希）
- 至少一门合法SelectionCourse（可选课程）
- 所有课程都绑定正式TeachingTask（教学任务）

PUBLISH/OPEN/CLOSE/LOCK（发布/开放/关闭/锁名单）全部调用一个纯SelectionPreflight（选课预检）。

---

## B-P0-03 SelectionCourse（可选课程）不能继续把Task（教学任务）当“选填”

### 当前事实
管理页面TeachingTask Picker（教学任务选择器）明确写“选填”。

核心服务中：
- teachingTaskId可空；
- 即使传入无效Task，也没有在该服务层形成足够强的同学期/同课程/状态拒绝。

### 根因
旧Selection（选课）还能从Course（课程）直接创建供给，下游新Roster（名单）架构却要求Task身份。

### 最终合同
每一个正式SelectionCourse必须：
- 有term（学期）；
- 有TeachingTask；
- Task属于同term；
- Task课程身份与SelectionCourse课程一致；
- formationMode（形成方式）允许Selection；
- Task达到可选课业务状态；
- 后续Schedule/Roster/Exam/Grade（课表/名单/考试/成绩）全部可沿taskId回链。

### 迁移顺序
**禁止直接先改NOT NULL（非空）。**

必须：
`inventory（盘点） → 阻止新脏数据 → 回填/标异常 → 对账 → INT迁移 → 再验收`

---

## B-P0-04 坏JSON（结构化配置）当前会fail-open（失败放行）

### 当前代码事实
在 `academic_affairs_selection_core_service.py（选课核心服务）`：

- `_rule（规则读取）` 解析失败后会落默认值；
- apply_scope_json（适用范围）解析失败会变空对象，等价不限范围；
- prerequisite_codes_json（先修代码）解析失败会变空列表，等价没有先修。

### 这是正式资格安全缺陷
系统不能把：
“我不知道规则是什么”
解释成：
“没有规则限制”。

### 最终合同
所有正式规则对象：
- schemaVersion（模式版本）
- publishedHash（发布哈希）
- strict parse（严格解析）
- immutable after open（开放后核心规则不可直接改）

任何解析失败：
`UNKNOWN/BLOCKED（未知/阻断）`
而不是：
`UNRESTRICTED（无限制）`

### RED
- 坏scope不能选课。
- 坏prerequisite不能选课。
- 坏rule不能OPEN。
- 管理预检和学生实时资格必须得到同一阻断码。

---

## B-P0-05 先修/重修判断还在消费旧成绩真值

### 当前代码事实
`_passed_course_names（已通过课程名称）`：
读取旧 `AcademicGrade（旧成绩投影）`
并返回 `course_name（课程名称）` 集合。

先修代码：
先把courseCode（课程代码）解析成名称，再用名称和passed names（已通过名称）比较。

而C线当前 `EffectiveGrade（有效成绩）` 已经：
- 优先courseId/courseCode/version（课程编号/代码/版本）；
- 支持多次修读；
- 策略缺失时fail-closed（失败阻断）；
- 保存不可变策略snapshot（快照）；
- 历史name-only（仅名称）记录不会静默合并。

### 本质
**B线在消费C线已经淘汰的旧成绩语义。**

### 后果
- 同名课程串课；
- 课程改名后先修错误；
- 补考后资格不更新；
- 重修后仍按旧名字判断；
- 成绩认定/更正后B和D结论可能不一致。

### 施工
B不新造成绩逻辑。
只建立只读EnrollmentAcademicRecordProvider（选课学业记录提供者）：
- 输入studentId、course identity、asOf（学生编号/课程身份/时间点）；
- 输出EffectiveGrade（有效成绩）/attempt（修读次数）/policy snapshot（策略快照）。

Selection（选课）先修和重修只能读这个provider。

### RED
- 同名不同courseId不串。
- 课程改名不改变资格。
- 补考由FAIL→PASS后先修资格更新。
- 无有效多次修读策略时阻断，不猜“最新成绩”。

---

## B-P0-06 时间冲突仍读取旧EFFECTIVE（有效）行

### 当前事实
`_task_slots（任务时段）`：
直接查询 `AaScheduleItem.status == EFFECTIVE（有效）`。

而当前正式课表真值已经升级为：
`term + scope → AaScheduleScopeHead.active_batch_id（学期+范围→正式课表头当前批次）`

正式发布新批次后旧批次状态为SUPERSEDED（被替代）。

### 根因
Selection（选课）冲突消费者没有跟上Schedule Truth（课表真值）升级。

### 生产风险
旧课表可能继续制造假冲突；真正新课表可能未成为选课资格来源。

### 施工
建立唯一PublishedScheduleProvider（正式课表提供者）：
- 从ScopeHead（正式课表头）解析active batch（当前批次）；
- 只返回当前正式Task occurrences（教学任务课次）；
- Selection、学生课表、教师课表共用。

legacy EFFECTIVE（历史有效行）只能在可证明旧数据上fallback（回退），并计量调用。

### Gold
发布v1课表→存在冲突；
发布v2替代并消除冲突；
Selection立即不再被v1阻断；
v1仍可历史回放。

---

## B-P0-07 validator（校验器）内部commit（提交）破坏事务纯度

### 当前精确问题
`_record_conflict_reject（记录冲突拒绝）`
内部直接：
`db.commit（提交事务）`

而：
- `_validate_enroll（校验选课）` 冲突时先记录再raise（抛异常）；
- `selection_final_service（选课最终服务）` catch（捕获）后又可能记录一次。

### 两个问题
1. 一次冲突可能两条审计；
2. 更危险的是校验函数可以提前提交外层事务中还没想提交的东西。

### 最终事务规则
- Validation/Preflight（校验/预检）必须纯读，绝不commit。
- Command（正式命令）拥有唯一事务边界。
- Audit/DecisionTrace（审计/决策轨迹）由最外层统一写一次。
- 如果失败审计必须在业务回滚后仍保留，用明确独立审计事务，不允许“偷偷commit当前session（会话）”。

### RED
- 同一冲突只一条拒绝事实。
- 校验前插入一个未提交对象→校验失败→对象不得被意外提交。
- 重复HTTP（接口）请求审计符合幂等合同。

---

## B-P0-08 学生端状态机仍是“简单先到先得”时代

### 当前学生PC（电脑端）
`AaSelectionStudentView.vue（学生选课页）` 状态映射只有：
- SELECTED（已选）
- LOCKED（已锁）
- DROPPED（已退）
- COURSE_CANCELLED（课程停开）

没有正式处理：
- PENDING_LOTTERY（待抽签）
- LOTTERY_LOST（未中签）

按钮由本地selectedIds（已选编号集合）判断：
- 不是SELECTED/LOCKED就可能出现“选课”。

### 风险
待抽签学生可能再次看到“选课”，最终只能靠后端报错；学生无法理解当前阶段与下一步。

### 最终Student Projection Contract（学生投影合同）
后端返回：
- status/statusLabel（状态/中文状态）
- phase（阶段）
- eligibility（资格）
- allowedActions（允许动作）
- reason（原因）
- howToResolve（下一步）
- window（时间窗）
- lottery/reselect（抽签/补改选）上下文

PC（电脑端）和miniapp（小程序）**只渲染allowedActions**。

客户端传 `reselect=true（补选标志）` 仍不能成为真值；后端继续根据真实COURSE_CANCELLED（课程停开）事实独立判断。

---

## B-P1-09 dataScope（数据范围）和分页仍有旧债

### 当前代码
Selection批次列表存在“学院管理员本期先全量只读，范围收敛在名单/统计层”的历史注释。
多个列表 `.all()` 后再Python切片。

### 生产标准
- object scope（对象范围）在SQL（结构化查询语言）查询前就确定；
- 空scope（范围）返回0，不是全校；
- count + limit/offset（计数+分页）在数据库完成。

### Gold
- 学院A看不到学院B私有批次元数据；
- pageSize=20只取20左右必要行；
- 20K（两万学生）和多年批次历史下响应稳定。

---

# B-1 当前强底座：禁止重写

## Schedule Truth（正式课表真值）
保留：
- ScopeHead（正式课表头）
- activeBatch（当前批次）
- version（版本）
- SUPERSEDED（被替代）
- 跨批次教师/教室/班级冲突
- MySQL（关系型数据库）新鲜读/锁策略

## TeachingRoster（正式教学名单）
保留：
- TeachingClass（教学班）
- RosterVersion（名单版本）
- roster_hash（名单哈希）
- source_type（名单来源）
- LOCKED/SUPERSEDED（锁定/被替代）
- Selection存在时fail-closed（失败阻断），不回退旧行政班名单
- Selection LOCK→Roster（选课锁定→正式名单）同事务投影

**B线不新建第二Roster，不新建第二OfficialSchedule（正式课表）。**

---

# B-2 七个持续施工波次

## B-W0 强底座回归冻结
先跑：
- schedule active truth（正式课表真值）
- TeachingRoster（正式名单）
- selection lock scaling（选课锁定规模）
- MySQL scope（数据范围）
- Lottery（抽签）
- FCFS（先到先得）

任何后续施工破坏这些测试，立即停。

## B-W1 SelectionPreflight（选课预检）纯化
先修：
- JSON fail-open（配置失败放行）
- validator commit（校验器提交）
- 双审计
- 规则发布冻结

输出：
`B-C2 Selection Eligibility Contract（选课资格合同）` 初版。

## B-W2 两个旧消费者替换
- AcademicGrade（旧成绩）→ EffectiveGrade Provider（有效成绩提供者）
- EFFECTIVE schedule rows（旧有效课表行）→ ScopeHead Provider（正式课表头提供者）

输出：
`B-C1 Published Schedule Contract（正式课表合同）`
`B-C2 Selection Eligibility Contract（选课资格合同）` 冻结。

## B-W3 排课管理PC Task-first（任务优先）
- 页面Task-first；
- 去18周；
- 去文本writer；
- 批量导入File Exchange（文件交换）。

## B-W4 Selection批次与课程身份
- batch term/window/scope（批次学期/时间/范围）
- SelectionCourse Task required（可选课程任务必需）
- 脏数据清查
- 应用层先封
- 必要数据库约束由INT迁移。

## B-W5 学生PC/小程序投影
- allowedActions（允许动作）
- Lottery（抽签）
- COURSE_CANCELLED（停开）
- reselect（补改选）
- LOCKED（锁定）
- 中文失败原因。

输出：
`B-C3 Student Selection Projection Contract（学生选课投影合同）`

## B-W6 MySQL（关系型数据库）高峰封板
- 最后1名额100+并发；
- 1k burst（千级突发）；
- 双draw（双抽签）；
- LOCK/drop（锁名单/退课）竞态；
- Roster hash/count（名单哈希/人数）对账；
- deadlock retry（死锁重试）无半写。

完成后：
`B Contract Freeze（B线合同冻结）`
C线同步正式Roster合同。

---

# B-3 真实学校Gold（最终验收基线）

1. 管理端只能对READY Task（可排教学任务）正式排课。
2. 同名课程/教师不会解析错Task。
3. 17周学期不出现18周默认。
4. 批量排课全部走File Exchange（文件交换）。
5. ScopeHead v2发布后v1不再影响当前选课冲突。
6. 无term批次不能发布。
7. 非法时间窗不能发布。
8. 坏scope JSON不能放行。
9. 坏先修JSON不能放行。
10. SelectionCourse无Task不能成为正式课程供给。
11. 跨学期Task不能挂SelectionCourse。
12. 同名不同课程不串先修。
13. 补考后EffectiveGrade更新，先修资格跟随更新。
14. 一次时间冲突只记一次拒绝审计。
15. 校验失败不提前commit调用者其他变化。
16. 最后1名额100并发不超卖。
17. 重复点击不双SelectionRecord（选课记录）。
18. Lottery双执行只一个生效。
19. PENDING_LOTTERY不出现再次选课动作。
20. LOTTERY_LOST显示真实下一步。
21. COURSE_CANCELLED进入补改选。
22. LOCK前不能被考勤/考试/成绩消费。
23. LOCK后Roster人数/hash和Selection一致。
24. 学院A不能读B私有批次。
25. 邻租户永不泄漏。
26. PC和小程序状态/allowedActions完全一致。
27. 1k突发下业务满额和系统故障能区分。
28. 所有新正式课表项都能回链taskId。
29. legacy name fallback调用量可观测。
30. B冻结后C不再需要读取SelectionRecord来猜正式名单。

---

# B-4 自行纠错与反证

1. **纠正“排课整体弱”**：后端课表真值很强，真正弱的是管理PC仍使用旧合同。
2. **纠正“Selection只是少几个规则”**：它仍消费旧成绩和旧课表，属于跨域Authority消费者错误。
3. **纠正“坏JSON只是配置问题”**：当前会放宽正式资格，必须P0。
4. **纠正“重复审计只是日志小问题”**：validator内部commit会破坏外层事务原子性。
5. **确认Roster不应重建**：TeachingRoster已经成熟，B只负责正确生成/消费。
6. Waitlist（候补）、Swap（换课）、Saved Schedule（保存课表）、Reserve Capacity（定向名额）继续放在主P0之后，只有目标学校明确需要才进入正式建设。

---

# B-5 最终签字

必须满足：
- 旧成绩消费者清零；
- 旧课表消费者清零或仅受控legacy；
- SelectionPreflight纯读；
- JSON配置0 fail-open；
- 新SelectionCourse 100% Task-bound（绑定任务）；
- 管理PC 100% Task-first；
- 学生两端100% allowedActions；
- MySQL并发不超卖、不双写；
- TeachingRoster合同冻结；
- P0=0；
- 需要本轮完成的P1=0；
- C线同步后考勤/考试/成绩消费者全部保持正式名单Gold。

---

# 附录：V1.5 B线详细业务设计

> 以下保留V1.5中Waitlist（候补）、Swap（换课）、Saved Schedule（保存课表）、补选、课程取消、页面矩阵、真实学校场景等详细设计。若与V2.1当前代码裁决冲突，以V2.1为准。

# B — Schedule/Selection：Task-first排课·正式课表·Selection制度·TeachingRoster — V1.5 四线并行深审增强唯一施工总册

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
本线真实学校验收场景：**49 条最低场景**。

状态分布：
- `CURRENT-BLOCKER/REWIRE`：1
- `CURRENT-HARDEN`：4
- `CURRENT-BLOCKER`：1
- `CURRENT-KEEP/HARDEN`：3
- `EXISTS-HARDEN`：2
- `VERIFY-FIRST / BENCHMARK-GAP`：3
- `VERIFY-FIRST`：2
- `NEW ORCHESTRATION over existing truths`：1
- `VERIFY-FIRST/HARDEN`：1
- `CURRENT-REWIRE`：1
- `HISTORICAL-VALID / OPS-HARDEN`：1



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


# Ⅵ-B. B线 Current Repo Evidence Inventory

- `AaScheduleBatch / AaScheduleItem / AaScheduleScopeHead / AaSchedulePublish / AaScheduleChange`：正式课表与发布后变更事实。
- `academic_affairs_schedule_final_service.py`：Task-first、READY、同学期、周次、教室容量/类型、周学时、冲突。
- `AaScheduleMaintainView.vue`：仍是关键REWIRE点，管理PC不能继续自由拼课程+教师+班级。
- Academic File Exchange已经有排课XLSX ImportJob；B线禁止另造CSV/UploadJob。
- `AaSelectionBatch / Course / Round / Record`：Selection主事实。
- `selection_final_service`：行锁、StudentAcademicFact、LOCK→TeachingRoster等强基座。
- `selection_round_service`：SHA256确定性抽签、容量原子更新。
- repo已有“补选管理”三级施工卡和正式router/page证据；补选不是新增模块。
- academic生产代码对`WAITLIST`明确证据弱；旧V2明确waitlist=LATER。
- planner/saved schedule/registration appointment/swap等current证据弱，全部先VERIFY-FIRST。
- `AaTeachingClass + RosterVersion + Member`已成熟；旧V2‘等成员表上线’的假设已过时。

# Ⅶ. 市场对标 → 当前仓库差距矩阵

| 能力 | 成熟系统/国内场景 | 当前裁决 | V1.5动作 |
|---|---|---|---|
| Task-first排课 | 成熟SIS section驱动 | CURRENT-BLOCKER | PC最终封口 |
| 正式课表版本 | 成熟SIS发布版本 | CURRENT-KEEP/HARDEN | ScopeHead唯一 |
| 分批/轮次 | PeopleSoft/Workday appointments/国内六批 | CURRENT-HARDEN | 复用Batch/Round/Scope |
| 资格排障 | Workday troubleshooting | CURRENT-HARDEN | 统一Preflight |
| 补选申请 | 国内正方真实流程 | EXISTS-HARDEN | 不是新增 |
| Waitlist | PeopleSoft/Workday | VERIFY-FIRST/LATER | 与Lottery/补选分离 |
| Swap | PeopleSoft/Workday | VERIFY-FIRST | 原子事务编排 |
| Saved Schedule | PeopleSoft/Workday | BENCHMARK-GAP | 私有草稿，不占容量 |
| Reserve Capacity | PeopleSoft/Workday | VERIFY-FIRST | Selection policy子结构 |
| 必修班取消重分配 | 国内真实流程 | VERIFY-FIRST/HARDEN | 批量reassign |
| 选修取消补改选 | 国内真实流程 | CURRENT-HARDEN | COURSE_CANCELLED |
| Add/Drop/Withdraw | Workday | VERIFY-FIRST | 按日期/记录语义拆分 |
| Selection高峰 | 成熟注册系统通用 | CURRENT-SCALE-GATE | 真实MySQL 1k burst |
| 正式Roster | 本系统强Authority | CURRENT-KEEP | LOCK后统一下游名单 |

# Ⅵ. V1.5 深度施工卡


---

## B15-01 — Task-first 排课管理 PC 最终封口

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-BLOCKER/REWIRE`  
**外部成熟度信号：** 成熟SIS排课以正式section/teaching assignment为身份，不允许前端自由拼课程+教师+班级。

### 1. 学校业务问题
- 旧UI若继续自由拼正式身份，会产生orphan、错教师、错学期课表。
- 学校批量排课时风险被放大。

### 2. 当前 exact-head 事实
- schedule_final_service已Task-first并校验READY/term/weeks/room/conflict。
- AaScheduleMaintainView仍是主要REWIRE点。

### 3. 历史设计 Reconciliation
- V1.3/V1.4已锁定该P0；历史V2排课设计补页面交互细节。

### 4. 唯一 Authority 决策
- TeachingTask是排课唯一业务身份；ScheduleItem只记录时间/地点/occurrence。
- 名称resolver仅历史COMPAT。

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
- 新写无taskId必须RED。
- 非READY排课RED。
- 前端篡改course/teacher identity RED。
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

## B15-02 — 正式课表 ScopeHead 单一读真值

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 成熟教务必须有明确current published schedule版本。

### 1. 学校业务问题
- Selection冲突、学生/教师课表、调课和考试都需要知道哪一版正式。

### 2. 当前 exact-head 事实
- AaScheduleScopeHead已有active_batch_id/version/publishedAt。
- Selection/Student facade仍有旧EFFECTIVE/class_id兼容。

### 3. 历史设计 Reconciliation
- V1.3已定义Published Schedule Truth；旧“状态=EFFECTIVE就是当前”假设废弃。

### 4. 唯一 Authority 决策
- term+scope→ScopeHead.activeBatch唯一正式读入口。
- 历史版本显式asOf/版本选择。

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
- 双active head RED。
- 旧batch参与Selection冲突RED。
- v1→v2后四端仍读v1 RED。
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

## B15-03 — Selection Batch：学期 / 时间窗 / Scope / Round 制度模型

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-BLOCKER`  
**外部成熟度信号：** Workday/PeopleSoft registration appointments和国内高校分批选课都证明‘谁何时能选’是正式制度。

### 1. 学校业务问题
- 无term/window/scope会形成能创建不能发布的死批次。
- 学校常按年级、课程性质分批开放。

### 2. 当前 exact-head 事实
- AaSelectionBatch/Round存在；当前管理UI创建字段不足。
- Final service正式写链更严格。

### 3. 历史设计 Reconciliation
- 旧V2已设计batch detail、适用范围、轮次、规则冻结，重新纳管。

### 4. 唯一 Authority 决策
- Batch是制度实例，Round表达阶段/算法/时间；registration appointment优先映射Round+Scope。
- 禁止再造RegistrationEngine。

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
- 无term批次OPEN RED。
- 坏scope fail-open RED。
- 两个互斥round同时开放RED。
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

## B15-04 — SelectionPreflight + Troubleshooting Console

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** Workday正式提供Registration Troubleshooting；成熟系统应提前解释为什么不能选。

### 1. 学校业务问题
- 学生不能只看到‘选课失败’。
- 教务发布批次前必须一次看到配置阻断。

### 2. 当前 exact-head 事实
- selection service / decision trace已有资格和决策基础。
- 当前Publish/OPEN/LOCK preflight仍需统一。

### 3. 历史设计 Reconciliation
- 历史V2已要求ruleCode/message/howToResolve，继续升级为正式DTO。

### 4. 唯一 Authority 决策
- 一个纯Preflight evaluator复用PUBLISH/OPEN/CLOSE/LOCK和student eligibility。
- 纯验证不得commit。

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
- 服务异常不得eligible=true。
- admin/student同一输入不同结论RED。
- 坏规则无blocker RED。
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

## B15-05 — FCFS 容量原子性 / 绝不超卖

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN`  
**外部成熟度信号：** 所有成熟注册系统都把section capacity当强一致约束。

### 1. 学校业务问题
- 最后一个名额是选课高峰的核心并发风险。
- 超卖属于正式事实错误。

### 2. 当前 exact-head 事实
- 现有Selection Round/Final服务已有行锁/容量原子更新基础。

### 3. 历史设计 Reconciliation
- 历史选课压测与容量施工卡并入当前MySQL协议。

### 4. 唯一 Authority 决策
- SelectionCourse capacity + SelectionRecord为唯一事实；缓存计数必须可reconcile。
- Roster只在LOCK后形成。

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
- 最后1席100+并发selected<=capacity。
- 重复点击不双记录。
- 锁超时不半写。
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

## B15-06 — Lottery 确定性抽签 Evidence Manifest

**优先级：** `P1`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN`  
**外部成熟度信号：** 抽签类选课的成熟度关键是可复核，而不是更复杂的随机算法。

### 1. 学校业务问题
- 学校投诉时要说明候选集合、规则版本、算法版本和结果。

### 2. 当前 exact-head 事实
- round service已有SHA-256 deterministic draw、CLOSED→DRAWN claim、原子容量。

### 3. 历史设计 Reconciliation
- 旧设计的Lottery与Waitlist边界继续有效。

### 4. 唯一 Authority 决策
- 不重写Lottery；只补candidateHash/resultHash/algorithmVersion/drawnAt等不可变证据。
- 禁止redraw。

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
- 双draw只有一个成功。
- 候选集合在draw期间变化RED。
- 相同输入hash不可复现RED。
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

## B15-07 — 补选申请（审批型）生产闭环

**优先级：** `P0`  
**V1.5 裁决：** `EXISTS-HARDEN`  
**外部成熟度信号：** 广州南方学院2026公开正方流程明确：正式选课后可提交补选申请，经开课单位审批后加入教学班。

### 1. 学校业务问题
- 补选申请与Waitlist不同，是国内学校真实异常处理流。
- 不能线下找老师直接加名单。

### 2. 当前 exact-head 事实
- repo已有补选三级施工卡、course_selection_router、学生选课页面等证据。
- 需要exact-head确认最终production closure。

### 3. 历史设计 Reconciliation
- 历史‘补选管理’不是新增设计，标HISTORICAL-MERGED/HARDEN。

### 4. 唯一 Authority 决策
- 审批通过后仍调用canonical Selection writer重新preflight容量/冲突/资格。
- 禁止审批直接INSERT Roster。

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
- 审批时容量已满RED。
- 越权审批RED。
- 重复申请RED。
- 通过后Roster/课表不一致RED。
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

## B15-08 — WAITLIST 候补自动递补

**优先级：** `P1`  
**V1.5 裁决：** `VERIFY-FIRST / BENCHMARK-GAP`  
**外部成熟度信号：** PeopleSoft/Workday都有waitlist position、自动/人工promotion、offer/expiry；旧V2明确该能力LATER。

### 1. 学校业务问题
- 候补适合FCFS满额后释放席位，不等于Lottery落签，也不等于补选申请。

### 2. 当前 exact-head 事实
- 当前academic生产代码对WAITLIST正式Authority证据弱，检索主要命中历史设计。

### 3. 历史设计 Reconciliation
- 旧V2边界继续有效：未中签不自动进候补；Waitlist先LATER。

### 4. 唯一 Authority 决策
- 仅在目标学校明确需要且exact-head确认缺失后，作为Selection子域设计。
- promotion最终仍调用canonical enroll writer。

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
- Lottery落签自动进waitlist RED。
- 一席多offer RED。
- expired offer仍可accept RED。
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

## B15-09 — 原子 Swap 换课

**优先级：** `P1`  
**V1.5 裁决：** `VERIFY-FIRST / BENCHMARK-GAP`  
**外部成熟度信号：** PeopleSoft/Workday把Swap作为独立原子注册动作。

### 1. 学校业务问题
- 学生先退旧课再选新课会出现新课失败、旧课也丢失。
- 换教学班同样需要原子语义。

### 2. 当前 exact-head 事实
- current repo生产级swap证据弱；历史表单设计有换课字样但不足以证明Authority。

### 3. 历史设计 Reconciliation
- 历史UI设想不等于正式事务。

### 4. 唯一 Authority 决策
- Swap=canonical target preflight + reserve + drop old + create target同事务编排。
- 不建第二Enrollment truth。

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
- target满额失败时old record必须仍在。
- 两个交叉swap死锁/半写RED。
- 重复请求RED。
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

## B15-10 — Saved Schedule / 预选方案 / A-B备选

**优先级：** `P1`  
**V1.5 裁决：** `VERIFY-FIRST / BENCHMARK-GAP`  
**外部成熟度信号：** PeopleSoft有Shopping Cart/Planner，Workday有Saved Schedule；国内高校也要求学生提前根据课表准备备选。

### 1. 学校业务问题
- 正式开选前学生需要做冲突和学分规划。
- 计划不能抢容量。

### 2. 当前 exact-head 事实
- current repo未检索到明确academic saved schedule生产能力。

### 3. 历史设计 Reconciliation
- 历史若有‘选课计划’只作为UX参考。

### 4. 唯一 Authority 决策
- Saved Schedule是学生私有草稿，只引用taskId，不生成SelectionRecord，不占容量。
- 正式提交时重新preflight。

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
- 草稿占容量RED。
- 窗口外一键变正式RED。
- 旧Task失效未提示RED。
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

## B15-11 — Reserved Capacity / 定向名额

**优先级：** `P1`  
**V1.5 裁决：** `VERIFY-FIRST`  
**外部成熟度信号：** PeopleSoft/Workday都支持reserve capacity；国内公共课程也常给特定年级/专业保留名额。

### 1. 学校业务问题
- 单一capacity无法表达定向座位。
- 规则要公平且可解释。

### 2. 当前 exact-head 事实
- 当前Selection scope/rule有适用范围；保留容量正式实现需精审。

### 3. 历史设计 Reconciliation
- 旧rule_json可作为优先扩展点，不急建规则表。

### 4. 唯一 Authority 决策
- 总capacity仍属SelectionCourse；reserved groups只是policy子结构。
- 总reserved不得超过capacity。

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
- general pool抢占保留席RED。
- reserved>capacity RED。
- 不同group并发计数漂移RED。
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

## B15-12 — 必修教学班取消后的批量重新分配

**优先级：** `P0`  
**V1.5 裁决：** `NEW ORCHESTRATION over existing truths`  
**外部成熟度信号：** 国内高校公开选课通知明确：必修班取消时调入其他不冲突且有容量的教学班。

### 1. 学校业务问题
- 固定必修不能简单取消后让学生自行承担。
- 批量移动要保护Roster/Schedule/容量。

### 2. 当前 exact-head 事实
- 低人数、Selection、TeachingRoster、Schedule已有基础；完整cancel→reassign闭环需verify。

### 3. 历史设计 Reconciliation
- 旧低人数设计可复用，实际成员事实使用当前Roster。

### 4. 唯一 Authority 决策
- preview target sections→冲突/容量校验→人工确认→生成新RosterVersion。
- 无法分配者保留异常队列，禁止静默丢学生。

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
- target满额/冲突时学生从source消失RED。
- 批量重复执行双移动RED。
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

## B15-13 — 选修教学班取消 → COURSE_CANCELLED → 补改选

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 国内公开流程明确：选修教学班取消后通知学生改选其他课程/教学班。

### 1. 学校业务问题
- 取消不能只改course状态；学生要有下一步。

### 2. 当前 exact-head 事实
- Selection已有COURSE_CANCELLED、低人数/reselect基础；学生Projection表达仍不足。

### 3. 历史设计 Reconciliation
- 旧低人数策略继续有效。

### 4. 唯一 Authority 决策
- 保留SelectionRecord历史，状态进入COURSE_CANCELLED；后续补选产生新正式record。
- 毕业要求只提示风险，不自动替学生选课。

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
- 取消后仍出现在正式课表RED。
- 取消后仍可考勤RED。
- 无allowedActions RED。
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

## B15-14 — Add / Drop / Withdraw 不同日期语义

**优先级：** `P1`  
**V1.5 裁决：** `VERIFY-FIRST/HARDEN`  
**外部成熟度信号：** Workday明确区分last add、drop without record、withdraw with grade。

### 1. 学校业务问题
- 开学后撤课可能必须保留W/撤课记录，不能都叫DROPPED。

### 2. 当前 exact-head 事实
- Selection已有drop/lock/归档；学期中withdraw生产语义需精审。

### 3. 历史设计 Reconciliation
- 历史退补选规则可复用，但不能凭旧设计改现状态枚举。

### 4. 唯一 Authority 决策
- 选课期Drop归Selection；教学开始后的Withdraw先明确是否属于课程修读/学籍记录变更。
- 日期由Term/Batch正式控制。

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
- LOCK后普通drop成功RED。
- 已有Grade后无审批withdraw成功RED。
- 截止边界时区错误RED。
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

## B15-15 — 人工 Override / Consent / 特殊资格

**优先级：** `P1`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** Workday明确提供registration restriction overrides，PeopleSoft也有受控override。

### 1. 学校业务问题
- 毕业年级、转专业等特殊学生可能需要例外。
- 直接改库或放宽全局规则不可接受。

### 2. 当前 exact-head 事实
- decision trace/audit/selection service已有基础；Control Plane统一权限。

### 3. 历史设计 Reconciliation
- 旧人工调整设计可重新归类为rule-scoped override。

### 4. 唯一 Authority 决策
- override只针对student+task+ruleCode+有效期，不改变全局policy。
- 正式SelectionRecord仍canonical。

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
- 无reason override RED。
- 过期仍生效RED。
- 学院越权全校override RED。
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

## B15-16 — 学生正式课表 = Published Schedule × TeachingRoster Membership

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-REWIRE`  
**外部成熟度信号：** 成熟SIS学生课表只应展示本人正式注册/名单内的已发布section。

### 1. 学校业务问题
- class_id+locked selection拼接不够覆盖合班、重修、MANUAL换版。

### 2. 当前 exact-head 事实
- TeachingRoster与ScopeHead已成熟；student schedule facade仍有兼容路径。

### 3. 历史设计 Reconciliation
- V1.3定义的最终Gold继续保持。

### 4. 唯一 Authority 决策
- Schedule决定何时何地；Roster决定学生是否属于该Task。
- 只做read projection，不建StudentSchedule truth。

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
- Roster外学生有正式课RED。
- Roster换版后仍显示旧课RED。
- 不同端source不一致RED。
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

## B15-17 — Course Component Cluster 原子选课

**优先级：** `P1`  
**V1.5 裁决：** `VERIFY-FIRST`  
**外部成熟度信号：** Workday/PeopleSoft对related components支持组合注册；理论+实验常需all-or-none。

### 1. 学校业务问题
- 学生不能只成功一半组件。
- 多个组件同时占容量和时间。

### 2. 当前 exact-head 事实
- 需要依赖A线linked components合同；当前Selection单Task路径强。

### 3. 历史设计 Reconciliation
- 旧同修/实验关联只作为候选。

### 4. 唯一 Authority 决策
- cluster动作是多条canonical Selection mutation的一个事务。
- 不新增第二Enrollment。

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
- 部分组件成功部分失败RED。
- 容量部分占用RED。
- 锁序不一致导致死锁RED。
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

## B15-18 — Selection 实时运行 / 高峰健康度

**优先级：** `P0`  
**V1.5 裁决：** `HISTORICAL-VALID / OPS-HARDEN`  
**外部成熟度信号：** 高峰选课成熟度取决于可观测和快速排障。

### 1. 学校业务问题
- 教务要区分满额、资格、冲突、系统锁等待和真实故障。

### 2. 当前 exact-head 事实
- 旧V2已设计QPS/失败规则/锁等待运行页；当前Outbox/ops metrics有基础。

### 3. 历史设计 Reconciliation
- 历史实时运行页HISTORICAL-VALID，但没有真实指标时禁止造图。

### 4. 唯一 Authority 决策
- metrics只是观测projection，不写Selection truth。
- traceId/业务码可下钻。

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
- 监控挂了却显示绿色RED。
- 1k burst指标与业务计数不符RED。
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

## B15-19 — LOCK 正式名单边界：未锁定不得进入考勤/考试/成绩

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN`  
**外部成熟度信号：** 国内学校规则强调正式选课后才获得上课/考试资格；本系统Roster架构正适合做强边界。

### 1. 学校业务问题
- LOCK必须成为下游正式名单的分水岭。
- 老师手工加学生不能获得正式成绩资格。

### 2. 当前 exact-head 事实
- Selection LOCK→SELECTION_LOCK Roster已存在；RosterConsumerSnapshot已接Attendance/Exam/Grade。

### 3. 历史设计 Reconciliation
- 旧V2‘等成员表上线’假设已OBSOLETE。

### 4. 唯一 Authority 决策
- LOCK事务核对records→生成RosterVersion→count/hash对账→正式锁定。
- 人工名单调整只能生成新RosterVersion。

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
- PENDING_LOTTERY/SELECTED未LOCK却能考勤RED。
- LOCK与drop并发错位RED。
- Roster count不等records RED。
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

## B15-20 — 多视角课表查询 / 打印统一

**优先级：** `P1`  
**V1.5 裁决：** `EXISTS-HARDEN`  
**外部成熟度信号：** 国内正方把班级/教师/教室/教学班课表查询打印作为正式排课交付。

### 1. 学校业务问题
- 不同视角不能各自写一套查询逻辑。
- 打印必须标正式版本。

### 2. 当前 exact-head 事实
- repo已有Class/Teacher/Student/Room等课表视图和四端页面。

### 3. 历史设计 Reconciliation
- 历史多视角页面树/打印模板可并入当前resolver。

### 4. 唯一 Authority 决策
- 统一Published Schedule resolver；学生视角额外joinRoster。
- 所有打印/export复用同一DTO。

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
- 同一Task在不同视图时间不同RED。
- 打印version缺失RED。
- 跨scope导出RED。
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

# Ⅷ. B 线页面级施工矩阵

## B-PAGE-01 — 排课Task-first工作台
- **页面唯一主任务**：围绕“排课Task-first工作台”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-02 — 排课XLSX导入
- **页面唯一主任务**：围绕“排课XLSX导入”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-03 — 课表发布与ScopeHead
- **页面唯一主任务**：围绕“课表发布与ScopeHead”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-04 — 课表版本历史
- **页面唯一主任务**：围绕“课表版本历史”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-05 — 选课批次总览
- **页面唯一主任务**：围绕“选课批次总览”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-06 — 选课批次详情
- **页面唯一主任务**：围绕“选课批次详情”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-07 — 课程供给与容量规则
- **页面唯一主任务**：围绕“课程供给与容量规则”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-08 — SelectionPreflight/排障
- **页面唯一主任务**：围绕“SelectionPreflight/排障”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-09 — 选课实时运行
- **页面唯一主任务**：围绕“选课实时运行”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-10 — 课程正式名单
- **页面唯一主任务**：围绕“课程正式名单”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-11 — 补选申请审批
- **页面唯一主任务**：围绕“补选申请审批”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-12 — Waitlist候补（VERIFY-FIRST）
- **页面唯一主任务**：围绕“Waitlist候补（VERIFY-FIRST）”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-13 — Saved Schedule（VERIFY-FIRST）
- **页面唯一主任务**：围绕“Saved Schedule（VERIFY-FIRST）”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-14 — 学生Selection
- **页面唯一主任务**：围绕“学生Selection”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-15 — TeachingRoster对账
- **页面唯一主任务**：围绕“TeachingRoster对账”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-16 — 学生正式课表来源诊断
- **页面唯一主任务**：围绕“学生正式课表来源诊断”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-17 — 必修班取消重新分配
- **页面唯一主任务**：围绕“必修班取消重新分配”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## B-PAGE-18 — 低人数选修取消与补改选
- **页面唯一主任务**：围绕“低人数选修取消与补改选”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。


# Ⅸ. B 线真实学校验收场景目录

每个场景施工时展开成 Given / When / Then，并绑定 exact SHA、角色、tenant、term、business IDs、API结果、必要MySQL/Playwright和对账查询。

## B-SC-001 — READY Task手工排课
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-002 — 非READY拒绝排课
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-003 — 同教师冲突
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-004 — 同班冲突
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-005 — 同教室冲突
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-006 — 单双周不冲突
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-007 — 教室容量不足
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-008 — 教室类型不符
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-009 — ScopeHead v1发布
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-010 — ScopeHead v2替换
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-011 — 旧batch不得成为当前
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-012 — 无term Selection批次
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-013 — 坏scope JSON
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-014 — SelectionCourse无task
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-015 — Selection冲突必须读current ScopeHead
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-016 — FCFS最后1名额100并发
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-017 — 同学生重复点击
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-018 — 学生PC与小程序同时提交
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-019 — OPEN/CLOSE与enroll并发
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-020 — Lottery双draw
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-021 — Lottery候选集合变化
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-022 — 按年级分六批开放
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-023 — 补选申请提交
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-024 — 补选审批通过
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-025 — 补选审批时容量已满
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-026 — 低人数选修取消
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-027 — COURSE_CANCELLED学生补选
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-028 — 必修班取消重新分配
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-029 — Waitlist加入
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-030 — Waitlist promotion
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-031 — Waitlist offer过期
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-032 — Lottery与Waitlist隔离
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-033 — Swap成功
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-034 — Swap目标满额整体回滚
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-035 — Saved Schedule保存不占容量
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-036 — Saved Schedule正式提交
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-037 — Reserve Capacity专业组
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-038 — Reserve释放到普通池
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-039 — Linked Component组合全选
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-040 — Linked Component部分失败整体回滚
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-041 — LOCK前考勤负向
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-042 — LOCK后Roster生成
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-043 — Roster hash/count reconciliation
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-044 — Selection-managed Roster防ADMIN覆盖
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-045 — 学生正式课表fixed course
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-046 — 学生正式课表selectable course
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-047 — 课表多视角一致
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-048 — 课表打印版本一致
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## B-SC-049 — Selection 1k burst运行监控
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


# B — Schedule/Selection：排课·正式课表·Selection·TeachingRoster — V1.4 四线并行唯一施工总册

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


# B — Schedule/Selection 主链施工总控

## B.1 责任边界

B 线负责：
- 05 排课 / Published Schedule Truth；
- 06 Selection 全生命周期；
- 07 TeachingRoster 汇流与对账。

B 是当前最重要的主链施工线。

B 不重新设计：
- Course/Program/TeachingTask；
- Attendance/Exam/Grade consumer；
- Graduation/Archive；
- Permission Catalog；
- 公共 Data Exchange framework。

## B.2 B 线最终交付 Contract

### B-C1 Published Schedule Contract
```text
termId + scope
activeBatchId
scopeHeadVersion
publishedAt
taskId-based items
occurrence coordinates
change history
```

### B-C2 Selection Student Projection
```text
batch
round
officialSchedule
eligibility
myRecord
allowedActions
blockers
scheduleConflict
windowStatus
```

四端禁止自行推断 canEnroll。

### B-C3 TeachingRoster Contract
```text
teachingClassId
taskId
classType
source
versionNo
memberCount
rosterHash
status
generatedAt
reason
```

下游 C 线只通过正式 RosterConsumer 协议消费名单。

## B.3 施工批次

### B0 — 等待/验证 A Contract Freeze
B 可以提前做：
- 现状审计；
- RED tests；
- UI wireframe/data contract；
- performance harness。

但在 A formation contract freeze 前，不自行定义 ADMIN_FIXED/SELECTABLE。

### B1 — Schedule PC Task-first
第一刀只动管理 PC 接线：
- 选择 READY TeachingTask；
- 从 Task 带 course/teacher/class/hours/weeks；
- 用户只编辑时间/教室；
- 不让 UI 自由拼 course + teacher + class。

后端 `schedule_final_service` 保持 KEEP。

### B2 — Schedule Import 统一到 Academic File Exchange
淘汰新业务主路径中的文本 CSV 旁路。

生产模板：
- `教学任务ID` canonical 必填；
- weekday/slot/startWeek/endWeek/parity/classroom；
- courseName/teacherName 只做显示/兼容。

流程：
`upload → scan → dry-run → errors → confirm → reread`。

ATOMIC 默认；PARTIAL 必须明确风险与结果。

### B3 — Published Schedule Truth / ScopeHead
所有正式读取逐步统一：
`ScopeHead.active_batch_id → published batch/items`。

必须验证：
- old EFFECTIVE item 不再冒充当前正式课表；
- publish 并发；
- version replacement；
- 学生/教师 PC/小程序一致；
- schedule change 后旧版本可追溯。

### B4 — Selection Schema / Runtime Preflight 第一层
先不要直接把 nullable 字段硬改 NOT NULL。

先做：
- dirty-data inventory；
- runtime PUBLISH/OPEN/LOCK fail-closed；
- termId 必须；
- TeachingTask 必须；
- same-term/status/type；
- scope/rule JSON corruption fail-closed；
- official schedule readiness。

旧脏数据先 reconciliation/backfill；schema tighten 若必要，提交 INT migration 请求。

### B5 — SelectionPreflight
建立纯 preflight，复用到：
- PUBLISH；
- OPEN；
- CLOSE；
- LOCK。

检查：
- term；
- window；
- scope；
- task；
- schedule truth；
- capacity/min；
- prerequisites；
- credit limits；
- repeat/pass rule；
- low-enrollment policy；
- FCFS/LOTTERY config。

返回可解释 blockers/allowedActions。

### B6 — 事务与锁正确性
修：
- `_record_conflict_reject` 验证中 commit；
- schedule conflict 读取当前 ScopeHead；
- scope/rule 损坏 fail-open；
- 状态推进锁顺序。

保持已有：
- deterministic SHA-256 lottery；
- atomic capacity；
- CLOSED→DRAWN claim；
- LOCK→Roster。

### B7 — 学生 Projection + 四端 UI
Student PC / miniapp 统一状态：
- PENDING_LOTTERY；
- SELECTED；
- LOCKED；
- DROPPED；
- LOTTERY_LOST；
- COURSE_CANCELLED。

全部按钮由后端 `allowedActions` 驱动。

必须移除：
- 本地 capacity/status 推 canEnroll；
- windowStart/startAt 等多套 fallback；
- `mySelected()` 只认 SELECTED 的错误语义。

### B8 — LOCK → TeachingRoster 汇流
证明两条链：

```text
ADMIN_FIXED → ADMIN_CLASS Roster
SELECTABLE → Selection → LOCK → SELECTION_LOCK Roster
```

两者进入同一：
- Attendance；
- Exam；
- Grade consumer protocol。

禁止 Selection-managed roster 被 ADMIN_CLASS refresh 覆盖。

### B9 — Roster Reconciliation
新增学期级检查：
`Task ↔ TeachingClass ↔ current RosterVersion ↔ memberCount/hash ↔ downstream snapshot`

要求：
- 0 orphan TeachingClass；
- 0 hash/count mismatch；
- 0 stale managed roster；
- 历史 version 可重放。

### B10 — Real MySQL Concurrency
Selection 必测：
- 最后一个名额 100+ 并发；
- 同学生多端重复提交；
- OPEN/CLOSE vs enroll；
- LOCK vs drop/reselect；
- LOTTERY retry；
- 1k 级突发流量。

Schedule 必测：
- ScopeHead 并发 publish；
- 同教师/班级/教室资源冲突；
- import confirm concurrency。

### B11 — B-line Gold / Contract Freeze
同一学期：
1. fixed course；
2. selectable course。

断言：
- fixed 永不进入选课列表；
- selectable LOCK 前不能成为考勤/考试/成绩正式名单；
- LOCK 后 roster source 正确；
- PC/miniapp 状态一致；
- Published Schedule × Roster membership 解释正确。

冻结 B-C1~B-C3，交接 C。

## B.4 B 线禁止事项
- 不重写 Schedule backend；
- 不重新设计 Lottery；
- 不另建 Selection roster 表；
- 不直接把 nullable 字段改 NOT NULL 而不先 dirty-data reconciliation；
- 不直接改 shared Data Exchange/Alembic/Permission files；
- 不让客户端决定资格；
- 不用旧 EFFECTIVE items 代替 ScopeHead 正式课表。

## B.5 B → C 交接包
- Published Schedule exact contract；
- TeachingRoster exact contract；
- Roster readiness states；
- Selection LOCK semantics；
- consumer snapshot regression；
- MySQL concurrency report；
- exact HEAD。


---

# 原 V1.3 详细施工内容完整整编：本线专项详细施工原文


---

## 来源文档：`05_排课与正式课表_真实学校交付施工文档_V1.3.md`

# 05 — 排课 Scheduling + 正式课表 Authority：现有代码逐行审计 + 真实学校交付校正版 V1.3

> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 1. 当前成熟度

**后端 🟢；管理 PC 🟠**

当前 Authority：`READY TeachingTask → ScheduleItem → Publish Gate → ScheduleScopeHead(active_batch_id) → Published Schedule Truth`

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
| AaScheduleBatch / AaScheduleItem | [KEEP] | 排课批次与课表事实 |
| AaScheduleScopeHead | [KEEP] | `term + scope` 唯一正式 head；active_batch_id/version/publishedAt 是正式课表真值 |
| AaSchedulePublish / AaScheduleChange | [KEEP] | 发布证据与发布后合法变更链 |

## 4. Router / Service / Guard 审计

| 文件 | 标记 | 逐函数/关键分支结论 |
|---|---|---|
| backend/app/modules/academic_affairs/services/academic_affairs_schedule_final_service.py | [KEEP] | 已经 Task-first；校验 READY、同学期、周次、教室容量/类型、周学时、冲突 |
| backend/app/modules/academic_affairs/services/academic_affairs_schedule_gate_service.py | [KEEP] | 发布前检查漏排/超排/orphan/坐标/硬冲突 |
| backend/app/modules/academic_affairs/services/academic_affairs_schedule_facade.py | [COMPAT] | 学生课表仍用行政班 + LOCKED选课合并，先保留 |

## 5. 四端前端审计

| 页面/客户端 | 标记 | 当前情况 |
|---|---|---|
| frontend/src/modules/academicAffairs/views/AaScheduleMaintainView.vue | [REWIRE] | 当前仍自由选择课程+教师+班级，未把 TeachingTask 作为必选身份 |
| frontend/src/modules/academicAffairs/views/AaClassScheduleView.vue | [KEEP] | 只读班级课表 |
| frontend/src/modules/academicAffairs/views/AaTeacherScheduleView.vue | [KEEP] | 教师课表 |
| student-portal/src/views/academic/StudentScheduleView.vue | [KEEP/HARDEN] | 页面成熟；后端来源需要逐步从 class_id 旁路收敛到 Roster membership |
| miniapp/src/pages/student/academic-affairs/schedule.vue | [KEEP/HARDEN] | 同上 |
| miniapp/src/pages/teacher/my-schedule/index.vue | [KEEP] | 教师正式课表 |

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

- **[BLOCKER]** 管理 PC 排课必须改成 TeachingTask-first，否则用户仍可通过旧 UI 依赖兼容解析，长期可能生成身份不完整课表项。
- **[BLOCKER]** 批量导入当前以课程名/教师名文本为身份，且把 teacherName 当 teacherKey，不能作为生产级批量排课入口。

## 7. HARDEN / REWIRE 清单

- 学生正式课表最终目标 = Published Schedule × current TeachingRoster membership；当前 `student.class_id` 旁路仅作兼容。
- 导入改为 xlsx + stable taskId + 预检/错误行/确认，不直接文本落库。
- 前端不要默认 1-18 周；必须从 Task/Term 带出。

## 8. 最小安全施工方式

**不重写排课后端**。第一刀只改 `AaScheduleMaintainView` 发送 taskId；用现有 backend gate 兜底。

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

## 真实学校增强：排课与正式课表

### 关键校正：不要新造排课导入

当前 main 已有 `Academic File Exchange` 的排课 XLSX ImportJob，且最终 Schedule Service 已做到：
- 优先 `taskId`；
- READY + 同学期校验；
- 教学周/节次校验；
- 教室类型/容量；
- 周学时；
- 冲突；
- dry-run 与 confirm 复用同一 canonical `_apply_import_rows`；
- ATOMIC/PARTIAL 两种导入语义。

因此 V1.3 的任务是：
1. 管理 PC `AaScheduleMaintainView` 改为 **READY TeachingTask-first**；
2. UI 的“批量导入”接现有 File Exchange，不再维护文本 CSV 旁路；
3. 新的生产模板把 `教学任务ID` 设为 canonical 必填；现有“课程名 + 教师工号/班级唯一匹配”只标 `[COMPAT]`；
4. 再补跨学期/跨学院错绑定、并发 confirm、rollback、错误 XLSX、超大文件等学校规模测试。

### [SCALE-BLOCKER] 排课大导入

必须用真实 MySQL + 文件解析跑：
- 1 万行 Task-first schedule XLSX；
- 错误率 5% 的 dry-run；
- ATOMIC confirm 全成全败；
- PARTIAL confirm 正确接受合法行并输出逐行错误；
- classroom/teacher/class 冲突保持稳定 businessCode。

---


---

## 来源文档：`06_Selection与正式名单_真实学校交付施工文档_V1.3.md`

# 06 — Selection + Lottery + TeachingRoster 汇流：现有代码逐行审计 + 真实学校交付校正版 V1.3

> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 1. 当前成熟度

**整体 🟠；并发基座强，但正式可用还有 P0。**

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
| AaSelectionBatch / Course / Round / Record | [KEEP/HARDEN] | 选课批次、供给、轮次、学生记录已存在 |
| AaTeachingClass / RosterVersion / Member | [KEEP] | 统一正式名单结构已经成熟 |

## 4. Router / Service / Guard 审计

| 文件 | 标记 | 逐函数/关键分支结论 |
|---|---|---|
| backend/app/modules/academic_affairs/services/academic_affairs_selection_final_service.py | [KEEP/HARDEN] | FCFS 行锁、cap 原子更新、LOCK→TeachingRoster 已存在 |
| backend/app/modules/academic_affairs/services/academic_affairs_selection_round_service.py | [KEEP] | Lottery 用 SHA-256 确定性排序；CLOSED→DRAWN 行锁 claim |
| backend/app/modules/academic_affairs/services/academic_affairs_selection_service.py | [BLOCKER] | validator 内部存在 conflict reject commit；schedule conflict 仍读旧 EFFECTIVE items；坏 JSON 有 fail-open 风险 |
| backend/app/modules/academic_affairs/services/academic_affairs_teaching_roster_service.py | [KEEP] | Selection 存在时未 LOCK 就 fail-closed，不回退行政班 |

## 5. 四端前端审计

| 页面/客户端 | 标记 | 当前情况 |
|---|---|---|
| frontend/src/modules/academicAffairs/views/AaSelectionConsoleView.vue | [HARDEN] | 新建批次字段偏少，TeachingTask 仍显示“选填” |
| frontend/src/modules/academicAffairs/views/AaSelectionStudentView.vue | [BLOCKER] | 只识别 SELECTED/LOCKED/DROPPED/COURSE_CANCELLED；不识别 PENDING_LOTTERY/LOTTERY_LOST；按钮在前端自行判断 |
| student-portal/src/views/academic/StudentCourseSelectionView.vue | [HARDEN] | 学生端合同需要与管理 PC 对齐 |
| miniapp 学生选课 | [HARDEN] | 必须与 PC 共用后端 allowedActions |

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

1. `termId`、selection window、scope、TeachingTask 必须成为正式合同。
2. JSON 配置损坏不得 fail-open。
3. schedule conflict 必须读 current ScopeHead，不得扫旧 EFFECTIVE items。
4. validator 不得 commit。
5. 学生端必须消费后端 state machine + allowedActions；补齐 Lottery 状态。
6. 20K 学生规模分页、锁批次效率、数据范围必须验证。

## 7. HARDEN / REWIRE 清单

- 先做 dirty-data inventory，再决定 NOT NULL / 索引收紧；不要直接 schema 变更把历史数据炸掉。
- Lottery 保持现有确定性设计，不重写“随机算法”。
- FCFS cap 更新保持原子 SQL；补充 100+ 并发超卖测试。
- Selection LOCK 后生成 `SELECTION_LOCK` Roster，Roster count/hash 必须与 Selection records 对账。

## 8. 最小安全施工方式

优先建立 `SelectionPreflight` 与 Student Projection，修事务边界，再收紧 schema。

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

## 真实学校增强：Selection 与正式名单

当前 final service 已具备很强的并发基座：
- FCFS 行锁 + 原子容量；
- Lottery CLOSED→DRAWN 行锁 claim + SHA-256 确定性顺序；
- LOCK → TeachingRoster；
- pending Selection 时 TeachingRoster fail-closed。

真实学校还必须补：
1. `SelectionPreflight` 在 PUBLISH/OPEN/LOCK 三阶段统一复用；
2. 先做 dirty-data inventory，再决定 NOT NULL / index tighten；
3. Student Projection 输出 `status/allowedActions/blockers/officialSchedule/window/round`；
4. 学生 PC/小程序不再自己算 `canEnroll`；
5. 20K 学生规模锁名单/名单生成/Projection 分页；
6. 学院教务员的数据范围不得先查全校再 Python 过滤。

### [SCALE-BLOCKER] Selection 真实 MySQL 并发协议

- FCFS 最后一席 100+ 并发；
- 同一学生 PC + miniapp 同时提交；
- OPEN/CLOSE 与 enroll 并发；
- LOCK 与 drop/reselect 并发；
- Lottery 重复 draw / worker retry；
- Roster 生成与 lock 失败 rollback；
- 目标容量 200、申请 1k 的 burst 验证。

验收不仅看 HTTP 200，而要对账：
`SelectionRecord count / selectedCount / capacity / Roster memberCount / rosterHash`。

---


---

## 来源文档：`07_TeachingClass与TeachingRoster_真实学校交付施工文档_V1.3.md`

# 07 — TeachingClass / TeachingRoster 汇流：现有代码逐行审计 + 真实学校交付校正版 V1.3

> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 1. 当前成熟度

**后端 🟢。这是当前最成熟的底座之一。**

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
| AaTeachingClass | [KEEP] | taskId 稳定关联；classType/formationMode 支持 ADMIN_FIXED / SELECTION / MANUAL / RETAKE 等场景 |
| AaTeachingRosterVersion / Member | [KEEP] | current head + version history + rosterHash + sourceType；同一 TeachingClass 只有一版 current |

## 4. Router / Service / Guard 审计

| 文件 | 标记 | 逐函数/关键分支结论 |
|---|---|---|
| backend/app/modules/academic_affairs/services/academic_affairs_teaching_roster_core_service.py | [KEEP] | ensure class、set roster、version/hash、Selection-managed 防覆盖 |
| backend/app/modules/academic_affairs/services/academic_affairs_teaching_roster_service.py | [KEEP] | resolver 对 Selection 未 LOCK fail-closed；ADMIN_CLASS 只在无 Selection 关系时使用 |
| Attendance/Exam/Grade consumer services | [KEEP] | 已通过 RosterConsumerSnapshot 读取正式名单 |

## 5. 四端前端审计

| 页面/客户端 | 标记 | 当前情况 |
|---|---|---|
| AaTeachingTaskDetailView | [KEEP/HARDEN] | 可显示任务/名单摘要；建议增加 rosterSource/version/hash/updatedAt |
| 教师成绩/考勤页 | [KEEP] | 下游应只认 RosterConsumerSnapshot |
| 学生端 | [KEEP/HARDEN] | 正式课表、考试资格、成绩资格最终都应以 current roster membership 解释 |

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

**当前没有新的数据结构级 BLOCKER。**  
真正需要的是保护它不被其他模块绕开：
- Attendance 不得从行政班直接猜名单；
- Exam 不得自己查 SelectionRecord；
- Grade 不得按课程名+学生号猜修读关系；
- 学生课表不得永远依赖 student.class_id。

## 7. HARDEN / REWIRE 清单

- TeachingRoster 管理/诊断页面要清楚显示 source/version/hash/当前状态。
- MANUAL 调整需要 before/after/reason/expectedVersion。
- Selection LOCK / Retake / Manual refresh 后，下游 snapshot 必须读 current version。

## 8. 最小安全施工方式

**不要再建新 roster 模型。**  
只补 read projection、版本并发、人工调整审计、下游回归。

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

## 真实学校增强：TeachingRoster Authority 守卫

这是当前最成熟的底座之一，V1.3 的任务不是新造表，而是把它变成所有下游都无法绕过的协议。

新增学期级 reconciliation：
`TeachingTask → TeachingClass → current RosterVersion → member count/hash → Attendance/Exam/Grade snapshot`

必须做到：
- 0 个 ACTIVE TeachingTask 没有合法 class/roster readiness；
- 0 个 current RosterVersion hash/count 不一致；
- 0 个 Selection-managed Roster 被 ADMIN_CLASS refresh 覆盖；
- MANUAL/RETAKE refresh 保留 version history；
- 任意学生正式课表、考试、成绩资格能追溯到 current roster membership。

---


# 00D. 线内 API Contract：允许 B 内部直接耦合，禁止向外泄漏内部模型

> 本节是 V1.3 深度补强稿在四线并行模式下的强制 Contract。  
> B 线内部服务可以直接依赖同线内部 DTO/模型；但 A/C/D/INT 只能消费以下发布 Contract，不得直接查 B 内部表来“顺手得到结果”。

## B-API-01 — PublishedScheduleDTO

发布给：C/D/学生课表消费者。

最小字段：

```json
{
  "termId": 1,
  "scopeKey": "SCHOOL|COLLEGE:10|CLASS:20",
  "activeBatchId": 100,
  "scopeHeadVersion": 3,
  "publishedAt": "2026-09-01T08:00:00+08:00",
  "items": [
    {
      "taskId": 2001,
      "weekday": 1,
      "slotId": "0102",
      "startWeek": 1,
      "endWeek": 16,
      "parity": "ALL",
      "classroomId": 301,
      "teacherIds": [501],
      "classIds": [601]
    }
  ]
}
```

硬门：
- C 线考勤/考试冲突只认此 DTO 或同义 public service；
- D 线只读历史/Archive snapshot；
- 禁止任何线直接拿 `AaScheduleItem.status == EFFECTIVE` 代替 current ScopeHead。

## B-API-02 — SelectionStudentProjectionDTO

发布给：学生 PC / 小程序 / 管理 PC 排障。

最小字段：

```json
{
  "batchId": 11,
  "roundId": 21,
  "termId": 1,
  "window": {"open": true, "startAt": "...", "endAt": "..."},
  "course": {
    "selectionCourseId": 31,
    "taskId": 41,
    "courseId": 51,
    "status": "OPEN",
    "capacity": 80,
    "selectedCount": 76
  },
  "eligibility": {
    "eligible": false,
    "businessCode": "PREREQUISITE_NOT_MET",
    "blockers": ["PREREQUISITE_NOT_MET"],
    "howToResolve": "完成先修或提交允许的人工 override"
  },
  "myRecord": {
    "status": "PENDING_LOTTERY",
    "recordId": 61
  },
  "allowedActions": ["VIEW", "DROP_PENDING_LOTTERY"],
  "officialSchedule": {
    "scopeHeadVersion": 3,
    "conflict": false
  }
}
```

硬门：
- 学生客户端不得用 `selectedCount < capacity` 自己推 `canEnroll`；
- 不得用本地时间自行决定 OPEN/CLOSED；
- `PENDING_LOTTERY / LOTTERY_LOST / COURSE_CANCELLED / LOCKED` 语义必须后端统一。

## B-API-03 — TeachingRosterDTO

发布给：C 线 Attendance / Exam / Grade 和 D 线 Archive。

最小字段：

```json
{
  "teachingClassId": 701,
  "taskId": 41,
  "termId": 1,
  "classType": "SELECTION",
  "sourceType": "SELECTION_LOCK",
  "versionNo": 4,
  "status": "LOCKED",
  "memberCount": 78,
  "rosterHash": "sha256:...",
  "generatedAt": "...",
  "reason": "SELECTION_LOCK",
  "members": [
    {"studentId": 9001, "studentNo": "20260001"}
  ]
}
```

硬门：
- C 线不能直接读 `AaSelectionRecord` 判断谁能考勤/考试/录成绩；
- D 线 Archive 必须保留 rosterVersion + hash；
- B 内部更换 current version 后，消费者下次读取必须自动命中新 current。

## B-API-04 — SelectionPreflightDTO

发布给：B 内 PUBLISH/OPEN/CLOSE/LOCK + 管理排障页。

```json
{
  "ready": false,
  "stage": "OPEN",
  "blockers": [
    {
      "code": "SCHEDULE_NOT_PUBLISHED",
      "message": "正式课表尚未发布",
      "ownerRole": "ACADEMIC_ADMIN",
      "howToResolve": "先发布当前学期正式课表"
    }
  ],
  "checkedAt": "...",
  "evidence": {"termId": 1, "scopeHeadVersion": 0}
}
```

要求：
- 纯读，禁止 `commit()`；
- PUBLISH/OPEN/CLOSE/LOCK 调用同一个 evaluator；
- `unknown / corrupted / service unavailable` 一律 fail-closed，不能变 `ready=true`。


# 00E. 线内 Frontend Page / Action Matrix

> 四端：管理/教师 PC、学生 PC、教师小程序、学生小程序。  
> B 线是学生选课 UX 与正式名单 Authority 的 Owner。

| 页面 | 角色 | 主任务 | 核心读 Contract | 正式写动作 | 必要状态 | Empty/Error/Blocked |
|---|---|---|---|---|---|---|
| 排课工作台 | 教务处/学院教务 | READY Task-first 排课 | A TeachingTask Contract + B Schedule Draft | create/update item | DRAFT/PUBLISHED | 无READY Task时引导回教学任务 |
| 排课导入 | 教务处/学院教务 | XLSX dry-run/confirm | Academic File Exchange | confirm job | READY/FAILED/CONFIRMED | 文件错误下载错误行 |
| 课表发布 | 教务处 | 发布ScopeHead | B PublishedScheduleDTO | publish | DRAFT/PUBLISHED/SUPERSEDED | 冲突/漏排下钻 |
| 选课批次 | 教务处 | 配置Batch/Round/Scope | B PreflightDTO | create/publish/open/close/lock | DRAFT/PUBLISHED/OPEN/CLOSED/LOCKED | blocker列表 |
| 选课课程供给 | 教务处/学院教务 | Task供给/容量/算法 | A Task + B course policy | add/update | DRAFT/OPEN/CANCELLED | 缺Task/跨学期/坏policy阻断 |
| 选课排障 | 教务处/学院教务 | 学生为什么不能选 | SelectionStudentProjectionDTO | override（若已验真） | any | 原因/证据/责任人 |
| 学生选课 | 学生PC/小程序 | 选课/退课/查看结果 | SelectionStudentProjectionDTO | enroll/drop | OPEN/PENDING/SELECTED/LOCKED/LOST/CANCELLED | 中文原因 + 下一步 |
| Lottery结果 | 学生/教务 | 查看抽签结果 | Lottery evidence | 无/受控admin action | DRAWN | candidateHash/resultHash |
| 补选审批 | 学生/学院/教务 | 正式选课后的审批式补选 | Existing add-selection projection | submit/approve/reject | PENDING/APPROVED/REJECTED | 审批时重新preflight |
| 正式名单 | 教师/教务 | 查看当前RosterVersion | TeachingRosterDTO | MANUAL refresh（受控） | LOCKED/SUPERSEDED | source/version/hash清晰 |
| 学生正式课表 | 学生PC/小程序 | 查看我真实上的课 | PublishedScheduleDTO × TeachingRoster | 无 | PUBLISHED | 非member不显示 |

## 按钮级强门

### 排课页
- “新增排课”：只有 READY Task；禁止自由拼课程+教师+班级。
- “批量导入”：进入 File Exchange，不再走文本 CSV 旁路。
- “发布”：先 Preflight；blocker=0 才允许。

### 学生选课页
- “选课”：只在后端 `allowedActions` 含 ENROLL 时显示。
- “退课”：只在 allowedActions 含 DROP 时显示。
- “换课”：若启用 B15-09，只能调用 atomic swap；禁止 UI 先 drop 再 enroll。
- “候补”：只有学校启用 Waitlist 且 algorithm=FCFS 时显示；Lottery 落签不自动显示候补。
- “补选申请”：仅正式选课结束后的学校政策窗口显示。

### 正式名单页
- “人工调整”：先 preview diff；Selection-managed class 默认禁止直接覆盖。
- “导出名单”：带 roster version/hash/generatedAt。


# 00F. 线内 Import / Export / Audit Contract

## Schedule Import
- 唯一通道：Academic File Exchange。
- 模板：taskId canonical；weekday/slot/weeks/parity/classroom。
- 禁止 teacherName 作为 teacherKey。
- confirm 前同一 canonical schedule evaluator。

## Selection / Roster Bulk Operations
- 若需批量加供给/名单调整，先判断是否能表达为现有 Batch/Task/Roster API；不能就提交新 schema 七问。
- 禁止 CSV 直接写 SelectionRecord / RosterMember。

## Export
正式文件至少带：
- school/term/batch/round；
- generatedAt/operator；
- dataScope；
- scheduleVersion 或 rosterVersion/hash；
- watermark（涉学生名单时）。

## Audit
高风险动作：
- Schedule publish/change；
- Selection publish/open/close/lock/draw；
- capacity change；
- override；
- course cancel；
- manual roster refresh。

必须记录：
`operator + reason + before + after + businessRef + version/hash + traceId`。


# 00G. 线内 Test / MySQL / Gold Matrix

## 必跑 targeted
- schedule final/gate/truth tests；
- selection final/round/eligibility tests；
- TeachingRoster core/service tests；
- RosterConsumerSnapshot regressions。

## 必跑 MySQL concurrency
1. ScopeHead 双 publish；
2. FCFS 最后一席 100+并发；
3. 同学生 PC+miniapp 重复提交；
4. OPEN/CLOSE vs enroll；
5. LOCK vs drop/reselect；
6. Lottery 重复 draw；
7. LOCK→Roster rollback/retry；
8. 1k burst selectedCount/capacity/memberCount/hash 对账。

## 必跑四端 E2E
- 管理 PC：Task-first排课→发布→选课批次→LOCK→名单；
- 学生 PC：OPEN→选课→PENDING/SELECTED/LOST/CANCELLED；
- 学生 miniapp：与 PC 同语义；
- 教师 PC/miniapp：LOCK后正式名单/课表一致。

## B 线 Gold

```text
PublishedScheduleDTO current head = DB ScopeHead current head
Selection selectedCount <= capacity
LOCKED Selection count = TeachingRoster memberCount
TeachingRoster hash = recompute(member IDs)
Student official schedule = Published Schedule ∩ current TeachingRoster membership
0 stale managed roster
0 client-side authoritative eligibility
```

B freeze 后，C 线才可把正式名单当稳定依赖。


---

# V1.2 详细任务附录

> 本节保留 V1.2 详细任务，补充为**学校真实施工粒度**，施工 AI 不得只完成上文摘要后停止。

---

## 来源：`05_排课与正式课表_全量真实化施工文档.md`

### BLOCKER / REWIRE 列表
- **[REWIRE]** 管理端 `AaScheduleMaintainView.vue` 改为 TeachingTask-first。
- **[HARDEN]** 批量导入改为 `taskId + weekday + slot + weeks + parity + classroomId` 的 XLSX 模板；课程名/教师名只做 snapshot/display。
- **[HARDEN]** 学生/教师课表所有正式读取必须经 `ScopeHead.active_batch_id`，旧 `EFFECTIVE` item 只能做显式 COMPAT。
- **[HARDEN]** 学生正式课表最终从 `Published Schedule × TeachingRoster membership` 推导。
- **[HARDEN]** 所有 publish / change 使用 expectedVersion / scope version guard。

### 服务施工卡
1. **ScheduleCurrentTruth**：输入 `termId + scope`，只返回 current published batch/items；无 head 必须 `NOT_READY`，不能回退最新 batch 猜测。
2. **ScheduleDraftWriter**：只接受 TeachingTask identity；UI 传 courseName/teacherName/classId 不能决定正式身份。
3. **SchedulePublishPreflight**：漏排、超排、周次、教室类型/容量、教师/班级/教室冲突、任务周学时一次返回 blocker 列表。
4. **SchedulePublishCommand**：lock ScopeHead→校验 expectedVersion→publish batch→supersede old→increment head version→审计。
5. **ScheduleChangeCommand**：发布后变更必须写 `AaScheduleChange` 或现有 change fact，保留 before/after/reason，不直接覆盖历史。
6. **StudentScheduleProjection**：只读服务，不新表；fixed + selectable 都通过 current Roster membership 解释。

### API/DTO 强门
- `GET /schedule/current?termId=&scope=`：返回 `activeBatchId/version/publishedAt/items`。
- `POST /schedule/items`：正式 payload 必须 `taskId`。
- `POST /schedule/publish`：必须 `expectedVersion`；409 返回 currentVersion。
- `POST /schedule/import/dry-run`：错误行 xlsx；不能只回字符串数组。
- `POST /schedule/import/confirm`：需要 idempotency key / jobId；重复确认不得重复建 item。

### UI 施工卡
- 排课页首屏：Term → Task completeness → draft conflict count → current published version → 下一动作。
- 新增排课 Dialog：选 TeachingTask；Course/Teacher/Class 全只读；用户只填 weekday/slot/weeks/parity/classroom。
- 冲突 UI：教师/班级/教室/周次/任务周学时分别有中文原因和下钻对象。
- 发布确认：显示本次 batch item count、受影响教师/班级/教室、将 supersede 的旧版本。
- 学生课表：显示数据来源 `正式课表 vN`；发生已发布调课时显示“已更新”而不是静默变化。

### 并发 / MySQL
- 同 scope 两个 publish：只能一个拿到新 version；另一个 409 stale。
- 同一教师/班级/教室 overlap：并发创建不能绕过冲突。
- Import confirm 与人工编辑同时发生：按固定锁顺序，不产生 duplicate item。

### Dirty-data / migration
- 统计所有 `schedule_item.task_id is null` / orphan task / old EFFECTIVE 无 head 行。
- 先 backfill/标记 COMPAT，不先加 NOT NULL。
- 证明 COMPAT 调用量归零后，才交 INT 做 schema tighten。

---

## 来源：`06_Selection与正式名单_全量真实化施工文档.md`

### BLOCKER 列表
1. SelectionBatch publish/open 前必须 `termId + valid window + non-empty scope + frozen rules`。
2. SelectionCourse 正式供给必须 `teachingTaskId`；无 Task 的历史数据只 COMPAT，不能新建。
3. `apply_scope_json / prerequisite_codes_json / rule_json` 解析失败全部 BLOCKED；绝不默认 `{}` / `[]`。
4. prereq/repeat 只读 EffectiveGrade Provider，不读旧 `AcademicGrade.course_name`。
5. schedule conflict 只读 PublishedSchedule Contract / ScopeHead current batch。
6. `_validate_enroll` / Preflight 纯读，不 commit。
7. 拒绝审计只在最外层 command 统一写一次；不得 validator + final service 双写。
8. 学生投影必须覆盖 FCFS / LOTTERY / CANCELLED / RESELECT / LOCKED 全状态。

### SelectionPreflightDTO
```json
{
  "ready": false,
  "stage": "OPEN",
  "blockers": [
    {
      "code": "COURSE_TASK_MISSING",
      "message": "可选课程未绑定正式教学任务",
      "ownerRole": "ACADEMIC_ADMIN",
      "howToResolve": "返回选课课程供给绑定 READY TeachingTask"
    }
  ],
  "ruleVersion": 3,
  "publishedRuleHash": "sha256:...",
  "checkedAt": "..."
}
```

### Eligibility DTO
```json
{
  "eligible": false,
  "codes": ["PREREQUISITE_NOT_MET", "SCHEDULE_CONFLICT"],
  "evidence": {
    "effectiveGradeAttempts": [],
    "scopeHeadVersion": 4,
    "conflictTaskIds": [101]
  },
  "allowedActions": ["VIEW"]
}
```

### FCFS command
固定顺序：
`lock batch/course/student active records → re-evaluate window/scope/grade/schedule → conditional capacity update → create record → outer audit → commit`。

### Lottery command
固定顺序：
`lock round → freeze candidate set/hash → deterministic ordering → conditional capacity claim → update records → resultHash/algorithmVersion → commit → outbox notify`。

### LOCK command
固定顺序：
`lock batch → preflight → freeze course list → lock active records → set final statuses → generate/update TeachingRosterVersion → count/hash reconciliation → batch LOCKED → commit`。

### Student Projection DTO
```json
{
  "status": "PENDING_LOTTERY",
  "statusLabel": "待抽签",
  "phase": "LOTTERY_PENDING",
  "allowedActions": ["VIEW", "DROP"],
  "reason": "已进入抽签候选，尚未生成结果",
  "howToResolve": "等待抽签结果",
  "window": {"startAt": "...", "endAt": "...", "open": false},
  "lottery": {"roundId": 1, "drawn": false},
  "reselect": null
}
```

### PC / miniapp 一致性
- 任何端不得本地用 status 判断 allowedActions。
- `PENDING_LOTTERY` 不显示“选课”；`LOTTERY_LOST` 不显示“退课”；`COURSE_CANCELLED` 优先显示补改选入口；`LOCKED` 只读。
- 后端 DTO 改动时 PC + miniapp 同 PR 更新 contract tests。

### 高峰 Gold
- 200 capacity / 1000 concurrent FCFS：最终 selected = 200，0 duplicate，0 negative capacity。
- 同学生多端重复提交：1 个 active record，其他返回 idem/already selected。
- Lottery 双 worker：1 次 draw manifest，结果完全相同或第二个稳定返回 already drawn。
- LOCK/drop race：最终要么 record dropped 且 roster无该生，要么 LOCKED 且 drop rejected；禁止状态/名单分裂。

---

## 来源：`07_TeachingClass与TeachingRoster_全量真实化施工文档.md`

### KEEP
- 现有 `AaTeachingClass / RosterVersion / Member` 保持唯一正式名单 Authority。
- `ensure_teaching_class_for_task / set_roster / resolve_teaching_task_roster` 保持 canonical。
- Selection 存在时 resolver 未 LOCK 必须 fail-closed。

### HARDEN
- 每次 `set_roster` 固定锁序：TeachingClass current row → current RosterVersion → member diff。
- `expectedVersion` stale 返回 409；不覆盖。
- `rosterHash = sha256(sorted stable studentIds))`；hash算法版本需冻结。
- sourceType 只允许现有 canonical values；禁止 UI 自定义来源字符串。
- MANUAL 调整必须 reason、operator、beforeHash/afterHash。

### Reconciliation API
`GET /teaching-rosters/reconcile?termId=` 返回：
```json
{
  "taskCount": 1000,
  "teachingClassCount": 1000,
  "currentRosterCount": 1000,
  "orphanTaskIds": [],
  "orphanClassIds": [],
  "countMismatch": [],
  "hashMismatch": [],
  "staleManagedRoster": []
}
```

### 下游 consumer hard gate
- Attendance：session/member snapshot source = roster version。
- Exam：assignment/seat candidate source = roster version。
- Grade：grade entry candidate source = roster version。
- Student schedule：member check = roster version。

任何 consumer 直接查行政班/SelectionRecord 猜名单，增加 structural RED test。

### Roster 20K scale
- 单 task 20K roster refresh：批量 delete/insert/upsert；禁止 O(N) commit。
- 学期 1000 task reconciliation：禁止 per-task N+1 全量 member scan；先 batch aggregate count/hash。
- export 20K roster xlsx 走后台任务/stream；不在 request thread 大内存 materialize。


---

# V1.1 风险卡附录

> 本节保留 V1.1 跨模块风险卡，作为施工 AI 的额外 RED 输入；V1.2 已将其中结论吸收到主方案。

---

## 来源：`05_排课_风险卡.md`

### 风险卡 05-01：旧 UI 能否绕过 Task-first
- 旧 PC 仍自由选 Course / Teacher / Class；最终 service 存在名称 fallback。
- **RED**：新业务请求缺 taskId；同名课程/教师歧义；跨学期错绑。
- **PASS**：PC 强制 taskId；后端仅保留受控 COMPAT，并有 usage metric。

### 风险卡 05-02：导入是否重新造引擎
- 当前已有 Academic File Exchange + schedule xlsx parser + confirm。
- **RED**：页面维护第二 CSV parser / UploadJob。
- **PASS**：UI 跳/接统一 File Exchange；template/taskId canonical。

### 风险卡 05-03：旧 EFFECTIVE 是否还能冒充 current
- **RED**：ScopeHead v2 已发布，Selection/学生课表仍读 v1 EFFECTIVE。
- **PASS**：所有正式读取 current head；历史必须显式 asOf/version。

### 风险卡 05-04：Published Change 后四端是否一致
- **RED**：管理端变更已发布，学生/教师某一端仍旧缓存。
- **PASS**：版本变化触发刷新或读时 fresh；四端显示同一 vN。

---

## 来源：`06_Selection_风险卡.md`

### 风险卡 06-01：坏 JSON fail-open
- **RED**：scope/prerequisite/rule 损坏后学生仍可选。
- **PASS**：corrupted config → SYSTEM_ABNORMAL/BLOCKED。

### 风险卡 06-02：validator 偷 commit
- **RED**：调用者外层还没完成，validate reject 已把 unrelated pending changes 提交。
- **PASS**：纯读 validator 0 commit；失败审计独立事务或 outer command。

### 风险卡 06-03：先修读旧成绩
- **RED**：补考已 PASS，旧 AcademicGrade 仍 FAIL；Selection错误拒绝。
- **PASS**：EffectiveGrade Provider 同D线复用。

### 风险卡 06-04：Lottery / FCFS / Waitlist 混语义
- **RED**：LOTTERY_LOST 被自动当 WAITLIST；FCFS course显示抽签文案。
- **PASS**：algorithm-specific state machine；Waitlist若未启用则 N/A。

### 风险卡 06-05：PENDING_LOTTERY 重复选
- **RED**：学生端本地selectedIds未包含PENDING，继续显示“选课”。
- **PASS**：allowedActions后端 authoritative。

---

## 来源：`07_Roster_风险卡.md`

### 风险卡 07-01：Selection-managed 被 admin refresh 覆盖
- **RED**：LOCK→Roster 后跑 admin refresh，source/hash变ADMIN_CLASS。
- **PASS**：selection relation存在时 resolver/setter fail-closed。

### 风险卡 07-02：Roster version race
- **RED**：两个 manual refresh 同时以v3为base，最后静默覆盖。
- **PASS**：expectedVersion/row lock，1成功1 stale。

### 风险卡 07-03：下游直接猜名单
- **RED**：Grade/Exam/Attendance任一 service 查询行政班或SelectionRecord作为正式候选。
- **PASS**：只通过 roster consumer public service。


---

# V1.0 核心施工总册附录

> 本节完整保留 V1.0 主任务、页面、门禁、测试与 DoD；V1.2/V1.3 只是在其上补充风险与学校交付层。

---

## 来源：`05_排课与正式课表_施工总册_V1.0.md`

# 教务中心 05 — 排课与正式课表唯一施工总册 V1.0

> 仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 文档生成日期：2026-08-16  
> 施工定位：**排课 Draft / Publish / Published Change / 四端正式课表**  
> 原则：**Schedule 负责“什么时候/在哪里”，TeachingRoster 负责“谁正式参加”；不新造第二套正式课表。**

---

## 1. 当前成熟度

**后端 🟢；管理 PC 🟠。**  
后端已经建立强正式课表真值；真正的 P0 是旧 UI 仍在自由拼课程+教师+班级。

---

## 2. 唯一 Authority

### 2.1 TeachingTask 是排课唯一业务身份
正式排课项必须尽量稳定回链 `task_id`。  
`course_name / teacher_name / class_name` 只做 snapshot/display，不作为新业务身份。

### 2.2 Published Schedule Truth

```text
(term_id + scope_type + scope_id)
        ↓
AaScheduleScopeHead.active_batch_id
        ↓
AaScheduleBatch(PUBLISHED)
        ↓
AaScheduleItem(task_id + occurrence coordinates)
```

旧 `AaScheduleItem.status == EFFECTIVE` 只能做 `[COMPAT]`；不能再代表“当前正式”。

### 2.3 学生正式课表
最终解释必须是：

```text
current Published Schedule items
∩
current TeachingRoster membership
```

固定行政班课程与 Selection 课程最后都通过 TeachingRoster 汇流。

---

## 3. 当前数据模型审计

| 模型 | 当前状态 | 裁决 |
|---|---|---|
| AaScheduleBatch | 已存在 | KEEP |
| AaScheduleItem | 已存在 | KEEP |
| AaScheduleScopeHead | 已存在，active head/version | KEEP，唯一 current truth |
| AaSchedulePublish | 已存在 | KEEP |
| AaScheduleChange | 已存在 | KEEP |

不得新建 OfficialSchedule 表。

---

## 4. 核心服务审计

### 4.1 `academic_affairs_schedule_final_service.py` — KEEP
已完成：
- Task-first；
- READY task；
- 同学期；
- startWeek/endWeek；
- term教学周；
- Task teachingWeekStart/End；
- classroom type/capacity；
- teacher/class/classroom overlap；
- weeklyHoursTotal；
- DELETE/UPDATE 同样走 canonical validation。

### 4.2 `academic_affairs_schedule_gate_service.py` — KEEP
已完成发布前：
- 漏排；
- 超排；
- task orphan；
- slot/week 坐标；
- 教师/班级/教室冲突。

### 4.3 `academic_affairs_schedule_truth_service.py` — KEEP
已完成：
- ScopeHead；
- 行锁；
- activeBatch；
- version；
- supersede；
- 跨 batch 资源冲突；
- MySQL fresh read。

---

## 5. 当前页面审计

### `AaScheduleMaintainView.vue` — P0 REWIRE
当前旧链：

```text
选行政班
→ 点网格
→ 自由选 course
→ 自由选 teacher
→ 选 classroom
→ 发送 courseName + teacherName + classId
```

问题：没有显式 `taskId`。

此外：
- 默认结束周 = 18；
- 内置文本 CSV；
- teacherName 直接作为 teacherKey。

---

# 6. 施工卡 05-01 — Task-first 排课 UI

## 6.1 新链

```text
选择 term
→ 选择 READY TeachingTask
→ 只读显示：课程 / 教师 / 行政班/教学班 / 周学时 / 教学周
→ 用户只填：weekday / slot / weeks / parity / classroom
→ submit taskId
```

## 6.2 TeachingTask Picker
必须支持：
- search；
- courseCode；
- courseName；
- teacherName；
- className；
- weeklyHours；
- teachingWeeks；
- status。

只返回 READY。

## 6.3 RED
- 无 taskId 新 UI 提交失败；
- 非 READY task；
- task.term != batch.term；
- 前端篡改 courseName 不影响身份；
- 前端篡改 teacherName 不影响身份。

---

# 7. 施工卡 05-02 — 周次来源统一

前端禁止默认 18 周。

来源顺序：
1. Task teachingWeekStart/End；
2. Term teachingWeekCount；
3. 如果都缺 → BLOCKED，不猜 18。

RED：17周学期无法产生18周课表。

---

# 8. 施工卡 05-03 — 排课 XLSX 统一导入

禁止继续使用页面文本 CSV 作为生产主入口。

### 模板

| 列 | 必填 |
|---|---|
| 教学任务ID | 是 |
| 星期 | 是 |
| 节次ID | 是 |
| 起始周 | 是 |
| 结束周 | 是 |
| 单双周 | 是 |
| 教室ID | 是 |
| 备注 | 否 |

### 流程
`upload → scan → dry-run → error xlsx → confirm → reread`

必须复用 Academic File Exchange。

---

# 9. 施工卡 05-04 — Published Schedule 单一读真值

所有消费者：
- Teacher Schedule；
- Student Schedule；
- Class Schedule；
- Room Schedule；
- Selection conflict；
- Exam scheduling；

统一走：
`ScopeHead.active_batch_id`。

### RED
发布 v1 后有冲突；发布 v2 消除冲突后：
- v1 仍可历史回放；
- current conflict 只看 v2。

---

# 10. 施工卡 05-05 — Publish 乐观锁

Publish 请求必须带：
`expectedVersion`。

冲突返回：
`409 SCHEDULE_HEAD_STALE`。

---

# 11. 施工卡 05-06 — Published Change

发布后不能直接改 item。

流程：
`preview impact → change reason → new change fact / version → publish → notify → history`

至少记录：
- before；
- after；
- operator；
- reason；
- sourceVersion；
- targetVersion。

---

# 12. 施工卡 05-07 — 学生正式课表收敛

当前 compat：行政班 + LOCKED Selection。  
目标：统一按 TeachingRoster membership。

### RED
- 合班学生显示正式课；
- 重修学生显示正式课；
- MANUAL roster学生显示正式课；
- 非Roster成员不得显示。

---

# 13. 施工卡 05-08 — 课表版本与打印

管理/教师/学生课表显示：
- 学期；
- 数据来源；
- version；
- lastUpdatedAt；
- publishedBy（管理端）；
- change notice（如有）。

打印/导出带：
- schoolName；
- termName；
- generatedAt；
- scheduleVersion。

---

# 14. 数据范围

- 教务处：全校；
- 学院教务：本学院对象；
- 教师：本人 Task；
- 学生：本人；
- 教室管理员（如存在）：按授权范围。

空 dataScope → 0 rows。

---

# 15. MySQL 并发门禁

必须覆盖：
1. 双 publish；
2. 同教师同时间并发排课；
3. 同教室并发占用；
4. import confirm vs manual edit；
5. stale expectedVersion。

---

# 16. 四端 Gold

## 管理 PC
Task-first 排课 → 发布 → 看到 version。

## 教师 PC / 小程序
读取同一 Published Schedule。

## 学生 PC / 小程序
读取 PublishedSchedule × TeachingRoster。

四端时间/地点/version 一致。

---

# 17. 生产性能

目标：
- 1000 TeachingTasks；
- 20000 students；
- 10000 schedule items；
- 课表查询 SQL 分页/索引；
- 不允许 `.all()` 后大规模 Python 过滤。

---

# 18. 最终 DoD

- 新建排课 100% taskId-first；
- 0 新名称匹配正式写；
- 0 新文本 CSV 正式入口；
- 0 current read 直接依赖旧 EFFECTIVE；
- ScopeHead 并发安全；
- 学生正式课表以 Roster membership 解释；
- 四端一致；
- MySQL 并发绿。


---

## 来源：`06_Selection与正式名单_施工总册_V1.0.md`

# 教务中心 06 — Selection / Lottery / TeachingRoster 唯一施工总册 V1.0

> 仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 文档生成日期：2026-08-16  
> 原则：**不新造第二套选课、名单、抽签或学生课表真值。**

---

# 1. 当前成熟度

**选课并发基座较强，但当前正式可用仍有 P0。**

强能力：
- FCFS 行锁 + 原子 capacity；
- Lottery deterministic SHA-256；
- CLOSED→DRAWN claim；
- LOCK→TeachingRoster；
- Selection 未锁时 TeachingRoster fail-closed。

---

# 2. 唯一 Authority

```text
SelectionBatch
→ SelectionCourse(taskId)
→ SelectionRound
→ SelectionRecord
→ LOCK
→ TeachingRosterVersion(source=SELECTION_LOCK)
```

---

# 3. P0-01 — Batch 正式合同

DRAFT 可以不完整；PUBLISH 前必须：
- termId；
- selectStart/selectEnd；
- scope；
- frozen ruleJson；
- ruleHash；
- 至少一门合法 SelectionCourse。

非法日期不允许解析成 None 后继续。

---

# 4. P0-02 — SelectionCourse 必须 Task-bound

新正式供给：`teachingTaskId` 必填。

Task 必须：
- same term；
- same course identity；
- formationMode permits selection；
- 合法状态。

历史无 Task 行先 inventory/backfill，不先改 NOT NULL。

---

# 5. P0-03 — JSON fail-closed

所有：
- applyScopeJson；
- prerequisiteCodesJson；
- ruleJson；

必须 strict parse。

解析错误：
`SYSTEM_ABNORMAL/BLOCKED`。

不得 `{}` / `[]` fallback。

---

# 6. P0-04 — EffectiveGrade Provider

禁止 `_passed_course_names()` 读旧 AcademicGrade + courseName。

正式输入：
- studentId；
- courseId/courseCode/version；
- asOf。

输出：
- effectiveResult；
- attempts；
- policySnapshot。

---

# 7. P0-05 — Schedule Conflict Provider

冲突判断：
- current ScopeHead；
- active batch；
- current task slots。

旧 EFFECTIVE 仅 COMPAT。

---

# 8. P0-06 — SelectionPreflight

统一阶段：
- PUBLISH；
- OPEN；
- CLOSE；
- LOCK。

检查：
- term；
- window；
- scope；
- rule；
- task；
- schedule；
- capacity；
- prerequisite；
- repeat；
- credit；
- low enrollment；
- algorithm。

纯读，不 commit。

---

# 9. P0-07 — 拒绝审计唯一

validator 不写审计、不 commit。

outer command：
1. catch business reject；
2. rollback business tx；
3. 独立 audit tx 写一次；
4. return businessCode。

---

# 10. FCFS

保持 atomic capacity。

Gold：最后1名额 100+ 并发：
`selected <= capacity`。

---

# 11. Lottery

保持 SHA-256 deterministic。

追加 manifest：
- candidateHash；
- resultHash；
- algorithmVersion；
- drawnAt；
- candidateCount；
- winnerCount。

禁止 redraw。

---

# 12. Student Projection

后端返回：

```json
{
  "status": "PENDING_LOTTERY",
  "statusLabel": "待抽签",
  "phase": "LOTTERY_PENDING",
  "eligibility": {...},
  "allowedActions": ["VIEW", "DROP"],
  "reason": "已进入抽签候选",
  "howToResolve": "等待抽签结果",
  "window": {...},
  "lottery": {...},
  "reselect": null
}
```

PC/小程序只渲染 allowedActions。

---

# 13. COURSE_CANCELLED / 补改选

课程取消：
- 原 record 保留；
- status=COURSE_CANCELLED；
- 发送通知；
- 学生获得 RESELECT_ALLOWED；
- 新选课仍重新 preflight。

---

# 14. LOCK → TeachingRoster

LOCK 事务：
1. lock batch；
2. preflight；
3. freeze courses；
4. lock active records；
5. finalize statuses；
6. set RosterVersion；
7. count/hash reconcile；
8. batch LOCKED；
9. commit。

---

# 15. Student PC / miniapp 状态

至少支持：
- OPEN；
- PENDING_LOTTERY；
- SELECTED；
- LOTTERY_LOST；
- COURSE_CANCELLED；
- LOCKED；
- DROPPED。

禁止客户端通过 `selectedIds` 自己决定按钮。

---

# 16. dataScope

- 教务处全校；
- 学院教务本学院；
- 学生本人；
- 空 scope 0 rows。

SQL 先过滤，不允许 `.all()` 后 Python 过滤。

---

# 17. MySQL 高峰

必须：
- FCFS 100 并发最后1名额；
- 1k burst；
- lottery double draw；
- lock/drop race；
- duplicate click；
- selectedCount / capacity / Roster count/hash reconciliation。

---

# 18. 最终 DoD

- 0 JSON fail-open；
- 0 旧成绩正式资格读取；
- 0 旧课表正式冲突读取；
- 0 validator commit；
- 0 双拒绝审计；
- 新 SelectionCourse 100% Task-bound；
- 新正式 Batch 100% term/window/scope/rule；
- Student PC + miniapp 100% allowedActions；
- MySQL 不超卖；
- Lottery deterministic；
- LOCK→Roster 对账绿。


---

## 来源：`07_TeachingClass与TeachingRoster_施工总册_V1.0.md`

# 教务中心 07 — TeachingClass / TeachingRoster 唯一施工总册 V1.0

> 仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 文档生成日期：2026-08-16  
> 原则：**TeachingRoster 是“谁正式修这门课”的唯一汇流，不新造第二名单。**

---

# 1. 当前成熟度

**🟢。强底座，禁止重写。**

---

# 2. 唯一结构

```text
TeachingTask
→ AaTeachingClass
→ AaTeachingRosterVersion(current head)
→ AaTeachingRosterMember
```

来源：
- ADMIN_CLASS；
- SELECTION_LOCK；
- MANUAL；
- RETAKE。

---

# 3. RosterVersion

必须：
- versionNo；
- current；
- sourceType；
- rosterHash；
- memberCount；
- generatedAt；
- reason。

---

# 4. Selection Guard

若 Task 存在 Selection 关系：
- 未 LOCK → fail-closed；
- 不得 fallback ADMIN_CLASS；
- LOCK → SELECTION_LOCK。

---

# 5. Fixed Course

无 Selection 关系：
ADMIN_FIXED 可使用 ADMIN_CLASS Roster。

这不是绕过 Selection，而是本来就不需要选。

---

# 6. MANUAL 更新

必须：
- permission；
- reason；
- expectedVersion；
- beforeHash；
- afterHash；
- audit。

Selection-managed 默认禁止普通 admin refresh 覆盖。

---

# 7. RETAKE

重修学生进入正式课程后：
- source=RETAKE 或现有正式来源；
- 必须形成 current RosterVersion；
- 下游考勤/考试/成绩统一消费。

---

# 8. 下游 Consumer

Attendance / Exam / Grade：
只能通过正式 Roster Consumer Service。

禁止：
- 行政班猜名单；
- SelectionRecord 猜名单；
- 课程名+学生号猜名单。

---

# 9. 学生课表

学生正式课表 =
`current Published Schedule × current Roster membership`。

---

# 10. Reconciliation

每学期检查：
- taskCount；
- teachingClassCount；
- currentRosterCount；
- orphanTaskIds；
- orphanClassIds；
- countMismatch；
- hashMismatch；
- staleManagedRoster。

---

# 11. 20K Scale

- 单 Task 20K member bulk write；
- 学期 1000 Task aggregate reconcile；
- 避免 per-member ORM commit；
- 避免 N+1 hash scan。

---

# 12. Export

Roster export XLSX：
- taskId；
- course；
- teacher；
- version；
- source；
- memberCount；
- rosterHash；
- generatedAt；
- studentNo/name；
- watermark。

20K 大导出走后台任务。

---

# 13. UI

管理/教师页显示：
- 正式名单；
- source；
- version；
- count；
- hash short；
- updatedAt；
- history。

名单详情独立页面，不 Drawer。

---

# 14. MySQL 并发

- 两个 manual refresh same base version；
- Selection LOCK vs admin refresh；
- Retake refresh vs Grade roster snapshot；
- 失败 rollback。

---

# 15. Gold

- fixed course ADMIN_CLASS；
- selectable course SELECTION_LOCK；
- 0 Selection-managed 覆盖；
- 0 hash mismatch；
- 0 orphan task/class；
- Attendance/Exam/Grade同一名单；
- 历史版本可回放。

---

# 16. 禁止

- 新建第二 Roster 表；
- UI 直接改 member；
- 下游直接查 SelectionRecord；
- 删除 superseded history；
- 以名单名称代替 studentId。

---

# 17. 最终 DoD

- TeachingRoster 唯一 Authority；
- 所有 active Task 有合法 roster readiness；
- 所有 current version count/hash 一致；
- 下游 consumer 无绕行；
- MySQL 并发绿；
- 20K scale绿。



---

# 最终开发节奏

固定顺序：

```text
审 exact-head
→ 对齐 B-C1/B-C2/B-C3
→ 选本模块最小安全施工面
→ RED
→ 改 canonical service / projection / page
→ targeted
→ MySQL
→ 四端真实业务 Gold
→ 更新本线 Contract / Evidence
→ commit
→ 自动进入下一施工卡
```

B 线目标不是把 Selection 做复杂，而是把：
`正式课表 → 选课制度 → 锁名单 → TeachingRoster → 下游正式教学`
做成一个学校可运行、可解释、可对账的强闭环。





---


# 四线共同硬门：后端变化必须同步前端 UI + 截图视觉复审 + 真实点击 E2E

> 本节是 A / B / C / D 四条施工线的统一施工硬门。  
> 任何一条线只要修改了后端正式 Contract、DTO、状态机、权限、dataScope、allowedActions、error code、read-only/archived behavior，必须在同一施工批次完成对应前端消费者同步；否则本批不得标记 COMPLETED。

## 1. Backend → Frontend Impact Matrix

每一刀后端变化后都必须建立影响矩阵：

| Backend Change | API / DTO | Consumer | UI Change | Screenshot | Real Click | Status |
|---|---|---|---|---|---|---|
| model / schema / enum | response fields | 管理PC | required | required | required | OPEN |
| Authority / lifecycle | status / allowedActions | 学生PC | required | required | required | OPEN |
| permission / dataScope | permission / object scope | 教师PC | required | required | required | OPEN |
| projection / error code | reason / howToResolve | 小程序 | required | required | required | OPEN |

没有对应消费者时，必须明确写：`N/A — 当前仓库不存在该角色/页面消费者`，不能默认为完成。

## 2. 前端禁止复制正式业务判断

客户端不得自行计算：
- 是否可选课；
- 是否可退课；
- 是否可锁名单；
- 是否可发布；
- 是否属于当前正式课表；
- 是否属于正式教学名单；
- 是否满足先修/重修；
- 是否为当前有效成绩；
- 是否允许归档/毕业。

统一消费后端：
`status / statusLabel / phase / allowedActions / blockers / reason / howToResolve / nextAction / readOnly`。

## 3. 页面同步要求

受影响页面至少复审：
- 首屏结论；
- 当前 blocker；
- 下一动作；
- 可执行按钮；
- 禁用原因；
- 空态；
- 错误态；
- 归档/只读态；
- 筛选/统计/导出；
- 小屏布局；
- 是否仍显示旧字段/旧状态/旧入口。

后端 writer 已升级为 TeachingTask-first 时，前端必须同步：
`选择Task → 课程/教师/对象只读回显 → 只填可变参数 → 提交taskId`。

## 4. Screenshot Before / After

影响 UI 的批次必须：
1. 修改前捕获 baseline screenshot，或记录无法进入原因；
2. 修改后用真实前端 + 真实后端重新截图；
3. PC 优先沿用仓库已有 visual Gold viewport；
4. miniapp 使用真实 H5 / 小程序目标视口；
5. 至少截图正常态 + 高价值阻断态 + 本批新增状态/只读态（如有）。

## 5. 截图必须实际视觉识别

施工 Agent 必须打开截图逐张检查：
- 标题/副标题；
- 首屏结论；
- blocker；
- allowedActions 按钮；
- 旧字段/旧入口泄漏；
- 截断/重叠/溢出；
- 表格横向溢出；
- 卡片密度；
- 弹窗/抽屉 viewport；
- sticky header；
- 状态标签；
- loading / empty / error / read-only；
- 窄屏点击；
- mock/placeholder 泄漏；
- console error。

发现问题必须：`修 → 重截图 → 再识别`。

## 6. 真实点击 E2E

UI 批次完成前必须真实点击：
- 进入真实路由；
- 选择学期/批次/TeachingTask；
- 点击真实按钮；
- 打开真实 modal/drawer；
- 填表；
- confirm；
- 观察真实 network request；
- 读取成功/失败反馈；
- refresh；
- reopen；
- 确认持久状态；
- 必要时换角色/换端。

至少一个负向：
`无权限 / 错误状态 / 409 / 校验失败 / archived read-only / duplicate click`。

## 7. 禁止把以下当作 UI 完成

- 只跑 pytest；
- 只调 API；
- 只跑 shallow component test；
- 只检查 DOM 存在；
- 只生成截图不点击；
- mock service；
- 因登录困难改假数据。

CI 无浏览器环境时只能标：`UI_E2E_BLOCKED`。

## 8. exact-head Evidence

每轮视觉/E2E必须记录：
- commit SHA；
- route；
- role；
- tenant；
- viewport；
- fixture identity；
- screenshot artifact；
- E2E run/job；
- console result；
- network mock count。

新 commit 后旧证据按影响范围失效。

## 9. 完成状态分级

- `BACKEND_GREEN_UI_OPEN`
- `UI_IMPLEMENTED_VISUAL_OPEN`
- `VISUAL_GREEN_E2E_OPEN`
- `EVIDENCE_STALE`
- `COMPLETED`

只有 backend + MySQL + frontend + visual + real-click + persistence + cross-client + permission/dataScope negatives + console 0 error + network 0 fake mock + exact-head evidence 全绿，才能标 `COMPLETED`。


---

# V2.1 B线施工裁决补充：前后端、四端与碰撞边界

## 1. B线 Frontend Impact Matrix 必须先建后改

B 每个 Wave 动后端前，先列：
- 哪个 DTO 字段变；
- AaScheduleMaintainView / AaSchedulingConsoleView / AaSelectionConsoleView / AaSelectionStudentView 哪些页消费；
- 学生 PC / 学生小程序是否同事实；
- 教师课表/正式名单是否受 ScopeHead 或 Roster 变化影响；
- 截图名、viewport、real-click scenario。

## 2. B-W3 Task-first UI 不是可选项

必须同步完成：
- TeachingTask Picker 成为第一对象；
- course / teacher / class 只读；
- taskId 发给后端；
- 教学周来自 Term/Task；
- 文本 CSV writer 从正常 UI 消失；
- 批量导入进入 Academic File Exchange。

## 3. B-W5 学生两端必须同状态

必须覆盖：
- PENDING_LOTTERY；
- LOTTERY_LOST；
- COURSE_CANCELLED；
- LOCKED；
- reselect；
- window closed；
- blocked prerequisite；
- schedule conflict。

学生 PC 和 miniapp 都只消费 allowedActions。

## 4. B线 Screenshot / Real-click 场景

排课至少：
- READY Task 正常排课；
- 冲突阻断；
- 17周学期；
- 刷新后正式项存在。

Selection 至少：
- 创建/配置/发布/open；
- FCFS 正常选课；
- PENDING_LOTTERY；
- LOTTERY_LOST；
- COURSE_CANCELLED reselect；
- LOCKED 只读；
- PC→miniapp换端一致。

## 5. PR碰撞安全

PR #96/#132/#133若触碰：
- route registration；
- services registry；
- model registry；
- permissions；
- Data Exchange；
- Alembic；

B 不直接抢写，写入INT request ledger。

---


# V1.5 深审附录补强：B线（Schedule / Selection）

> 目标：补足 V1.5 仍不够明确的页面级、权限级、导入/导出、历史设计 reconciliation、复杂 Selector 与真实学校高峰场景。

## Ⅰ-B. 当前仓库页面 / 路由 / API 再盘点

### 1. 管理/教师 PC 页面

#### AaScheduleMaintainView
- 当前正式职责：周课表维护、冲突显示、发布前排课。
- 当前风险：仍有 course/teacher/class 自由组合、18周默认、文本导入痕迹。
- V1.5 最终：Task-first + 学期周次 + Academic File Exchange。

#### AaSchedulingConsoleView
- 当前正式职责：排课工作台/批次/规则/冲突。
- V1.5 必须：区分‘草稿排课’和‘正式发布’，显示 ScopeHead activeBatch/version。

#### AaSelectionConsoleView
- 当前正式职责：批次、规则、课程供给、锁名单。
- V1.5 必须：Batch 创建时收 term/window/scope，SelectionCourse 100% TeachingTask-first。

#### AaSelectionStudentView
- 当前正式职责：学生选课主交互。
- V1.5 必须：状态、allowedActions、failure reason、lottery/reselect全部来自后端 projection。

### 2. 学生 PC
- 当前 StudentCourseSelection / StudentSchedule 页面需要同时读取：Selection projection + current Published Schedule。
- 禁止学生 PC 自己拼 eligible/canEnroll。

### 3. 学生 miniapp
- 主交互应与 PC 同义；可以更简洁，但状态/动作必须相同。

### 4. 教师端
- 教师不负责学生选课制度配置；只需要正式课表、正式名单。
- TeachingRoster 未 LOCK 时，教师端应看到“名单未冻结/不可点名”，而不是旧行政班 fallback。

## Ⅱ-B. Selection Eligibility 详细矩阵

| 规则 | 正式事实来源 | Fail-closed 条件 | 学生提示 |
|---|---|---|---|
| 学期 | A-C1 Term | 无正式 term | 当前选课批次未绑定正式学期 |
| 时间窗 | SelectionBatch | 非法/空窗口 | 选课时间尚未开放或已结束 |
| dataScope | Selection scope | JSON坏/范围空 | 当前课程不在你的适用范围 |
| TeachingTask | A-C4 | 无Task/跨学期/状态错 | 课程供给配置异常，请联系教务 |
| 正式课表 | B-C1 ScopeHead | 无active batch | 正式课表未发布，暂不能选课 |
| 时间冲突 | B-C1 occurrences | current head未知 | 无法确认课表冲突，已阻断 |
| 先修 | C EffectiveGrade | provider异常/策略缺失 | 无法确认先修完成情况 |
| 重修 | C EffectiveGrade + policy | attempt policy异常 | 无法确认重修资格 |
| 学分上限 | Selection policy | policy坏 | 选课规则异常 |
| 容量 | SelectionCourse | row lock异常 | 当前系统繁忙，请重试，不得误报满额 |
| Lottery | SelectionRound | draw未完成 | 已进入抽签，等待结果 |
| CANCELLED | SelectionCourse/Record | 无reselect policy | 课程已停开，请按指引补改选 |

## Ⅲ-B. Selector 复杂业务

### 1. 公选课
- 普通 FCFS/LOTTERY 规则。
- 院系/年级/专业可限制 scope。

### 2. 体育分项
- 课程身份与 TeachingTask 绑定；可按场地/教师/项目过滤。
- 不要用课程名称区分“篮球1/篮球2”身份。

### 3. 英语板块
- 若学校用分级考试/层级结果控制 eligibility，必须来自正式评测/成绩 Provider，不从页面输入。

### 4. 重修跟班
- 由 C EffectiveGrade / retake eligibility 决定；正式选上后进入 TeachingRoster。

### 5. 单开重修班
- TeachingTask formationMode=RETAKE；可进入独立 SelectionBatch 或 admin assign，但最终 Roster一致。

### 6. 补修/提前修读/免修
- 都是 eligibility/override policy；不能造第二 Enrollment 表。

### 7. 必修课退选
- 默认不允许；若学校允许，必须是显式政策/审批，前端不显示通用‘退课’。

## Ⅳ-B. Batch / Round / Scope 版本化

PUBLISH 时冻结：
- termId；
- scope snapshot/hash；
- rule schemaVersion/hash；
- course supply list hash；
- round algorithm/version/window；
- teachingTask identity。

OPEN 后规则变化：
- 不直接覆盖；
- 新版本 + 变更理由 + 影响预览；
- 已提交学生是否 grandfathered 必须学校政策明确。

## Ⅴ-B. 详细 UI 状态

### 教务控制台首屏
应优先显示：
1. 当前学期/选课批次；
2. 状态；
3. 窗口；
4. blocker 数；
5. 课程供给数；
6. 无Task课程数；
7. 当前人数/容量；
8. Lottery未抽签轮次；
9. 待补选/课程取消人数；
10. 下一步主按钮。

### 学生选课首屏
应优先显示：
1. 当前轮次；
2. 剩余时间；
3. 已选学分；
4. 可选学分；
5. 待抽签数；
6. 需要补选数；
7. 当前 blocker；
8. 下一步。

## Ⅵ-B. Import / Export / Print

### 课程供给导入
若需要批量供给：
- 必须走 Academic File Exchange；
- canonical列：batchId、teachingTaskId、capacity、minCapacity、algorithm、ruleProfileId；
- name列只做辅助校验；
- dry-run输出跨学期Task、重复Task、无READY Task、坏容量、坏algorithm。

### Selection名单导出
导出：
- Selection阶段状态；
- 教学任务ID；
- 课程；
- 学生；
- recordStatus；
- round；
- submitAt；
- selectedAt；
- blocker/override（如有）；
- batch ruleHash。

### 正式名单打印
必须使用 TeachingRosterVersion；文件标：rosterVersion/rosterHash/generatedAt。

## Ⅶ-B. 通知

事件：
- SELECTION_OPENED；
- ROUND_CLOSING_SOON；
- LOTTERY_RESULT_READY；
- COURSE_CANCELLED；
- RESELECT_REQUIRED；
- WAITLIST_OFFERED（若启用）；
- WAITLIST_OFFER_EXPIRING（若启用）；
- SELECTION_LOCKED。

通知对象：
- studentIds；
- class/major/grade scope；
- teacher（课程取消/名单锁定）；
- academic admin（异常）。

消息失败不回滚业务事实。

## Ⅷ-B. High-load Runbook

### 开选前
- Preflight blockers=0；
- ScopeHead ready；
- DB连接池正常；
- Redis若仅缓存，不影响正式选择正确性；
- capacity count reconcile；
- worker/Outbox健康；
- 告警开启。

### 高峰中
监控：
- enroll QPS；
- p95/p99 latency；
- lock wait；
- deadlock retry；
- capacity rejects；
- schedule conflict rejects；
- duplicate request count；
- unexpected 5xx。

### 高峰后
- SelectionRecord count；
- selectedCount reconcile；
- round result hash；
- no duplicate active records；
- no cross-tenant rows。

## Ⅸ-B. 真实学校场景补充

50. 同一课程两个教学班同时最后1席；学生并发只成功一个，不得两边都占。
51. 学生在PC选中，miniapp 100ms后重复提交，返回同一正式结果。
52. CLOSE命令与enroll同时发生，边界以数据库锁内服务器时间为准。
53. ScopeHead刚发布v2，学生已有浏览器缓存v1，提交时后端重新按v2判断冲突。
54. 课程取消与LOCK同时发生，只能按一个明确锁序成功，Roster不可含已取消课程错误成员。
55. Lottery结果已draw，管理员不能修改候选集/容量后重抽。
56. Override过期前选中，后续LOCK时是否继续有效必须按policy snapshot而非当前override猜。
57. 教学班MANUAL roster变更后，学生课表立即按新current roster刷新。
58. 补选审批通过瞬间课程满额，审批必须失败并保留申请状态/失败原因。
59. 1k burst后 selectedCount=实际active records，任何差异触发reconcile告警。


---

# V2.1 B线补丁：复杂状态视觉语义

## 1. 学生端状态不得只靠颜色

PENDING_LOTTERY：
- 标签：待抽签；
- 说明：已进入候选，尚未产生最终名额；
- 主动作：查看规则/等待；
- 不得显示“再次选课”。

LOTTERY_LOST：
- 标签：未中签；
- 说明：本轮未获得名额；
- 主动作：根据学校政策显示补选/候补/无动作；
- 不得默认自动进入Waitlist。

COURSE_CANCELLED：
- 标签：课程停开；
- 说明：该课程/教学班取消；
- 主动作：补改选；
- 原记录保留证据。

LOCKED：
- 标签：名单已锁定；
- 说明：已进入正式教学名单；
- 只读，不显示普通退课。

## 2. 管理端 Preflight 阻断必须可下钻

每个 blocker 显示：
- code；
- 中文说明；
- owner role；
- affected count；
- evidence link；
- howToResolve；
- batch/rule/schedule version。

禁止只显示“还有3个问题”。

## 3. Screenshot Gold

必须截图：
- 教务控制台正常可OPEN；
- 坏规则BLOCKED；
- 学生FCFS可选；
- PENDING_LOTTERY；
- LOTTERY_LOST；
- COURSE_CANCELLED；
- LOCKED；
- 17周学期排课；
- Task-first排课冲突态；
- 窄屏/小程序主要状态。

## 4. Real-click Gold

必须真实点击：
- 管理员选Task排课；
- 冲突提交失败；
- 修正后成功；
- 发布；
- 创建Selection Batch；
- 添加Task供给；
- OPEN；
- 学生PC选课；
- 学生小程序读取同状态；
- 管理员LOCK；
- 教师打开正式名单确认。


---

# V2.1 B线补丁：完整学期前后端联动验收

## 1. 排课后端变更后
必须同步：
- 排课Task Picker；
- 周次选择；
- 冲突说明；
- 正式版本；
- 学生/教师课表来源。

## 2. Selection后端变更后
必须同步：
- 管理控制台；
- 学生 PC；
- 学生 miniapp；
- TeachingRoster view；
- 课程取消/补选引导。

## 3. Roster变更后
必须同步：
- 教师名单；
- 考勤资格；
- 考试资格；
- 成绩资格；
- 学生正式课表。

## 4. 端到端真实点击链
`管理PC排课 → 发布 → 创建选课批次 → 添加Task课程 → OPEN → 学生PC选课 → 学生小程序复核 → LOCK → 教师PC名单 → 刷新 → 教师小程序名单/课表`

链中任何端状态不一致，不得封板。


---

# V2.1 B线补丁：文件 / 导入 / 下载 UX

## 1. 排课导入
- 正常 UI 不再提供文本 CSV writer；
- 提供“下载XLSX模板 / 上传 / 扫描 / 预检 / 下载错误行 / 确认”；
- 页面显示 job status / accepted / rejected / conflict / task mismatch。

## 2. 正式课表导出
- 版本；
- 学期；
- scope；
- generatedAt；
- operator；
- watermark（需要时）。

## 3. 正式名单导出
- TeachingRoster version/hash/source；
- 学生编号/姓名；
- 课程/教师/教学班；
- generatedAt；
- watermark。

## 4. 前端不得伪造导出成功
后台任务未完成时显示PROCESSING，失败显示FAILED与重试入口。


---

# V2.1 B线补丁：移动端真实性

## 学生 miniapp
高频优先：
- 当前轮次；
- 倒计时；
- 我的选课状态；
- 待抽签；
- 未中签；
- 停开补选；
- 锁名单；
- 正式课表。

不是把管理控制台缩小。

## 教师 miniapp
B线只需：
- 我的正式课表；
- 我的正式名单；
- 名单未锁阻断说明。

教师不负责配置Batch/Rule。


---

# V2.1 B线补丁：权限与dataScope

建议业务 permission（由INT注册）：
- `academic.schedule.read`
- `academic.schedule.write`
- `academic.schedule.publish`
- `academic.selection.read`
- `academic.selection.manage`
- `academic.selection.override`
- `academic.selection.lock`
- `academic.roster.read`
- `academic.roster.adjust`

范围：
- 教务处：学校；
- 学院教务：学院；
- 教师：本人Task/Roster；
- 学生：本人。

空scope=0 rows。


---

# V2.1 B线补丁：数据对账

## Schedule Reconciliation
- ScopeHead active batch exists；
- active batch PUBLISHED；
- item count；
- task orphan；
- task term mismatch；
- teacher/class/room conflicts；
- version history。

## Selection Reconciliation
- course selectedCount；
- active record count；
- capacity；
- duplicate active；
- badTask；
- badTerm；
- badScope；
- lottery manifest。

## Roster Reconciliation
- Selection LOCK records count = roster memberCount；
- hash match；
- source=SELECTION_LOCK；
- current version唯一。


---

# V2.1 B线补丁：最终签字证据格式

```json
{
  "line": "B",
  "exactHead": "...",
  "termId": "...",
  "schedule": {"scopeHeadVersion": 4, "taskFirstRate": 1.0},
  "selection": {"badJsonFailOpen": 0, "taskBoundRate": 1.0},
  "roster": {"countMismatch": 0, "hashMismatch": 0},
  "frontend": {"impactOpen": 0},
  "visual": {"screenshotsReviewed": true},
  "e2e": {"realClick": true, "fakeMockCount": 0},
  "mysql": {"fcfsOversell": 0, "doubleLottery": 0},
  "status": "COMPLETED"
}
```

任何字段不满足不得把status写COMPLETED。
