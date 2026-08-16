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
| 教师工作量 | PeopleSoft/正方 | EXISTS-KEEP | 已有正式能力 |
| LMS integration | PeopleSoft | OPTIONAL | Outbox边界 |
| 大批成绩导入 | 商业教务必需 | CURRENT-KEEP/HARDEN | File Exchange+Roster hash |

# Ⅵ. V1.5 深度施工卡


---

## C15-01 — 教师 Today / Faculty Center 工作台

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** PeopleSoft Faculty Center和成熟教师门户都把课表、名单、成绩、考试任务聚合到教师当天工作。

### 1. 学校业务问题
- 老师不应从十几个菜单寻找点名、监考和成绩任务。
- 移动端最重要的是‘今天我要做什么’。

### 2. 当前 exact-head 事实
- 教师miniapp已有教务首页、my-schedule、attendance、grade-entry；UnifiedTodo存在。

### 3. 历史设计 Reconciliation
- 旧V2已指出移动端是图标目录而非任务首页，HISTORICAL-VALID。

### 4. 唯一 Authority 决策
- 纯读聚合Task/Schedule/Roster/Exam/Grade/Todo，不建第二TaskCenter。
- 局部source失败必须显示unknown/traceId，不能整页假绿。

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
- 教师换人后旧教师仍看到Today Task RED。
- 无scope却聚合全校RED。
- 今日调课后仍显示旧地点RED。
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

## C15-02 — 考勤正式 Roster Snapshot 封板

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN`  
**外部成熟度信号：** 成熟SIS attendance roster来自正式enrollment roster。

### 1. 学校业务问题
- 名单变化不能让已提交考勤静默换学生。
- 教师需要看到名单版本和来源。

### 2. 当前 exact-head 事实
- Attendance normal path已Task-first；RosterConsumerSnapshot支持ATTENDANCE_SESSION。

### 3. 历史设计 Reconciliation
- 旧考勤设计归并到current snapshot协议。

### 4. 唯一 Authority 决策
- AttendanceSession+frozen RosterConsumerSnapshot是历史依据；不从StudentProfile动态回算。
- Roster not ready直接BLOCKED。

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
- Selection未LOCK却能建正式考勤RED。
- Roster stale仍提交RED。
- 同occurrence重复session RED。
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

## C15-03 — 管理员特殊人工考勤 / 历史补录隔离

**优先级：** `P1`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 商业教务可以有纠错能力，但必须和教师正常链隔离。

### 1. 学校业务问题
- 无Task历史数据或特殊场次可能需补录。
- 如果入口混在正常教师链，就成为绕过Roster的后门。

### 2. 当前 exact-head 事实
- attendance service存在admin class-based/no-task compat路径。

### 3. 历史设计 Reconciliation
- V1.3已要求特殊人工场次显式隔离。

### 4. 唯一 Authority 决策
- 保留compat但标SPECIAL_ADMIN；reason/evidence/operator必填。
- 能关联Task/Roster时必须关联，不能覆盖正常session。

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
- 普通教师调用特殊入口RED。
- 无reason成功RED。
- 覆盖正常场次RED。
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

## C15-04 — 调停课 / 教室故障 / 按周换教师正式变更

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 国内正方实际包含调停课申请、按周换教师；成熟系统保留schedule change history。

### 1. 学校业务问题
- 正式课表发布后现实仍会变化，但不能直接UPDATE旧item。
- 师生必须及时得到新安排。

### 2. 当前 exact-head 事实
- AaScheduleChange存在；ScopeHead、Task、Teacher relation已存在。

### 3. 历史设计 Reconciliation
- 历史调停课审批流程继续有效，旧自由拼课程方式废弃。

### 4. 唯一 Authority 决策
- 变更以Published Schedule occurrence为对象，先preview conflict/affected users再审批。
- 旧publish evidence不改，新resolver读取变更后effective occurrence。

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
- 并发两变更RED。
- 批准时新教室已冲突RED。
- 旧教师权限未撤RED。
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

## C15-05 — 集中考试 / 分散考试模式

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN + VERIFY-FIRST(mode)`  
**外部成熟度信号：** 国内正方真实上线明确区分集中、分散考试。

### 1. 学校业务问题
- 不同课程组织方式不同，但都必须受正式名单和发布完整性保护。

### 2. 当前 exact-head 事实
- Exam core/facade已覆盖Task、Roster freeze、room/seat/invigilator/publish。
- 显式CENTRALIZED/DECENTRALIZED mode完备度需exact-head核。

### 3. 历史设计 Reconciliation
- 历史考务施工包可补页面、打印和业务模式细节，不新建Exam truth。

### 4. 唯一 Authority 决策
- ExamCourse+RosterConsumerSnapshot仍唯一名单；mode只决定readiness规则。
- 分散考试也不能绕过服务器final check。

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
- 分散模式缺最小必要字段仍publish RED。
- 跨模式资源冲突未拦RED。
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

