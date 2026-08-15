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



# 0A-C. C线一键开工总控提示词（直接复制到C施工窗口）

```text
@GitHub

你现在接管教务中心 V2.1 四线并行施工：

C — Teaching Execution（教学执行线）

仓库：
penghaibin9/saas

固定施工分支：
agent/academic-c-teaching-execution

创建 Draft PR（草稿拉取请求），不合并 main（主分支），不 force push（强制推送）。

唯一当前施工总册：
《C_教务Teaching_Execution_当前代码精确施工总册_V2.1_20260816.md》

C线当前成熟度最高。任务不是重写考务/成绩，而是保护成熟链，补正式课次、兼容旁路、教师高频入口、规模和前端体验闭环。

第一笔建立：

docs/06-开发施工与质量验收/施工记录/
2026-08-16-教务C线-Teaching-Execution-V2.1-施工顺序与文档读取地图.md

记录：
main/C exact HEAD；
PR #96/#132/#133碰撞；
特别标出services/__init__.py、academic_affairs_registry.py、教师小程序grade-entry；
C KEEP矩阵；
C-W0～C-W5；
每批文档/源码/测试；
B Contract Freeze输入；
C-C1/C-C2/C-C3输出；
Frontend Impact Matrix；
截图识别；
真实点击E2E；
MySQL；
exact-head证据；
下一入口。

先读本总册：
C-0
C-P0-01～C-P0-04
C-P1-05～C-P1-08
C-W0～C-W5
0B/0C-C
自行纠错
最终签字；
再按Wave读V1.5附录。

C-W0：
读成熟链冻结章节、Attendance/Exam/Grade附录。
源码：
attendance_public_service
exam_facade
exam_core_router
grade_service
effective_grade_policy_service
grade correction/recheck
roster consumer snapshot
tests。
建立KEEP矩阵：
Attendance Task/Roster；
Exam snapshot/publish；
Grade stable course identity/Roster snapshot；
EffectiveGrade；
Correction/Recheck。
先证明，不重写。

C-W1：
读取 C-P0-01/C-P0-02、B-C1 Published Schedule Contract、B TeachingRoster Contract。
若B未冻结，只做调用图/RED，不伪造合同。
源码：
attendance public service
schedule truth
schedule change
TeachingTask
RosterConsumerSnapshot
tests。
先证伪当前是否已有Published Occurrence（正式课次）校验；没有才补。
普通考勤 = Task + current schedule + schedule change + roster。
特殊考勤 = ADMIN_SPECIAL + reason + evidence。
冻结 C-C1 Attendance Consumer Contract。
同步教师PC/小程序课表与考勤UI；调课前后截图必须证明旧课次退出、新课次生效；真实点击点名并刷新回读。

C-W2：
读取 C-P1-06、Teacher Today附录和当前教师首页。
源码：
mobile academic public service
UnifiedTodo
teacher schedule
attendance
exam
grade
schedule change
教师PC/小程序入口。
只做read projection，不建第二Task/Todo。
首屏：今日课→名单→点名→调课变化→监考→成绩待办。
必须截图识别首屏信息层级和窄屏；真实点击从首页三步内进入点名。

C-W3：
读取 C-P0-03、集中/分散考试附录、考务施工卡。
源码：
exam facade/models
incident closure
student exam projection
invigilator
seat assignment
publish tests。
只补模式/打印/监考改派/异常/通知/体验，禁止重写正式名单和发布门禁。
冻结 C-C2 Exam Consumer Contract。
同步管理端/教师端/学生考试UI；截图考场/监考/异常状态并真实点击发布/阻断/回读。

C-W4：
读取 C-P0-04/C-P1-05/C-P1-07、成绩附录和PR #96最新diff。
源码：
grade service
effective grade policy
grade task page
grade import
correction/recheck
workload
教师小程序grade-entry
scheduler/outbox
tests。
施工SQL分页、截止/延期/逾期、催录、退回重提、大XLSX、工作量对账。
冻结 C-C3 Effective Grade Read Contract。
同步教师PC/小程序成绩状态与allowedActions；必须截图正常录分、退回、逾期/延期、已发布等关键态并真实点击。

C-W5：
做真实教师连续链：
正式课表 → 今日课程 → 正式名单 → 点名 → 调课 → 监考 → 录成绩 → 学院退回 → 教师重提 → 发布 → EffectiveGrade。
PC和教师小程序、refresh、logout/login、role change、teacher replacement全部一致。
同步PR #96后只认最终exact-head证据。

禁止：
重建Exam/Grade/EffectiveGrade/TeachingRoster/UnifiedTodo；
Teacher Today造第二任务系统；
普通教师走ADMIN_SPECIAL；
名称做正式课程身份；
未读PR #96最新diff覆盖grade-entry；
直接抢services/__init__.py或academic_affairs_registry.py；
skip/xfail/ignore；
SQLite代替MySQL；
force；
合并main。

固定循环：
读文档 → exact-head源码 → CURRENT FACT → RED → 后端修复 → targeted
→ KEEP regression → MySQL
→ Frontend Impact Review
→ UI同步
→ 修改前/后截图
→ 打开截图视觉识别
→ 修复视觉问题并重截图
→ 真实浏览器可见控件点击E2E
→ refresh/relogin/角色变化
→ exact-head证据
→ 回写施工地图
→ 下一安全Wave。

后端绿但UI/截图/真实点击未完成，只能标BACKEND_GREEN_UI_OPEN。

现在：
创建固定分支 → Draft PR → 写C线施工地图 → C-W0。
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



## 0C-C. C线后端变化对应的前端同步重点

C线必须重点复查：
- Teacher Today（教师今日工作台）；
- 教师PC课表/考勤；
- 教师小程序教务首页/课表/考勤；
- 调停课台账/教师通知；
- Exam（考务）批次/考场/监考/异常页面；
- 学生考试查询；
- Grade（成绩）任务/录分/审核/发布/更正/复查；
- 教师小程序 grade-entry（成绩录入）；
- Workload（工作量）；
- 学生正式成绩/成绩单消费者。

特别要求：
- Published Occurrence（正式课次）合同变化后，教师Today、课表、考勤创建页必须同时变化。
- 调课生效后截图必须证明旧时间不再显示为当前课次，新时间/地点在教师端一致。
- Grade allowedActions（成绩允许动作）变化时，教师PC与小程序按钮必须同步。
- 成绩退回、逾期、延期、已发布必须有明确中文状态与下一步。
- PR #96碰撞文件的UI证据只有在最终集成exact-head上才有效。


---


# C（教学执行线）— 当前代码精确审计与最终施工裁决

## C-0 当前真实成熟度

**当前代码生产成熟度：92/100。目标：99/100。**

C线不是“重做考试和成绩”，而是**保护当前最成熟的后半链，补最后的课次真实性、兼容旁路隔离、规模和教师高频体验。**

### 当前强能力
- Attendance（考勤）正常教师路径已经TeachingTask-first（教学任务优先）、当前学期、教师本人、正式TeachingRoster（教学名单），并冻结名单消费者快照。
- Exam（考务）已经具备Task（任务）、正式名单、考场、座位、监考、资源冲突和发布完整性。
- Grade（成绩）已经绑定稳定courseId/version（课程编号/版本）、正式名单、RosterConsumerSnapshot（名单消费者快照）、提交/审核/发布/退回。
- EffectiveGrade（有效成绩）策略非常成熟：多次修读无正式策略时fail-closed（失败阻断），正式策略会冻结快照与哈希。
- Grade correction/recheck（成绩更正/复查）和归档后纠错已经有强事实链。
- Workload（教师工作量）已有模型、迁移、service（服务）、页面和测试，不是新增模块。

### 当前需要补强
1. 普通考勤场次是否与当前Published Occurrence（正式课次）一一对应，需要最终证伪/封口。
2. 管理员无Task（任务）的人工考勤兼容路径需要显式标记和隔离。
3. Grade task list（成绩任务列表）仍存在 `.all()` 后Python分页。
4. 教师Today（今日）工作台还没有充分利用成熟Task/Schedule/Roster/Exam/Grade（任务/课表/名单/考试/成绩）聚合。
5. 成绩截止/催录运营合同需要核实并补齐。
6. PR #96（拉取请求）直接碰教师小程序grade-entry（成绩录入）与共享注册文件，C线必须按碰撞协议施工。

---

## C-P0-01 考勤名单已经正确，但“这节课是否真的存在”仍需最终封口

### 当前代码
`academic_affairs_attendance_public_service.py（考勤公开服务）` 正常教师路径已经做：
- current term（当前学期）；
- TeachingTask（教学任务）存在；
- Task状态可教学；
- 同当前term；
- 当前教师是任务正式教师；
- resolve_versioned_roster（解析版本名单）；
- 同事务freeze ATTENDANCE_SESSION roster snapshot（冻结考勤名单快照）。

这是很强的。

### 仍需证伪的问题
create_session（创建考勤场次）接收：
- sessionDate（场次日期）
- slotNo（节次）

在本轮读取的公开服务中，尚未看到它必然校验：
“这个Task在当前ScopeHead（正式课表头）与ScheduleChange（调停课变更）解析后，今天这个节次确实有一节正式课”。

### 为什么重要
名单对了，不代表场次对了。

如果没有其他层二次校验，教师可能：
- 对周二课程在周三建考勤；
- 调课后还在旧时间点名；
- 给一个合法Task随便造日期/节次。

### 施工顺序
**先证伪，不直接改。**
1. 全仓搜索attendance session create（考勤场次创建）所有调用；
2. 搜索Published Schedule occurrence resolver（正式课次解析）；
3. 如果已经在更深层校验，补合同测试，不重复实现；
4. 如果没有，建立只读PublishedOccurrenceProvider（正式课次提供者）：
   - Task；
   - ScopeHead active batch（正式课表头当前批次）；
   - ScheduleChange（调停课变更）；
   - 周次、单双周、节假日、补课日；
5. 普通考勤绑定正式occurrence identity（课次身份）。

### RED（先失败测试）
- 非正式日期/节次创建失败。
- 调课后旧课次失败、新课次成功。
- 单双周错误周失败。
- 节假日停课不应创建普通考勤。
- 补课日正式变更后可以创建。

---

## C-P0-02 管理员人工考勤旁路要显式隔离

### 当前代码
管理员可以不传TeachingTask（教学任务）：
- 按classId（行政班）；
- 从StudentProfile（学生主档）取学生；
- 生成标准AaAttendanceSession（考勤场次）。

代码内部有 `ADMIN_MANUAL（管理员手工）` 语义，但当前场次事实是否有足够模型级sourceType（来源类型）仍需核。

### 不能简单删除
真实学校有：
- 历史补录；
- 特殊活动；
- 数据迁移后的纠错；
- 无标准课表的特殊场次。

### 但必须和正常教学分开
否则统计时可能把“管理员补录”误当正式课堂。

### 最终合同
普通场次：
`Task + Published Occurrence + Roster Snapshot（任务+正式课次+名单快照）`

特殊场次：
`ADMIN_SPECIAL（管理员特殊） + reason（原因） + evidence（证据） + operator（操作人） + 可关联Task则必须关联`

### 权限
- 普通教师永远不能触发ADMIN_SPECIAL（管理员特殊）。
- 特殊补录是独立高权限动作。
- 必须可在统计和审计中区分。

---

## C-P0-03 Exam（考务）当前不是重构对象，是保护对象

### 本轮确认的强事实
`academic_affairs_exam_facade.py（考务公开门面）`：
- Exam Batch（考试批次）需要formal term（正式学期）；
- 课程确认需要TeachingTask（教学任务）；
- 课程确认时冻结当前Roster（名单）快照；
- 铺位只允许快照名单成员；
- 同一学生不能在同课程多个考场重复；
- 考场使用有效容量；
- 发布前检查日期/时间、Task、当前Roster快照、预计人数、考场、座位全集、容量、监考；
- 发布后普通时间修改受限。

### 专业裁决
**KEEP（保留）。禁止为了“统一架构”重做考务。**

只做：
- 集中/分散考试mode（模式）如果当前目标学校确实需要；
- 考试名单/座位/监考正式打印；
- 监考冲突/改派；
- 缺考/违纪/缓考异常闭环；
- 教师/学生Today（今日）投影；
- 通知与规模。

### 保护性RED
任何C线施工都必须保持：
- Roster换版后旧Exam snapshot（考试快照）不能假装当前；
- 名单外学生不能铺位；
- 座位集合不完整不能发布；
- 容量不足不能发布；
- 监考不完整不能发布。

---

## C-P0-04 Grade（成绩）已经是正式主链，禁止另建第二套成绩逻辑

### 当前确认
`academic_affairs_grade_service.py（成绩服务）`：
- Task（任务）绑定concrete course version（具体课程版本）；
- 正常成绩任务消费正式TeachingRoster（教学名单）；
- submit（提交）冻结RosterConsumerSnapshot（名单消费者快照）；
- publish（发布）确认冻结名单仍是当前；
- 保存课程身份、修读次数、教学班、名单版本、名单来源；
- special admin supplement（管理员特殊补录）有独立来源语义。

`academic_affairs_effective_grade_policy_service.py（有效成绩策略服务）`：
- formal grade write（正式成绩写）要求active policy（生效策略）；
- 多次历史修读无冻结策略时fail-closed（失败阻断）；
- courseId/courseCode/version（课程编号/代码/版本）优先；
- name-only（仅名称）历史成绩不会静默并入；
- 策略快照有哈希和幂等冲突。

### 这带来一个重要跨线裁决
B线的先修/重修必须向C线EffectiveGrade（有效成绩）收敛。

**绝不能因为B线旧代码简单，就把C线正式成绩再降级成名称查询。**

### C线只做
- SQL（结构化查询语言）分页；
- 教师高频体验；
- 截止/催录；
- 批量导入规模；
- 更正/复查体验；
- 工作量事实对账。

---

## C-P1-05 Grade task list（成绩任务列表）规模欠账

### 当前代码
list_tasks（任务列表）构造SQL条件后：
`.all()`
再Python：
`rows[offset:offset+page_size]`

### 生产风险
多学期累积后：
- 内存；
- 延迟；
- 学院范围查询；
都会随历史总量增长。

### 精确施工
改为数据库：
- count（计数）
- order（排序）
- limit/offset（分页）

dataScope（数据范围）在SQL阶段就收敛。

### Gold
pageSize=20只取必要行；
学院A不加载B学院全量后再过滤；
查询次数可测。

---

## C-P1-06 Teacher Today（教师今日工作台）应该成为高频入口

### 当前条件已经具备
可以从正式事实聚合：
- 今日正式课表；
- 正式名单是否就绪；
- 待考勤；
- 调停课变化；
- 监考；
- 成绩待提交/被退回；
- UnifiedTodo（统一待办）。

### 不能做的事
不能新建：
- 第二Task Center（任务中心）；
- 第二Todo（待办）；
- 第二教师课表。

### 正确设计
纯read projection（只读投影）：

首屏：
1. 今天第几节在哪上课；
2. 当前名单多少人；
3. 是否需要点名；
4. 有没有临时调课；
5. 今天/本周监考；
6. 哪些成绩任务快截止/被退回。

### Gold
真实老师从首页到点名不超过3步；
换教师后旧教师立即失去高频入口；
调课后首页自动显示新时间地点；
PC和教师小程序同源。

---

## C-P1-07 成绩截止与催录是运营主链，不应靠人工Excel统计

### 当前基础
GradeTask（成绩任务）已经有正式状态机和Todo（待办）。

### 需核实
当前是否已经存在统一：
- dueAt（截止时间）
- extension（延期）
- isOverdue（是否逾期）
- 退回后的新责任截止

如果缺失：
- 截止属于GradeTask/term policy（成绩任务/学期策略）；
- isOverdue优先派生；
- 不新建“逾期成绩”真值表；
- 催录用Outbox（事务消息箱）dedupe（去重）。

### 必须避免
- 已提交教师还被催；
- 已发布还被催；
- 延期已经批准但旧截止仍报警；
- 批量催办产生消息风暴。

---

## C-P1-08 PR #96（拉取请求）是C线真实工程碰撞

PR #96（教务静态收口拉取请求）当前直接触碰：
- `services/__init__.py（教务服务注册入口）`
- `academic_affairs_registry.py（教务模型注册）`
- 教师小程序grade-entry（成绩录入）页面
- 教师成绩录入测试
- 学期演练工作流

### 规则
C线不能：
- 直接抢两个共享注册文件；
- 在旧PR内容未重读时覆盖教师成绩小程序。

正确流程：
`C业务RED → INT碰撞审计 → 需要共享变更时INT处理 → C同步 → exact-head重跑`

---

# C-1 当前代码Authority（权威真值）地图

## Attendance（考勤）
正式：
`AaAttendanceSession + RosterConsumerSnapshot（考勤场次+名单快照）`

普通教师来源：
`TeachingTask + TeachingRoster（教学任务+正式名单）`

待封：
`Published Occurrence（正式课次）`

## Exam（考务）
正式：
`AaExamBatch/AaExamCourse/AaExamRoom/AaExamRoomStudent/AaExamInvigilator（考试批次/课程/考场/座位学生/监考）`
+
`EXAM_COURSE RosterConsumerSnapshot（考试名单快照）`

## Grade（成绩）
正式：
`AaGradeTask/AaGradeRecord（成绩任务/记录）`
→正式发布投影
→`EffectiveGradePolicy（有效成绩策略）`

## Workload（工作量）
现有正式能力，继续从Task/Schedule/Exam（任务/课表/考试）等正式来源计算/申报，不反向成为教学关系Authority。

---

# C-2 六个持续施工波次

## C-W0 Mature Chain Freeze（成熟链冻结）
先锁：
- Attendance Task/Roster（考勤任务/名单）
- Exam snapshot/publish（考试快照/发布）
- Grade roster/submit/publish（成绩名单/提交/发布）
- EffectiveGrade（有效成绩）
- Correction（更正）

这些测试先全部绿，再动代码。

## C-W1 Published Occurrence（正式课次）与考勤
先证伪已有实现。
缺失才补：
`Task + Schedule Truth + Schedule Change（任务+课表真值+调停课）`

输出：
`C-C1 Attendance Consumer Contract（考勤消费者合同）`

## C-W2 Teacher Today（教师今日）
纯读聚合，不建新真值。

## C-W3 Exam（考务）保护性加固
- 集中/分散考试；
- 打印；
- 监考；
- 异常；
- 通知；
但核心发布门禁不重写。

输出：
`C-C2 Exam Consumer Contract（考务消费者合同）`

## C-W4 Grade（成绩）规模与运营
- SQL分页；
- 截止/催录；
- 大XLSX（Excel工作簿格式）；
- 退回重提；
- 更正复查；
- Workload（工作量）对账。

输出：
`C-C3 Effective Grade Read Contract（有效成绩读取合同）`

## C-W5 C Gold（C线最终验收）
完整教师一天：
`课表 → 点名 → 调课 → 考试/监考 → 录成绩 → 审核退回 → 再提交 → 发布`

同步PR #96碰撞后重新跑。

---

# C-3 MySQL（关系型数据库）验收

- 同一考勤场次重复创建；
- Roster换版与考勤创建并发；
- Exam publish（考试发布）与名单换版并发；
- Grade submit/publish（成绩提交/发布）与名单换版并发；
- 两个管理员/教师重复提交；
- Grade correction（成绩更正）并发；
- EffectiveGrade（有效成绩）唯一当前策略；
- 大XLSX确认期间版本漂移。

---

# C-4 真实学校Gold（最终验收基线）

1. 教师Today显示当前正式课表。
2. 正常点名只用正式Roster。
3. 不存在的日期/节次不能建立普通考勤场次。
4. 调课后旧课次不能点名。
5. 管理员特殊补录明确标来源。
6. Selection未LOCK不能进入正式考勤。
7. Exam确认冻结当前Roster。
8. Roster换版后旧Exam快照不能直接发布。
9. 名单外学生不能铺位。
10. 同学生不能在同一考试重复铺位。
11. 教室容量不足不能发布。
12. 监考不完整不能发布。
13. 发布后普通时间修改被阻断。
14. GradeTask绑定稳定课程版本。
15. 名单外学生不能录正式成绩。
16. 成绩提交冻结Roster快照。
17. Roster换版后旧成绩任务发布冲突。
18. 多次修读无策略时fail-closed。
19. 同名课程成绩不静默合并。
20. 发布后普通编辑失败。
21. 补考/重修/认定后EffectiveGrade唯一。
22. 任务列表真正SQL分页。
23. 换教师后旧教师失去考勤/成绩写权限。
24. 教师Today三步内进入点名。
25. 退回成绩重新产生教师待办。
26. 已提交/已发布成绩不被误催。
27. 5000行成绩导入版本漂移时确认失败。
28. PC与小程序成绩状态一致。
29. PR #96同步后教师小程序测试仍绿。
30. C冻结后D只消费EffectiveGrade等正式证据，不读取草稿成绩。

---

# C-5 自行纠错与反证

1. **纠正“C线应该大改”**：Exam和Grade是当前最强部分，必须保护。
2. **纠正“成绩只是后半模块”**：EffectiveGrade已经成为B先修和D毕业都应该消费的正式跨域事实。
3. **把考勤缺口缩小**：名单链已经对，重点只剩正式课次和管理员特殊旁路。
4. **纠正“工作量是竞品新增能力”**：你仓库已经有正式实现，后续只做来源对账、体验和规模。
5. Teacher Today（教师今日）是高频产品优化，不允许借机新造第二Todo/Task真值。

---

# C-6 最终签字

- Mature Chain（成熟链）0回归；
- 普通考勤正式课次合同明确；
- 特殊考勤旁路隔离；
- Exam核心不退化；
- Grade/EffectiveGrade核心不退化；
- SQL分页完成；
- 教师Today可真实工作；
- 成绩周运营闭环；
- PR #96碰撞安全回收；
- P0=0；
- 本轮P1=0；
- 输出C-C1/C-C2/C-C3三份冻结合同给D。

---

# 附录：V1.5 C线详细业务设计

> 以下保留V1.5的教师工作台、集中/分散考试、异常、工作量、成绩周、LMS（教学平台集成）等详细场景。若与V2.1当前代码裁决冲突，以V2.1为准。

# C — Teaching Execution：教师日常·考勤·调停课·考务·成绩·工作量 — V1.5 四线并行深审增强唯一施工总册

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
本线页面施工矩阵：**19 个工作区/页面任务**。  
本线真实学校验收场景：**50 条最低场景**。

状态分布：
- `CURRENT-HARDEN`：7
- `CURRENT-KEEP/HARDEN`：4
- `CURRENT-KEEP/HARDEN + VERIFY-FIRST(mode)`：1
- `EXISTS-HARDEN`：3
- `VERIFY-FIRST/HARDEN`：1
- `EXISTS-KEEP/HARDEN`：2
- `OPTIONAL-INTEGRATION`：1
- `FINAL-C-LINE-GATE`：1



# Ⅰ. 2026 成熟教务 / SIS 对标证据层

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


# Ⅵ-C. C线 Current Repo Evidence Inventory

- Attendance正常教师路径已经Task-first，并冻结正式Roster snapshot。
- 管理员无Task/class-based人工考勤仍是compat能力，必须显式隔离。
- Exam core/facade已经覆盖Task候选、Roster冻结、考场、座位、监考、巡考、缓考、异常、发布与归档。
- Grade core/service已经覆盖Roster、逐人/批量录分、XLSX、提交、学院审核、教务发布、退回、归档。
- Effective Grade是全系统当前有效成绩的唯一政策层，Credits/GPA/Graduation不得各自选“最新一行”。
- `AaTranscriptView.vue`、学生transcript、小程序transcript、成绩单打印三级施工卡已存在：成绩单不是新增模块。
- `0098_aa_workload_declaration.py + academic_affairs_workload_service.py + AaWorkloadReviewView.vue + test_aa_workload.py`已存在：教师工作量不是新增模块。
- PR #96当前仍触碰`miniapp/.../grade-entry.vue`、academic registry、`services/__init__.py`等；C线修改这些文件前必须重新collision audit。

# Ⅶ. 市场对标 → 当前仓库差距矩阵

| 能力 | 成熟系统/国内场景 | 当前裁决 | V1.5动作 |
|---|---|---|---|
| 教师Today/Faculty Center | PeopleSoft Faculty Center | EXISTS-HARDEN | 统一Today/Todo/Risk |
| 正式考勤名单 | 成熟SIS enrollment roster | CURRENT-KEEP | RosterSnapshot |
| 特殊考勤补录 | 商业纠错 | CURRENT-HARDEN | 与normal path隔离 |
| 调停课/按周换教师 | 国内正方 | CURRENT-HARDEN | occurrence-first change |
| 集中/分散考试 | 国内正方 | VERIFY-FIRST/HARDEN | 复用Exam Authority |
| 考试名单打印 | 国内正方 | EXISTS-HARDEN | 绑定roster snapshot |
| 监考资源 | 国内正方/成熟SIS | CURRENT-HARDEN | 冲突+改派 |
| 成绩录入审核发布 | 成熟SIS通用 | CURRENT-KEEP | 不重写 |
| grading scheme | 成熟SIS通用 | CURRENT-HARDEN | Task config snapshot |
| 成绩逾期/催录 | 成熟教务 | VERIFY-FIRST | Todo+derived overdue |
| 成绩更正/复查 | 成熟SIS通用 | CURRENT-KEEP | append+EffectiveGrade |
| 预警联动 | Academic standing | EXISTS-HARDEN | 不复制Warning |
| 教师工作量 | PeopleSoft/正方 | EXISTS-KEEP | 已实现，补来源对账 |
| 成绩导入 | 商业系统标配 | CURRENT-HARDEN | 规模+回执+版本漂移 |
| 教师小程序录分 | 移动端高频 | EXISTS-HARDEN | 与PC同status/allowedActions |
| LMS集成 | 成熟生态 | OPTIONAL-INTEGRATION | 不进入C Gold主链 |


# Ⅷ-C. C线专题施工卡总表

| 卡号 | 专题 | 当前状态 | 核心复用 | Authority目标 | 前端入口 | 关键门禁 |
|---|---|---|---|---|---|---|
| C01 | Teacher Today | EXISTS-HARDEN | UnifiedTodo + schedule + Exam + Grade | read projection | 教师PC/小程序首页 | 今日事实一致 |
| C02 | 普通考勤正式课次 | CURRENT-HARDEN | Attendance + Task + Roster | PublishedOccurrence consumer | 点名入口 | 不存在课次不可建场次 |
| C03 | 特殊考勤补录 | CURRENT-HARDEN | Attendance compat | ADMIN_SPECIAL source | 管理补录 | 教师不可调用 |
| C04 | 调停课 | CURRENT-HARDEN | Schedule truth + change | occurrence-first | 教师课表/教务台账 | change后旧occurrence失效 |
| C05 | 按周换教师 | CURRENT-HARDEN | TeachingTask + ScheduleChange | occurrence instructor assignment | 周次换教师 | 历史可追溯 |
| C06 | 考务集中/分散模式 | CURRENT-KEEP/HARDEN + VERIFY-FIRST(mode) | Exam Authority | mode on existing batch/course | 考务批次 | 不重写名单/发布 |
| C07 | 考试名单/座位打印 | EXISTS-HARDEN | Exam roster snapshot | print projection | 考务打印 | hash/version水印 |
| C08 | 监考安排/改派 | CURRENT-HARDEN | Exam invigilator | assignment fact | 监考台账 | 冲突/替换并发 |
| C09 | 考试异常 | CURRENT-HARDEN | defer/incident | incident closure | 异常处置 | append/audit |
| C10 | 学生考试查询 | EXISTS-HARDEN | Exam projection | read-only | 学生PC/小程序 | 发布前不可见 |
| C11 | 成绩任务 | CURRENT-KEEP/HARDEN | GradeTask | canonical task | 教师录分 | stable course identity |
| C12 | 成绩SQL分页 | CURRENT-HARDEN | Grade list | SQL limit/offset | 任务列表 | 不all后切片 |
| C13 | 成绩截止/延期/催录 | VERIFY-FIRST/HARDEN | GradeTask + Todo + Outbox | due derived state | 教师/教务 | dedupe/no false reminder |
| C14 | 成绩导入规模 | CURRENT-HARDEN | XLSX import | draft→confirm | 批量录分 | 5k/version drift |
| C15 | 成绩审核退回 | CURRENT-KEEP/HARDEN | Grade state machine | existing | 学院审核 | 重提/待办 |
| C16 | 成绩发布/EffectiveGrade | CURRENT-KEEP/HARDEN | policy service | unique effective truth | 教务发布/学生查询 | fail-closed |
| C17 | 成绩更正/复查 | CURRENT-KEEP/HARDEN | correction/recheck | append-only + effective | 更正/复查 | archived safe |
| C18 | 教师工作量 | EXISTS-KEEP/HARDEN | workload service | derived/accounting fact | 工作量审核 | 来源可对账 |
| C19 | LMS集成 | OPTIONAL-INTEGRATION | current grade authority | adapter only | 配置 | 不写正式成绩真值 |
| C20 | C Gold | FINAL-C-LINE-GATE | all above | evidence bundle | 全端 | MySQL/E2E/scale |


# Ⅸ-C. C线专题施工卡

## C01 Teacher Today / Faculty Center

### CURRENT FACT
- 现有教师PC/小程序已经有教务入口、课表、考勤、成绩、考试等页面或服务。
- UnifiedTodo 已存在。
- 不需要新Task Center。

### HISTORICAL MERGE
保留旧设计中“我的今日课表、待办、风险、快捷动作”的高频结构，但必须全部来自当前Authority。

### BENCHMARK
PeopleSoft Faculty Center证明教师自助应是一致工作台，而不是分散菜单。

### Authority
只读projection：
`TeachingTask + PublishedScheduleOccurrence + TeachingRoster + Attendance + ExamInvigilator + GradeTask + UnifiedTodo`

### UI
首屏顺序：
1. 下一节课；
2. 当前名单/点名状态；
3. 临时调停课；
4. 今日监考；
5. 成绩截止/退回；
6. 快捷操作。

### RED
- 换教师后旧教师首页不再显示该课。
- 调课后旧时间消失、新时间出现。
- Roster未就绪显示阻断，不显示“开始点名”。
- GradeTask退回后出现教师待办。

### Gold
从教师首页到真实点名≤3次点击。

---

## C02 普通考勤正式课次合同

### CURRENT FACT
Attendance正常教师路径已经 Task + current term + teacher + Roster snapshot。

### GAP
仍需证明普通session是否校验PublishedOccurrence。

### Authority
`Task + PublishedOccurrence + RosterSnapshot`

### RED
- 非正式日期/slot创建失败；
- 停课日失败；
- 调课旧时间失败；
- 补课新时间成功；
- 单双周错误失败。

### DB
若存occurrence identity，必须stable且可追溯；不允许只存展示字符串。

### API
create session必须返回：
- occurrence identity；
- sourceType=NORMAL；
- rosterVersionId；
- scheduleRevision/hash；
- allowedActions。

### UI
点名页显示正式课程/时间/地点/名单版本；不能允许教师自由造sessionDate+slot。

### MySQL
同occurrence重复创建必须唯一/幂等。

---

## C03 管理员特殊考勤补录

### CURRENT FACT
现有compat path允许admin按行政班创建。

### Authority
不新建第二Attendance表，只扩现有session事实的source语义。

### sourceType
至少：
- `NORMAL`；
- `ADMIN_SPECIAL`；
- 如迁移确需，`MIGRATED_LEGACY`。

### ADMIN_SPECIAL必填
- reason；
- evidence/ref；
- operator；
- source context；
- 可关联Task则关联。

### Permission
独立高权限，不归普通teacher attendance.write。

### UI
管理端明显显示“特殊补录”，教师端不出现入口。

### RED
普通教师伪造sourceType必须403/422。

---

## C04 调停课 occurrence-first

### CURRENT FACT
仓库已有ScheduleChange/调停课，不重建。

### 目标
把变化落实到“具体occurrence”，而不是只改一个长期模板后丢历史。

### 场景
- 单次调课；
- 多周调课；
- 停课；
- 补课；
- 换教室；
- 换节次；
- 跨日；
- 法定节假日特殊补课。

### Authority
读取仍以正式Schedule ScopeHead为基线，change只做受控覆盖。

### RED
- change生效后旧occurrence不可再建立普通attendance；
- 学生/教师课表显示新时间；
- 考试/成绩不因课表change改写课程身份。

### Concurrency
同时两条互斥change必须409/版本冲突。

---

## C05 按周换教师 / Temporary Instructor

### CURRENT FACT
TeachingTask是长期正式教学关系Authority。

### 业务需求
国内教务常见“第8周后由教师B接课”“第5周临时代课”。

### Authority
不能直接覆盖Task主教师导致前7周历史消失。
优先：occurrence-level instructor assignment / schedule change extension。

### RED
- 历史考勤显示当时教师；
- 当前周仅有效教师可点名；
- 长期工作量按规则归属；
- 旧教师失去未来occurrence写权限。

### UI
教师课表明确显示“代课/变更”。

---

## C06 集中 / 分散考试模式

### VERIFY-FIRST
先查当前Exam模型/路由是否已有mode/type字段或隐式能力。

### 模式
- 集中考试：统一批次、集中排考场/监考；
- 分散考试：课程/学院在约束窗口内自行组织，但仍必须进入正式Exam Authority。

### 禁止
为分散考试另建第二套Exam表。

### Publish Gate
两种模式都必须满足：
- Task；
- Roster snapshot；
- 时间；
- 地点/允许的场地语义；
- 人数/容量；
- 监考/责任人；
- 发布版本。

---

## C07 考试名单 / 座位 / 监考打印

### Authority
打印只消费已冻结Exam roster snapshot和当前已发布版本。

### 输出
至少：
- 考试名单；
- 座位表；
- 门贴/考场信息；
- 监考安排表；
- 异常记录空表/签到表（若学校需要）。

### Watermark
- tenant/school；
- term；
- batch；
- version/hash；
- printedAt；
- operator。

### RED
Roster换版后旧打印必须明确“历史版本/非当前”，不能伪装当前。

---

## C08 监考安排 / 改派

### CURRENT FACT
Exam已有invigilator资源。

### 补强
- 教师时间冲突；
- 跨考场重复；
- 改派；
- 缺岗；
- 临时替换；
- 监考确认。

### Authority
仍是Exam invigilator assignment，不新建第二Roster。

### Concurrency
两管理员同时改同一监考位：版本冲突。

### UI
教师Today显示今日/本周监考。

---

## C09 考试异常闭环

### 场景
- 缺考；
- 违纪；
- 作弊；
- 设备/场地故障；
- 试卷问题；
- 缓考；
- 临时停考/重排。

### Authority
复用现有Exam incident/defer能力；若当前只有一部分，优先扩状态/子事实，不新Exam系统。

### 审计
异常append-only；关闭必须有责任人、结论、时间、证据。

### 联动
- Grade读取缓考/缺考正式事实；
- Graduation最终只读EffectiveGrade，不直接读Exam incident做第二结论。

---

## C10 学生考试查询

### Authority
只读已发布Exam projection。

### UI
学生必须看到：
- 课程；
- 日期/时间；
- 考场；
- 座位；
- 状态；
- 变更通知；
- 缓考结果；
- 考试须知。

### Security
- 不能看到他人座位敏感信息全集；
- 未发布考试不可见；
- tenant隔离。

---

## C11 成绩任务稳定身份

### CURRENT FACT
已很成熟：Task+stable courseId/version+Roster。

### KEEP
- 课程名称只能snapshot；
- roster version冻结；
- submit/publish状态机；
- admin supplement来源语义。

### HARDEN
grading scheme配置必须快照或版本化，不能发布后学校改规则导致历史成绩重算。

### RED
发布后规则变化不改历史已发布分数/等级语义。

---

## C12 成绩任务SQL分页

### CURRENT FACT
当前存在 `.all()` 后Python切片风险。

### 施工
- SQL COUNT；
- ORDER BY stable fields；
- LIMIT/OFFSET或cursor；
- dataScope进入SQL；
- 避免N+1。

### RED
可通过SQLAlchemy query instrumentation断言只取pageSize数量级数据。

### MySQL规模
10万任务历史、pageSize20仍稳定。

---

## C13 成绩截止 / 延期 / 催录

### VERIFY-FIRST
先查GradeTask是否已有dueAt/related policy。

### 若已有
HARDEN，不新字段重复。

### 若缺失
截止挂在Task或Term policy，不新建OverdueTruth表。

### 状态
`isOverdue`优先派生：
当前时间 > effectiveDueAt 且任务仍处于需教师动作状态。

### Extension
延期必须有：
- approvedBy；
- reason；
- previousDueAt；
- newDueAt；
- audit。

### Reminder
Outbox dedupe key含：
`tenant + task + reminderType + effectiveDueVersion`

### RED
- submitted/published不提醒；
- approved extension不按旧截止提醒；
- returned任务按新责任截止计算。

---

## C14 成绩批量导入 / 大 XLSX

### CURRENT FACT
已有成绩XLSX能力。

### 目标
5000行真实教师成绩导入：
`template → parse → validate → staging/draft → error workbook → confirm → receipt`

### 键
正式匹配优先：
- taskId；
- studentId/studentNo within frozen roster；
- course stable identity来自Task，不由Excel自由填。

### 禁止
- 课程名称作为正式join；
- 名单外学生自动插入；
- confirm前直接写正式记录。

### Version Drift
confirm时重验：
- task version；
- roster version；
- grading scheme version；
- task status。

漂移则整批失败/要求重预览。

### Gold
5000行+错误行工作簿+幂等重放。

---

## C15 成绩审核 / 退回 / 重提

### CURRENT FACT
状态机已存在。

### HARDEN
退回必须：
- reason；
- reviewer；
- reviewedAt；
- teacher todo；
- resubmission history。

### UI
教师明确看到：
- 哪些学生有问题；
- 退回原因；
- 当前允许动作；
- 截止/延期。

### RED
旧教师/非任课教师不可重提。

---

## C16 发布 / EffectiveGrade

### CURRENT FACT
这是当前最强Authority之一。

### KEEP
- multi-attempt policy；
- active policy；
- snapshot/hash；
- name-only legacy fail-closed；
- publish revalidate roster。

### 跨线合同
输出给B：
`PrerequisiteEffectiveGradeRead`
输出给D：
`GraduationEffectiveGradeRead`

两者都不得直接读取AaGradeRecord最新一行。

### RED
- 重修/补考后有效成绩唯一；
- 无policy fail-closed；
- 同名课程不同stable id不合并。

---

## C17 成绩更正 / 复查 / 归档后纠错

### CURRENT FACT
仓库已有correction/recheck强事实链。

### KEEP
不得改成直接UPDATE正式发布成绩。

### 工作流
`申请 → 复核 → 决定 → append correction → EffectiveGrade recompute/policy resolution → transcript/graduation projection invalidation/recompute`

### Archived
归档后允许的纠错必须：
- 独立高权限；
- append-only；
- archive amendment ledger；
- 不静默改历史。

---

## C18 教师工作量

### CURRENT FACT
已有migration/service/page/test。

### 不是新增模块
后续只做：
- 来源对账；
- 规模；
- 规则可解释；
- 学院审核；
- 锁定/结算。

### 来源
优先读取正式：
- TeachingTask；
- Published schedule；
- 发生的schedule changes；
- Exam invigilation；
- 允许计入的指导/实践事实。

### 禁止
工作量申报反向修改Task/课表。

---

## C19 LMS / 教学平台集成

### OPTIONAL-INTEGRATION
不是C Gold阻断。

### 原则
- LMS成绩只能作为草稿/参考/待确认来源；
- 正式成绩仍经GradeTask writer；
- 外部course mapping版本化；
- roster来自本SIS，不允许LMS自创正式名单。

### 接口
adapter/outbox/inbound receipt，不把外部API写入核心服务。

---

## C20 C-Line Gold Gate

### 连续教师日
`Teacher Today → 课表 → 名单 → 点名 → 调课变化 → 监考 → 成绩录入 → 提交 → 学院退回 → 教师修正 → 再提交 → 教务发布 → 学生查成绩 → 更正/复查 → EffectiveGrade`

### Gate
- exact-head；
- MySQL；
- PC + miniapp；
- teacher replacement；
- roster version race；
- screenshot visual audit；
- real-click E2E；
- no mock；
- PR96 collision absorbed。

---

# Ⅹ-C. C线页面 / 工作区施工矩阵

| 页面/工作区 | 主角色 | 第一结论 | Authority | 高频动作 | 异常/阻断 | 移动端 |
|---|---|---|---|---|---|---|
| Teacher Today | 教师 | 下一节课/待办 | read projection | 点名/监考/录分 | 名单未就绪 | 必须 |
| 教师课表 | 教师 | 当前正式课表 | Published Schedule | 查看/进入点名 | 调课变更 | 必须 |
| 考勤创建/点名 | 教师 | 本课次可否点名 | Task+Occurrence+Roster | 点名/提交 | 非正式课次 | 必须 |
| 考勤管理补录 | 教务 | 特殊补录原因 | Attendance special | 补录 | 高权限 | PC |
| 调停课台账 | 教务/教师 | 哪些课已变化 | ScheduleChange | 审批/查看 | 冲突 | 教师可看 |
| 考试批次 | 教务 | 当前批次完整性 | ExamBatch | 配置/发布 | 缺资源 | PC |
| 考场/座位 | 教务 | 容量/铺位状态 | ExamRoom | 自动/手工铺位 | 容量不足 | PC |
| 监考安排 | 教务 | 缺岗/冲突 | Invigilator | 安排/改派 | 时间冲突 | 教师可看 |
| 考试异常 | 教务/学院 | 未闭环异常 | Incident | 处置/关闭 | 证据缺失 | 部分 |
| 学生考试查询 | 学生 | 我的考试时间地点 | published projection | 查看 | 未发布 | 必须 |
| 成绩任务列表 | 教师/学院/教务 | 哪些任务要处理 | GradeTask | 进入/催录/审核 | 逾期/退回 | 教师必须 |
| 成绩录入 | 教师 | 当前允许动作 | GradeTask+Roster | 单条/批量/XLSX | 名单外/已发布 | 必须 |
| 成绩审核 | 学院 | 待审/问题任务 | GradeTask | 通过/退回 | 数据异常 | PC |
| 成绩发布 | 教务 | 可发布任务 | GradeTask+EffectivePolicy | 发布 | roster漂移 | PC |
| 成绩更正 | 教务/教师 | 更正流程状态 | Correction | 申请/审批 | 已归档 | PC |
| 成绩复查 | 学生/教务 | 复查进度 | Recheck | 申请/处理 | 超期 | 学生可查 |
| 工作量 | 教师/学院 | 本周期工作量 | Workload | 申报/审核 | 来源不一致 | PC优先 |
| 成绩单 | 学生/教务 | 当前正式成绩 | EffectiveGrade | 查看/打印 | 历史修读 | 必须 |
| 教务成绩运营 | 教务 | 逾期/催录/退回统计 | GradeTask projection | 批量提醒 | 消息风暴 | PC |


# Ⅺ-C. 权限 / 数据范围 / 审计矩阵

## 教师
- 只看自己的Task/occurrence/Exam invigilation/GradeTask；
- 只写正式分配给自己的考勤/成绩；
- teacher replacement后未来写权限即时失效。

## 学院教务员
- college dataScope；
- 可审核成绩、查看考勤/考试、处理授权范围内异常；
- 不得跨学院读取敏感成绩明细。

## 学校教务
- school scope；
- Exam publish、Grade publish、special attendance、correction等高风险权限拆分。

## 学生
- 只读自己的published exam/effective grade/recheck。

## 审计动作
必须包含：
- special attendance；
- schedule change；
- exam publish；
- invigilator replacement；
- grade submit/reject/publish；
- extension；
- reminder batch；
- correction/recheck；
- workload approval。


# Ⅻ-C. MySQL / 并发 / 幂等矩阵

1. 同一正式occurrence重复attendance session创建；
2. attendance create与Roster换版并发；
3. schedule change与attendance create并发；
4. 两管理员同时改监考位；
5. exam publish与Roster换版；
6. seat auto-assign重复重放；
7. grade submit双击；
8. grade approve与teacher resubmit竞态；
9. grade publish与Roster换版；
10. correction双审批；
11. effective policy切换与成绩发布；
12. 5k XLSX confirm与task version漂移；
13. reminder worker重复消费；
14. workload settlement重复确认。

每一项必须验证：
- 单赢家/幂等；
- 无半写；
- 状态可解释；
- 锁顺序稳定；
- deadlock可重试且不重复副作用。


# ⅩⅢ-C. 导入 / 打印 / 通知 / Outbox

## 导入
- Grade XLSX：staging + confirm + receipt；
- Exam学生/座位不允许绕Roster快照导入正式事实；
- Workload导入若存在只能进入申报草稿，不覆盖来源Authority。

## 打印
- Exam roster/seat/invigilation；
- transcript/grade sheet；
- attendance record；
- workload statement；
必须带tenant/term/version/hash/printedAt。

## 通知
- 调课；
- 考试发布/变更；
- 监考安排/改派；
- 成绩截止/催录/退回；
- 成绩发布；
- 复查结果。

全部Outbox dedupe；失败可重试；不得事务内直接发外部短信/邮件。


# ⅩⅣ-C. 可观测性 / Scale（规模）

## Metrics
至少：
- attendance_session_create_total{sourceType,result}
- attendance_occurrence_block_total{reason}
- exam_publish_total{result,reason}
- invigilator_conflict_total
- grade_task_overdue_total
- grade_submit_total{result}
- grade_publish_total{result,reason}
- grade_import_rows_total{result}
- grade_reminder_total{result}
- grade_correction_total{result}
- effective_grade_resolution_total{policy,result}

## Scale Gold
- 20k教师Today并发读取应是projection/索引化，不N+1；
- 10万GradeTask历史分页稳定；
- 5k成绩XLSX；
- 大批考试名单/座位打印；
- reminder批量分页/节流；
- teacher miniapp弱网恢复。


# ⅩⅤ-C. C线真实学校最低验收场景（50条）

## 教师Today / 课表 / 考勤
1. 教师登录看到今日第一节正式课；
2. 当前名单人数与Roster一致；
3. 正式课次可进入点名；
4. 非正式日期不可建普通考勤；
5. 调课后旧时间不可点名；
6. 新时间可点名；
7. 单双周错误周被拒；
8. 节假日停课不生成普通考勤；
9. 补课日可生成；
10. 换教师后旧教师失权；
11. 新教师看到未来课次；
12. Roster换版并发时session安全失败/绑定正确版本；
13. 管理员特殊补录显示source；
14. 普通教师无法special补录；
15. 点名后刷新仍持久。

## 考务
16. 创建正式ExamBatch；
17. 选择Task并冻结Roster；
18. 名单外学生不可铺位；
19. 同学生同课程不可重复座位；
20. 容量不足阻断；
21. 监考缺失阻断；
22. 教师时间冲突阻断/提示；
23. 改派监考后旧教师Today更新；
24. 集中考试发布；
25. 分散考试若启用仍走同Authority；
26. 发布后学生看到考试；
27. 未发布学生看不到；
28. 缓考状态正确；
29. 违纪/异常有闭环；
30. 打印名单带version/hash。

## 成绩
31. 教师只能看到自己的GradeTask；
32. task绑定stable course version；
33. 正式Roster成员可录；
34. 名单外不可录；
35. 5k XLSX预检；
36. 错误行生成错误工作簿；
37. roster漂移后confirm失败；
38. submit冻结snapshot；
39. 学院可审核；
40. 退回后教师看到原因；
41. 退回重新产生Todo；
42. 教师重提；
43. publish前再次校验Roster；
44. publish后普通编辑失败；
45. 多修读无policy时fail-closed；
46. active policy决定唯一EffectiveGrade；
47. 补考/重修后成绩单正确；
48. correction不直接UPDATE历史；
49. 已提交/发布不被误催；
50. PC/miniapp/学生成绩单一致。


# ⅩⅥ-C. C线实施与学校交付清单

上线前学校必须确认：
- 考勤是否按课次管理；
- 特殊活动/历史补录权限；
- 调停课审批制度；
- 是否支持按周换教师；
- 集中/分散考试制度；
- 考场容量与资源；
- 监考改派规则；
- 缓考/违纪流程；
- 成绩构成与grading scheme；
- 成绩提交/审核/发布职责；
- 截止/延期/催录规则；
- 补考/重修有效成绩规则；
- 更正/复查期限；
- 工作量计算/结算规则；
- 打印模板；
- 消息渠道。


# ⅩⅦ-C. C线施工顺序（持续施工）

```text
C-W0 Mature Chain Freeze
↓
C01 Teacher Today evidence map
↓
C02 Published Occurrence attendance
↓
C03 ADMIN_SPECIAL isolation
↓
C04/C05 schedule change + teacher replacement
↓
C06 Exam mode verify
↓
C07/C08 print + invigilation
↓
C09/C10 incident + student projection
↓
C11/C12 Grade stable identity + SQL pagination
↓
C13 overdue/extension/reminder
↓
C14 5k XLSX
↓
C15 review/return/resubmit
↓
C16 EffectiveGrade cross-line contract
↓
C17 correction/recheck
↓
C18 workload reconciliation
↓
C19 optional LMS adapter
↓
C20 C-Line Gold
```


# ⅩⅧ-C. C线最终 DoD

- 当前成熟Attendance/Exam/Grade/EffectiveGrade全部0回归；
- 普通考勤只能绑定正式occurrence；
- ADMIN_SPECIAL独立权限/来源/审计；
- 调课/换教师后Today与点名立即正确；
- 集中/分散考试复用同一Exam Authority；
- Exam打印/监考/异常可真实工作；
- GradeTask SQL分页；
- 截止/延期/催录不误报；
- 5k XLSX可验收；
- EffectiveGrade仍是唯一当前成绩；
- correction/recheck append-only；
- workload来源可对账；
- Teacher Today ≤3步到点名；
- PC/教师小程序一致；
- screenshot visual audit完成；
- real-click E2E完成；
- MySQL concurrency/scale全绿；
- PR #96碰撞最终exact-head重验；
- C-C1/C-C2/C-C3冻结给D消费。


# ⅩⅨ-C. C线最终反证清单

开PR进入最终评审前，必须主动证明以下“不会发生”：
1. 教师能给不存在的课次点名；
2. 调课后旧课次仍可写；
3. admin special被教师利用绕Roster；
4. 考务名单脱离Roster snapshot；
5. 监考不完整仍发布；
6. 名称成为Grade主身份；
7. 成绩列表全量all到内存；
8. overdue提醒已完成任务；
9. XLSX confirm忽略roster drift；
10. correction直接覆盖历史；
11. EffectiveGrade多条并存为“当前”；
12. Teacher Today成为第二Task/Todo系统；
13. miniapp自己发明成绩状态；
14. shared registry被C线抢占；
15. PR #96 UI改动被静默覆盖。


# ⅩⅩ-C. C线“施工中状态标签”规范

施工地图中只能使用：
- `NOT_STARTED`
- `CURRENT_FACT_PROVEN`
- `RED_READY`
- `BACKEND_GREEN_UI_OPEN`
- `UI_IMPLEMENTED_VISUAL_OPEN`
- `VISUAL_GREEN_E2E_OPEN`
- `EVIDENCE_STALE`
- `UI_E2E_BLOCKED`
- `COMPLETED`

禁止使用“基本完成、差不多、应该好了、看起来通过”。


# ⅩⅪ-C. C线施工记录模板

每个Wave至少记录：

```text
Wave:
Base exact-head:
Working exact-head:
Current fact:
Historical docs read:
Source files read:
Tests read:
Authority reused:
RED added:
Backend fix:
Targeted tests:
KEEP regression:
MySQL:
Frontend consumers:
Frontend Impact Matrix:
Before screenshots:
After screenshots:
Visual audit findings:
Real-click E2E:
Refresh/relogin/role-change:
CI run/job:
Collision recheck:
Evidence exact-head:
Final status:
Next safe entry:
```


# ⅩⅫ-C. C线开发者“禁止提交”清单

以下情况禁止提交为Gold：
- 只改后端未同步UI；
- 只改UI未改Authority；
- 用mock教师/学生数据截图；
- 用SQLite代替MySQL；
- 测试把核心失败改成xfail；
- 为了通过考试/成绩测试恢复name-only identity；
- 直接写shared registry；
- 复制PR #96旧grade-entry覆盖新版本；
- 把视觉问题写进known-issue后结束；
- 只跑API不做真实点击。


# ⅩⅩⅢ-C. C线跨端语义一致性

所有端对同一事实必须同义：

| 事实 | 管理PC | 教师PC | 教师小程序 | 学生PC/小程序 |
|---|---|---|---|---|
| 课次取消 | 已停课 | 本课已停 | 已停课 | 课程变更 |
| 调课 | 新时间/地点 | 新时间/地点 | 新时间/地点 | 新时间/地点 |
| 名单未就绪 | 阻断原因 | 暂不可点名 | 暂不可点名 | N/A |
| 成绩退回 | 待教师重提 | 退回待修改 | 退回待修改 | 不显示草稿 |
| 成绩逾期 | 逾期 | 已逾期 | 已逾期 | N/A |
| 成绩延期 | 新截止 | 已延期 | 已延期 | N/A |
| 成绩已发布 | 已发布 | 只读 | 只读 | 正式成绩 |
| Exam未发布 | 草稿/未发布 | 视权限 | 视权限 | 不可见 |


# ⅩⅩⅣ-C. C线 Final Gold Evidence Bundle

最终PR必须能一眼定位：
- 当前exact SHA；
- C-W0～C-W5结果；
- C01～C20卡状态；
- C-C1/C-C2/C-C3合同；
- MySQL报告；
- 5k XLSX artifact；
- visual截图目录/CI artifact；
- real-click E2E run；
- permission/dataScope negative；
- PR96 collision result；
- unresolved review threads=0；
- main race check；
- final merge readiness。


# ⅩⅩⅤ-C. C线“下一安全入口”规则

每个Wave结束后只能写一个next safe entry：

- 若后端未绿：继续当前RED；
- 若后端绿UI未闭环：停留当前Wave做UI，不跳下一Wave；
- 若UI/E2E证据过期：先重验；
- 若shared collision出现：移交INT，不私改；
- 若PR96影响本Wave：先同步最新diff；
- 只有当前Wave `COMPLETED` 才进入下一Wave。