## C15-06 — 考试名单 / 座位表 / 监考表打印交付

**优先级：** `P0`  
**V1.5 裁决：** `EXISTS-HARDEN`  
**外部成熟度信号：** 国内高校正方上线把考试名单打印、监考安排作为正式业务。

### 1. 学校业务问题
- 现场考试需要可离线执行的名单/座位/监考材料。
- 打印必须绑定正式名单版本。

### 2. 当前 exact-head 事实
- Exam已有room/student/invigilator；导出/打印完备度需结合current export核。

### 3. 历史设计 Reconciliation
- 历史打印导出模板设计可吸收水印、版本、下载审计。

### 4. 唯一 Authority 决策
- 打印只是Published Exam projection，不建纸面名单truth。
- 文档必须含examBatch/course/room/time/rosterSnapshot/version/generatedAt。

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
- draft考试生成正式抬头材料RED。
- 名单人数!=snapshot RED。
- 跨scope下载RED。
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

## C15-07 — 监考资格 / 冲突 / 改派闭环

**优先级：** `P1`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 成熟教务把监考教师当正式考试资源；国内高校有监考任务和调换。

### 1. 学校业务问题
- 教师不能同一时间上课又监考，也不能两场重叠。
- 临时改派要有历史。

### 2. 当前 exact-head 事实
- Exam已有AaExamInvigilator和资源冲突；Teacher Schedule可作为冲突输入。

### 3. 历史设计 Reconciliation
- 旧监考施工卡重新纳管。

### 4. 唯一 Authority 决策
- AaExamInvigilator继续唯一分配事实；改派追加change/audit。
- Workload只消费监考事实。

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
- 同教师同时间双场RED。
- 与本人正式课程冲突未拦RED。
- 改派后旧教师仍收到任务RED。
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

## C15-08 — 考试异常 / 缺考 / 违纪 → 后续处置

**优先级：** `P1`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 成熟考试管理不会止于incident记录，而要连接缓考、成绩资格和纪律处置。

### 1. 学校业务问题
- 缺考/违纪会影响成绩或后续流程。
- 只有incident没有责任去向会形成归档悬空。

### 2. 当前 exact-head 事实
- Exam core已有incident/defer；处分事实可能属于Student Affairs，不能复制。

### 3. 历史设计 Reconciliation
- 历史考务异常设计可补状态/证据/通知。

### 4. 唯一 Authority 决策
- ExamIncident记录现场事实；后续resolution引用外部处分/成绩政策。
- D/C线不复制Student Affairs处分Authority。

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
- 重大incident未解决却Exam finish/archive RED。
- 纪律处分旁路复制RED。
- 重复incident无幂等RED。
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

## C15-09 — 成绩录入组件 / Grading Scheme

**优先级：** `P1`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN`  
**外部成熟度信号：** 成熟SIS支持不同课程评分构成和grading scheme。

### 1. 学校业务问题
- 不同课程可能平时/期中/期末/项目权重不同。
- 教师需要可理解的质量校验。

### 2. 当前 exact-head 事实
- GradeTask/Record、固定/动态组件相关能力、Effective Grade均已存在。

### 3. 历史设计 Reconciliation
- 旧V2曾提出动态组件双轨；current exact-head需判哪些已落地，已落地标HISTORICAL-MERGED。

### 4. 唯一 Authority 决策
- GradeTask配置是本任务评分规则快照；Published Grade/EffectiveGrade不变。
- 前端表头不是规则Authority。

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
- 权重非法RED。
- submit后规则变化RED。
- XLSX模板与任务config不一致RED。
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

## C15-10 — 成绩录入截止 / 逾期 / 催录 / 延期

**优先级：** `P1`  
**V1.5 裁决：** `VERIFY-FIRST/HARDEN`  
**外部成熟度信号：** 成熟Student Records会有grading截止和逾期治理；学校日常最常见问题之一就是迟交成绩。

### 1. 学校业务问题
- 教务需要知道谁未提交、谁被退回、谁逾期。
- 催录不能误催已提交教师。

### 2. 当前 exact-head 事实
- GradeTask有状态/工作台；UnifiedTodo/消息基础已有。
- deadline/lapse policy当前完备度需精审。

### 3. 历史设计 Reconciliation
- 历史首页/待办设计可吸收。

### 4. 唯一 Authority 决策
- dueAt/extension只属于GradeTask/policy；isOverdue优先作为projection。
- 延期若需审批走独立override，不改成绩状态机。

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
- 已提交仍被催RED。
- 重复催办消息风暴RED。
- 延期越权RED。
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

## C15-11 — 成绩更正 / 复查 / 版本追溯

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN`  
**外部成熟度信号：** 正式成绩发布后成熟SIS使用受控grade change，不直接覆盖。

### 1. 学校业务问题
- 学生复查和教务更正需要完整历史。
- 更正会影响学分、GPA、毕业。

### 2. 当前 exact-head 事实
- Grade recheck/correction、EffectiveGrade、PostArchiveCorrectionCase已有。

### 3. 历史设计 Reconciliation
- 旧成绩状态机和更正施工卡标HISTORICAL-MERGED。

### 4. 唯一 Authority 决策
- Published Grade不删；Correction追加，EffectiveGrade选择当前有效。
- 归档后只走PostArchiveCorrectionCase。

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
- 发布后普通edit成功RED。
- 双EffectiveHead RED。
- 归档后绕过Case RED。
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

## C15-12 — 期中不及格 / 学业预警联动

**优先级：** `P1`  
**V1.5 裁决：** `EXISTS-HARDEN`  
**外部成熟度信号：** PeopleSoft等成熟体系把academic standing/deficiency与正式成绩事实联动。

### 1. 学校业务问题
- 学生风险应尽早发现，但预警处置不能复制在Grade域。

### 2. 当前 exact-head 事实
- AcademicWarning/Intervention/UnifiedTodo已有；Grade可作为证据provider。

### 3. 历史设计 Reconciliation
- 旧全业务总册明确AcademicWarning是预警处理唯一事实，这一分域继续有效。

### 4. 唯一 Authority 决策
- Grade只发事件/提供证据；Warning Authority决定状态和干预。
- 不建AaGradeWarning。

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
- 成绩更正后旧预警不reconcile RED。
- 同rule重复warning RED。
- Grade直接关闭Warning RED。
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

## C15-13 — 教师工作量从正式教学事实计算

**优先级：** `P1`  
**V1.5 裁决：** `EXISTS-KEEP/HARDEN`  
**外部成熟度信号：** PeopleSoft有Instructor Workload；国内正方还做理论/实验/实践/监考工作量和结算。

### 1. 学校业务问题
- 工作量可能用于绩效，必须追溯到Task/Schedule/Exam。
- 不能让教师自己填一个不可核对总数。

### 2. 当前 exact-head 事实
- 0098 workload migration、academic_affairs_workload_service、AaWorkloadReviewView、test_aa_workload均存在。

### 3. 历史设计 Reconciliation
- 旧工作量设计标HISTORICAL-MERGED，重点转成与current事实对账。

### 4. 唯一 Authority 决策
- Workload是下游计算/申报事实，不反向成为任课Authority。
- 按周换教师、课程取消、监考都要改变来源明细。

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
- 课程取消仍计工作量RED。
- 按周换教师未拆分RED。
- finalized后源事实静默改总数RED。
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

## C15-14 — LMS / 外部教学平台集成边界

**优先级：** `P2`  
**V1.5 裁决：** `OPTIONAL-INTEGRATION`  
**外部成熟度信号：** PeopleSoft官方把LMS integration列为Student Records主要能力之一。

### 1. 学校业务问题
- 学校可能使用超星/智慧树等平台同步课程、名单或链接。
- 核心教务必须在无LMS时独立工作。

### 2. 当前 exact-head 事实
- 仓库有部分外部平台能力；统一LMS sync Authority需exact-head核。

### 3. 历史设计 Reconciliation
- 历史集成设计只保留接口边界。

### 4. 唯一 Authority 决策
- Task/Roster/Grade是本系统source of truth；LMS是consumer/provider。
- 外部回传成绩先进入受控import/recognition，不直接覆盖Published Grade。

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
- LMS失败导致本地Roster回滚RED。
- 重复callback双写RED。
- 外部成绩直接覆盖正式成绩RED。
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

## C15-15 — 成绩单打印与成绩录入解耦

**优先级：** `P1`  
**V1.5 裁决：** `EXISTS-HARDEN`  
**外部成熟度信号：** 成熟SIS transcript基于正式记录，不基于教师草稿。

### 1. 学校业务问题
- 教师录分页不能直接生成正式成绩单。
- 正式查询件只读Published/EffectiveGrade。

### 2. 当前 exact-head 事实
- AaTranscriptView、student transcript、成绩单打印三级施工卡均已存在。

### 3. 历史设计 Reconciliation
- 历史打印模板可归D线文档交付；C线只保证数据源。

### 4. 唯一 Authority 决策
- C负责Published Grade/EffectiveGrade；D负责正式文档生成。
- 内部核对导出与正式transcript必须显式区分。

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
- draft成绩进入正式transcript RED。
- 非正式件冒充盖章证明RED。
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

## C15-16 — 补考 / 缓考 / 重修 / 免修 → Effective Grade

**优先级：** `P0`  
**V1.5 裁决：** `EXISTS-KEEP/HARDEN`  
**外部成熟度信号：** 国内教务把补缓重免作为常规链，PeopleSoft有repeat checking。

### 1. 学校业务问题
- 不同尝试会影响当前有效成绩、学分和毕业。
- 学校规则差异不能靠页面挑最新一行。

### 2. 当前 exact-head 事实
- repo已有makeup/retake/exemption/clearance和EffectiveGrade Policy。

### 3. 历史设计 Reconciliation
- 旧补缓重免完整状态机应逐项retest，已落地部分标HISTORICAL-MERGED。

### 4. 唯一 Authority 决策
- 各业务域保留自己的事实；EffectiveGrade Policy决定当前有效结果。
- 不UPDATE覆盖原Published Grade。

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
- 两个有效head RED。
- 补考结果按错误policy覆盖更优成绩RED。
- 重修重复计学分RED。
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

## C15-17 — Exam / Grade Archive Readiness Provider

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 真实学期封存前必须清零未完成考试、未发布成绩和未处置异常。

### 1. 学校业务问题
- 仅‘有数据’不能证明业务结束。
- 归档阻断必须有责任人和入口。

### 2. 当前 exact-head 事实
- Archive domain policy和R11 GRADE/ARCHIVE阶段已有；C负责准确provider。

### 3. 历史设计 Reconciliation
- 历史readiness设计可补未完事项分类。

### 4. 唯一 Authority 决策
- C只提供纯读evidence；D/Archive决定PASS/BLOCKED。
- provider失败=UNKNOWN/BLOCKED，禁止默认PASS。

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
- 有1条未发布Grade却Archive PASS RED。
- 未解决Exam incident却PASS RED。
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

## C15-18 — 教师课表 / 考勤 / 成绩权限随任课关系生效

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-HARDEN`  
**外部成熟度信号：** 成熟Faculty Center只给教师本人有效任课关系范围。

### 1. 学校业务问题
- 换教师后旧教师不能继续看到名单或录成绩。
- 多教师协同时权限必须按有效范围。

### 2. 当前 exact-head 事实
- Task teacher/TeachingClassTeacher、Schedule、Attendance、Grade均已有本人权限基础。

### 3. 历史设计 Reconciliation
- 旧权限矩阵的角色职责继续，permission code以Control Plane为准。

### 4. 唯一 Authority 决策
- 教师权限由正式Task/Teacher relation+effective weeks/scope决定。
- Workload/历史记录只读不赋予写权限。

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
- 旧教师能录新成绩RED。
- 协同教师获得超出角色的发布权限RED。
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

## C15-19 — 大规模成绩 XLSX / 异步作业可靠性

**优先级：** `P0`  
**V1.5 裁决：** `CURRENT-KEEP/HARDEN`  
**外部成熟度信号：** 商业教务必须处理学院/全校批量成绩，不能让Web请求长时间阻塞。

### 1. 学校业务问题
- 5000+行成绩导入需要扫描、预检、错误行、确认、Roster版本校验。

### 2. 当前 exact-head 事实
- Grade已有XLSX template/upload/dry-run/errors/confirm；File Exchange是统一框架。

### 3. 历史设计 Reconciliation
- 旧Excel施工卡重新作为性能/UX输入。

### 4. 唯一 Authority 决策
- 成绩确认仍由Grade domain writer；ImportJob只编排。
- dry-run与confirm之间Roster/Task config变化必须冲突。

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
- Roster换版后confirm仍成功RED。
- 5000行Web同步阻塞RED。
- 重复confirm双写RED。
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

## C15-20 — 教师真实一日 / 考试周 / 成绩周 Gold

**优先级：** `P0`  
**V1.5 裁决：** `FINAL-C-LINE-GATE`  
**外部成熟度信号：** 成熟度最终要体现在教师真正一天、一周能连续工作。

### 1. 学校业务问题
- 独立模块绿不等于老师能完成日常。
- 调课、监考、成绩退回等异常必须串起来。

### 2. 当前 exact-head 事实
- C线已有Today、Attendance、Exam、Grade、Workload等成熟基座。

### 3. 历史设计 Reconciliation
- 历史页面动作矩阵可转成E2E步骤，不再只当设计文档。

### 4. 唯一 Authority 决策
- 不新增Authority；只是跨模块同一教师事实链验收。
- 所有任务来自同一Task/Schedule/Roster/Exam/Grade。

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
- 换端后状态不一致RED。
- 消息失败导致业务事实回滚RED。
- console error/网络mock RED。
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

# Ⅷ. C 线页面级施工矩阵

## C-PAGE-01 — 教师Today工作台
- **页面唯一主任务**：围绕“教师Today工作台”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-02 — 教师课表
- **页面唯一主任务**：围绕“教师课表”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-03 — 教师考勤
- **页面唯一主任务**：围绕“教师考勤”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-04 — 特殊考勤补录
- **页面唯一主任务**：围绕“特殊考勤补录”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-05 — 调停课申请
- **页面唯一主任务**：围绕“调停课申请”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-06 — 调停课审核
- **页面唯一主任务**：围绕“调停课审核”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-07 — 考务总览
- **页面唯一主任务**：围绕“考务总览”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-08 — 考试课程与Roster
- **页面唯一主任务**：围绕“考试课程与Roster”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-09 — 考场座位
- **页面唯一主任务**：围绕“考场座位”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-10 — 监考安排
- **页面唯一主任务**：围绕“监考安排”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-11 — 考试异常处置
- **页面唯一主任务**：围绕“考试异常处置”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-12 — 缓考处理
- **页面唯一主任务**：围绕“缓考处理”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-13 — 成绩任务
- **页面唯一主任务**：围绕“成绩任务”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-14 — 成绩录入
- **页面唯一主任务**：围绕“成绩录入”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-15 — 成绩审核
- **页面唯一主任务**：围绕“成绩审核”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-16 — 成绩发布
- **页面唯一主任务**：围绕“成绩发布”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-17 — 成绩复查/更正
- **页面唯一主任务**：围绕“成绩复查/更正”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-18 — 教师工作量
- **页面唯一主任务**：围绕“教师工作量”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。

## C-PAGE-19 — 成绩逾期/催录
- **页面唯一主任务**：围绕“成绩逾期/催录”完成一个可闭环任务，不把统计、规则、名单、审批全部堆在同一页。
- **首屏结论**：当前学期/对象、当前阶段、正常/风险/阻断、关键数量、下一动作。
- **URL**：复杂对象必须可深链、刷新不丢 batchId/taskId/studentId；旧入口保留 redirect/alias。
- **数据**：只读 canonical DTO；不得用页面本地拼正式状态。
- **按钮**：每个按钮都必须明确 API、required permission、allowed state、success side effects、failure business code。
- **空态**：解释为什么空、谁应先完成什么、提供正确入口。
- **错误态**：业务码 + 人话 + traceId + 重试/处理建议。
- **归档态**：显式只读，不展示伪可写按钮。
- **大数据**：分页/搜索/筛选；名单不放 Drawer。
- **验收**：direct URL、refresh、back、无权限、跨scope、空数据、脏数据、归档态、必要移动端。


# Ⅸ. C 线真实学校验收场景目录

每个场景施工时展开成 Given / When / Then，并绑定 exact SHA、角色、tenant、term、business IDs、API结果、必要MySQL/Playwright和对账查询。

## C-SC-001 — 教师今日第一节课点名
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-002 — Roster未就绪阻断考勤
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-003 — Selection未LOCK阻断考勤
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-004 — 管理员特殊补录
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-005 — 特殊补录无reason失败
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-006 — 调课到新教室
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-007 — 调课资源冲突
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-008 — 按周换教师
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-009 — 换教师后旧教师权限撤销
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-010 — 集中考试排考
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-011 — 分散考试
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-012 — 同教师监考冲突
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-013 — 同教室考试冲突
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-014 — 多考场同课程铺位
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-015 — 考试名单打印
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-016 — 监考表打印
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-017 — 考试改期
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-018 — 缓考申请
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-019 — 缺考incident
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-020 — 违纪incident
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-021 — 未解决incident阻断归档
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-022 — GradeTask名单生成
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-023 — 逐人成绩录入
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-024 — 批量保存
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-025 — XLSX dry-run
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-026 — XLSX confirm时Roster换版
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-027 — 5000行成绩导入
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-028 — 教师双提交
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-029 — 学院双审核
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-030 — 教务双发布
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-031 — 成绩退回重提
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-032 — 发布后普通编辑拒绝
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-033 — 成绩复查
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-034 — 成绩更正
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-035 — 归档后成绩更正
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-036 — 补考后EffectiveGrade
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-037 — 重修后EffectiveGrade
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-038 — 免修/认定影响EffectiveGrade
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-039 — 两个EffectiveHead负向
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-040 — 成绩逾期催办
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-041 — 已提交教师不得误催
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-042 — 期中不及格触发预警
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-043 — 成绩更正后预警reconcile
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-044 — 教师工作量重算
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-045 — 课程取消后工作量变化
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-046 — 按周换教师工作量拆分
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-047 — LMS推Roster失败不影响本地
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-048 — 教师PC与小程序换端一致
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-049 — 考试周完整教师工作流
- **Given**：真实 tenant / 正式 term / 真实角色 / stable IDs；禁止 demo seed 冒充学校签字事实。
- **When**：只走 canonical router/service/页面；兼容旁路如被触发必须有计量证据。
- **Then-事实**：状态、版本、hash、数量、引用关系与预期一致。
- **Then-权限**：本人/本院/全校范围符合角色；邻租户不可见。
- **Then-审计**：正式写有 operator/reason/业务引用；高风险动作可回放。
- **Then-持久性**：reread、refresh、re-login/换端仍一致。
- **Negative**：至少构造越权、重复、错误状态或脏数据中的一个失败分支。
- **Evidence**：exact HEAD + migration head（适用时）+ test run + 对账结果。

## C-SC-050 — 成绩周完整教师工作流
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


# C — Teaching Execution：教学运行·考勤·调停课·考务·成绩 — V1.4 四线并行唯一施工总册

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


# C — Teaching Execution 成熟链保护性施工总控

## C.1 责任边界

C 负责：
- 08 教学运行 / 考勤 / 调停课；
- 09 考务；
- 10 成绩。

核心原则：**这是成熟链保护性强化，不是重做。**

C 不得重建：
- TeachingRoster；
- Exam Authority；
- Grade Authority；
- Effective Grade；
- Schedule Truth。

## C.2 C 线消费的 B Contract
只有 B-C1/B-C3 freeze 后，C 才能正式改下游 consumer：
- 当前 Published Schedule；
- 当前 TeachingRoster；
- version/hash/memberCount；
- `ROSTER_PENDING_SELECTION` 不得被正常考勤/考试/成绩消费。

## C.3 施工批次

### C0 — Mature Chain Freeze
先冻结现有：
- attendance Task-first；
- RosterConsumerSnapshot；
- exam confirm/publish；
- grade roster/hash/import/workflow；
- effective grade。

现有 tests 先全跑出 baseline，任何后续变化都和 baseline 对比。

### C1 — Attendance 正常链保持，admin compatibility 隔离
正常教师：
`Today Task → current roster → session → submit`

不改。

管理员无 Task 手工场次：
- 单独权限；
- 明确“特殊人工场次”；
- 原因必填；
- 审计；
- 不作为教师正常 UX。

### C2 — 教师“今天我要做什么”体验
PC/小程序首屏：
- 今日课程；
- roster ready/count/source/version；
- 点名入口；
- 已提交状态；
- 异常学生；
- 后续任务。

目标：教师小程序 3 步内到点名。

### C3 — 调停课 occurrence-first
调停课只能基于 Published Schedule occurrence。

覆盖：
- 教师请假；
- 教室故障；
- 临时活动；
- 校历调整；
- 整周停课；
- 跨周补课。

变更后：
- 新正式课表立即读取；
- 旧版本可追溯；
- affected teachers/students 进入消息 Outbox。

### C4 — Exam Operational Readiness
保留 exam state machine。

增强工作台：
- batch；
- course；
- frozen roster；
- rooms；
- seats；
- invigilators；
- patrol；
- defer；
- incidents；
- blockers。

publish 前逐项下钻。

### C5 — Exam Change / Incident Closure
发布后考试时间、教室、监考不得普通 UPDATE。

建立/确认专门 change flow：
- reason；
- impact preview；
- concurrency recheck；
- audit；
- notification。

违纪/缺考/缓考不能只留下孤立 incident，要有责任去向/结果。

### C6 — Grade Teacher Workflow
完整教师链：
- task list；
- roster；
- single edit；
- batch save；
- XLSX；
- quality check；
- submit；
- returned reason；
- resubmit。

学院：
- pending；
- anomalies；
- return。

教务：
- final review；
- publish；
- correction/recheck/archive。

学生：
- official published only。

### C7 — PR #96 Collision Seal
`miniapp/src/pages/teacher/academic-affairs/grade-entry.vue` 当前与 PR #96 冲突风险高。

施工前：
- fetch exact #96 diff；
- 若 #96 已合并，基于新 main；
- 若仍 open，本线不覆盖其逻辑；
- 共享 `services/__init__.py` / registry 交 INT。

### C8 — Grade Reliability / MySQL Concurrency
必测：
- same task multi-device save；
- double submit；
- double review；
- double publish；
- XLSX confirm vs roster version change；
- miniapp retry/offline duplicate；
- post-publish normal edit blocked。

### C9 — Effective Grade Cross-surface
同一学生同一课程：
- StudentGrades；
- transcript/query copy；
- credits/GPA；
- graduation；
必须选同一 effective grade。

不得各页面 `latest row wins`。

### C10 — C-line Gold
固定课 + SELECTABLE LOCK 后各跑：
`Schedule → Attendance → Exam → Grade`

验证：
- roster snapshot identity 一致；
- version stale fail-closed；
- 0 名单外考生；
- 0 名单外成绩；
- publish 后学生读取一致；
- teacher PC/miniapp reload 后事实一致。

冻结 C Consumer Contract，交 D。

## C.4 C 线禁止事项
- 禁止重写 Exam/Grade state machine；
- 禁止从 StudentProfile 动态拼正式名单；
- 禁止让课程名/行政班决定考试/成绩 identity；
- 禁止碰 PR #96 同文件而不 collision audit；
- 禁止特殊补录混进正常 GradeTask；
- 禁止消息发送失败回滚正式业务事实。

## C.5 C → D 交接包
- Attendance snapshot evidence；
- Exam roster/seat/invigilator evidence；
- Grade workflow/effective grade evidence；
- teacher journey E2E；
- concurrency report；
- known P0/P1 = 0；
- exact HEAD。


---

# 原 V1.3 详细施工内容完整整编：本线专项详细施工原文


---

## 来源文档：`08_教学运行考勤调停课_真实学校交付施工文档_V1.3.md`

# 08 — 教学运行 / 考勤 / 调停课：现有代码逐行审计 + 真实学校交付校正版 V1.3

> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 1. 当前成熟度

**🟢/🟡 正常教学链较成熟**

当前 Authority：`TeachingTask + current TeachingRoster + Published Schedule → Attendance / ScheduleChange`

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
| AaAttendanceSession | [KEEP] | 场次冻结 roster_json，public service 另冻结 roster snapshot |
| AaRosterConsumerSnapshot | [KEEP] | ATTENDANCE_SESSION 正式名单身份 |
| AaScheduleChange | [KEEP] | 正式课表发布后的合法调整事实 |

## 4. Router / Service / Guard 审计

| 文件 | 标记 | 逐函数/关键分支结论 |
|---|---|---|
| backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py | [KEEP/HARDEN] | 教师必须当前学期本人 Task；正常链冻结正式 roster；管理员仍有 class 手工兼容入口 |
| backend/app/modules/academic_affairs/services/academic_affairs_roster_consumer_service.py | [KEEP] | 提交/后续可校验名单未静默换版 |

## 5. 四端前端审计

| 页面/客户端 | 标记 | 当前情况 |
|---|---|---|
| miniapp/src/pages/teacher/academic-affairs/attendance.vue | [KEEP] | Task-first 新建考勤；无任务不让教师点名 |
| miniapp/src/pages/teacher/academic-affairs/index.vue | [KEEP] | 今日教学+待办 |
| student-portal/src/views/academic/StudentAcademicReadOnlyView.vue | [KEEP] | 学生考勤只读 |
| frontend/src/modules/academicAffairs/views/AaAttendanceStatsView.vue | [KEEP] | 管理统计 |

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

- 管理员无 Task 的手工考勤入口必须显著标“特殊人工场次”，权限/审计与正常教学链隔离。
- 教师端新建场次时显示 roster source/version/count；roster not ready 明确阻断原因。
- 调停课最终只针对 Published Schedule occurrence，不允许重新自由拼课程/教师。

## 8. 最小安全施工方式

正常教师链不动；先约束/标记 admin compatibility path。

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

## 真实学校增强：教学运行

- 教师日常主路径必须以“今天我要做什么”为入口：今日课程 → 点名 → 提交 → 异常学生 → 后续查看。
- 管理员手工 class-based 考勤只作为特殊纠错/历史补录能力，必须单独权限、原因、审计，不和正常教师链混用。
- 调停课必须覆盖：教师请假、教室故障、临时活动、校历调整、整周停课、跨周补课。
- 课表变更通知必须可追踪到受影响教师/学生；投递失败有补偿任务。
- 考勤 session 必须有正式 roster snapshot；缺失即 BLOCKED。

**Go-Live DoD**
- 教师小程序可在 3 步内进入今日课程并点名；
- 提交后刷新/换端仍一致；
- 调课后旧课表历史可追溯、新课表立即成为正式读取；
- 异常调课通知有送达/失败台账。

---

## 来源文档：`09_考务Exam_真实学校交付施工文档_V1.3.md`

# 09 — 考务 Exam：现有代码逐行审计 + 真实学校交付校正版 V1.3

> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 1. 当前成熟度

**🟢 主链强**

当前 Authority：`TeachingTask → EXAM_COURSE roster snapshot → time/room/seat/invigilator → publish → incident/defer → finish/archive`

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
| AaExamBatch / AaExamCourse / AaExamRoom / AaExamRoomStudent / AaExamInvigilator | [KEEP] | 考务批次、课程、考场、座位、监考完整事实 |
| AaRosterConsumerSnapshot(EXAM_COURSE) | [KEEP] | 学院确认课程时冻结考生名单 |

## 4. Router / Service / Guard 审计

| 文件 | 标记 | 逐函数/关键分支结论 |
|---|---|---|
| backend/app/modules/academic_affairs/routers/exam_core_router.py | [KEEP] | Task候选、preview/confirm、排考、考场、座位、监考、巡考、缓考、异常、归档 |
| backend/app/modules/academic_affairs/services/academic_affairs_exam_facade.py | [KEEP] | 确认冻结 roster；铺位只认 snapshot；发布重新校验名单/座位/容量/监考/资源冲突 |

## 5. 四端前端审计

| 页面/客户端 | 标记 | 当前情况 |
|---|---|---|
| frontend/src/modules/academicAffairs/views/AaExamConsoleView.vue | [KEEP/HARDEN] | 已经 Task-first 候选+preview |
| student-portal/src/views/academic/StudentExamView.vue | [KEEP] | 只展示本人正式名单内已发布场次 |

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

- 管理 PC 把 rosterIdentity/version/count 可视化，便于学校对账。
- 教师/学生端不要根据课程名或行政班自行拼考试安排。
- 保留跨批次资源冲突的同学期行锁协议。

## 8. 最小安全施工方式

不重写考务状态机；只做可解释性与 E2E。

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

## 真实学校增强：考务运营

考务 Authority 不重写，但学校上线要补“运营完整性”：
- 考试批次、课程、考场、座位、监考、巡考、缓考、异常必须有一张 readiness 工作台；
- 发布前 blockers 逐项下钻；
- 考试时间/教室/监考发布后变更必须走专门 change flow + 通知，不允许普通 UPDATE；
- 考场签到/缺考/违纪的后续处理必须闭环，不允许只有 incident 记录没有责任去向；
- 关键通知（考试发布、改期、缓考结果）必须进入消息投递可观测链。

**规模验收**
- 全校考试周批量排考；
- 同时段资源冲突并发发布；
- 大考场/多考场同课程座位全量一致；
- 失败重试不重复铺位/重复通知。

**Go-Live DoD**
- `expectedStudents == frozenRoster.memberCount`；
- 座位全集与 frozen roster 完全一致；
- 0 重复座位、0 名单外学生；
- 每个正式考场有监考。

---

## 来源文档：`10_成绩Grade_真实学校交付施工文档_V1.3.md`

# 10 — 成绩 Grade：现有代码逐行审计 + 真实学校交付校正版 V1.3

> 审计仓库：`penghaibin9/saas`  
> 审计基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`  
> 审计日期：2026-08-16  
> 审计模式：**只读代码审计；未修改 main、未创建迁移、未提交代码。**  
> PR #101 的 D1–D9 教务结构治理已经合入此基线；本总册按“保护现有成熟能力、焊接主链断点”编写。


## 1. 当前成熟度

**🟢 主链很强**

当前 Authority：`TeachingTask + current TeachingRoster → GradeTask → GradeRecord → workflow → published official grade → effective-grade policy`

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
| AaGradeTask / AaGradeRecord | [KEEP] | 成绩任务/录入记录 |
| AaRosterConsumerSnapshot(GRADE_TASK) | [KEEP] | 提交时冻结名单版本 |
| Effective Grade policy/snapshot/identity head | [KEEP] | 统一成绩有效性，不让各页面自行选最新 |

## 4. Router / Service / Guard 审计

| 文件 | 标记 | 逐函数/关键分支结论 |
|---|---|---|
| backend/app/modules/academic_affairs/routers/grade_core_router.py | [KEEP] | 名单、录分、xlsx、提交、学院审核、发布、退回、归档 |
| backend/app/modules/academic_affairs/services/academic_affairs_grade_service.py | [KEEP] | 稳定课程版本、正式 roster、hash 预检、提交冻结 snapshot、发布前版本校验 |
| backend/app/models/academic_affairs_registry.py | [KEEP] | grade extension/effective policy 注册及 fresh schema 元数据对齐 |

## 5. 四端前端审计

| 页面/客户端 | 标记 | 当前情况 |
|---|---|---|
| frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue | [KEEP/HARDEN] | Task-first 正常录入；管理员特殊补录明确隔离 |
| miniapp/src/pages/teacher/academic-affairs/grade-entry.vue | [KEEP/HARDEN] | 正式名单+质量报告+批量保存；当前 main 基线，注意 PR #96 正在改此文件 |
| student-portal/src/views/academic/StudentGradesView.vue | [KEEP] | 只显示正式发布成绩，查询件不冒充盖章证明 |

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

- 教师 PC/小程序统一展示 roster source/version/count，stale 时明确 BLOCKED。
- PR #96 合并前后必须做 collision audit，不把未合入分支内容当当前 main 事实。
- 特殊补录继续禁止混入普通 TeachingTask 发布链。

## 8. 最小安全施工方式

成绩不是本轮结构重写对象。优先保护 R9 roster consumer + effective grade。

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

## 真实学校增强：成绩正式业务

当前成绩主链继续 `[KEEP]`，但上线标准必须覆盖老师真正使用：
- 教师 PC/小程序：任务列表、名单、逐人录入、批量保存、Excel、质量检查、提交、退回后重提；
- 学院：待审核列表、异常项、退回原因；
- 教务：终审、发布、更正、复查、归档；
- 学生：只看正式发布成绩与复查状态。

**规模/可靠性**
- 5000+ 成绩行 XLSX 通过 File Exchange 或明确批次限制；
- dry-run 与 confirm 之间名单换版必须冲突，不静默导入；
- 重复提交、双审核、双发布做 MySQL 并发；
- 教师小程序断网/重复点击不能产生重复正式记录。

**Go-Live DoD**
- 所有正式成绩可回链 courseId/version + TeachingTask + roster snapshot；
- 发布后普通录入接口 fail-closed；
- 更正产生版本/审计，不覆盖历史；
- effective grade 在成绩单/学分/GPA/毕业处一致。

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
