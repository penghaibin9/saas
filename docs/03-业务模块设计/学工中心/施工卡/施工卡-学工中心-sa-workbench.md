# 施工卡 · 学工中心 · 学工工作台（sa-workbench）

> **模块口径**：本卡为学工中心 B 包「学工工作台」二级模块的生产级施工卡，供甲方照此开发。
> **导航事实**（`frontend/src/config/navPlan.js` L81）：`mod('sa-workbench', '学工工作台', null, P('学工总览', '辅导员工作台'))` —— 二级模块 `sa-workbench`，label「学工工作台」，含 **2 个三级页面：学工总览、辅导员工作台，二者均 `planned`/`待施工`/`disabled`、未注册路由**（`P()` 生成 `status:'planned'`，见 navPlan.js L24–26）。当前按 §42 规划占位页规则，点击进入公共占位页，不做假业务。
> **权限前缀**：本模块权限点统一 `studentAffairs.*`（业务 moduleKey=`studentAffairs`；导航二级 key=`sa-workbench`，两者不冲突）。
> **文档性质**：只写文档，不改任何代码 / navPlan / 配置 / 迁移。凡读不到依据处一律标「需人工确认」，不臆造字段 / 接口 / 流程。
> **对标声明**：对标正方、强智、青果等经市场验证的成熟学工产品的**产品精华与业务成熟度**（角色分工、看板聚合、待办闭环、批量处理、下钻对账、权限审计），**不抄袭其界面、代码、数据库、商标、专有文案**。本卡未联网检索，厂商级细粒度特性以仓库《商业化对标审计（第一轮）》为主依据，超出该依据的厂商细节均标「需人工确认」。

---

## 1. 模块定位与真实学校业务价值

### 1.1 这是什么
「学工工作台」是学工中心的 **PC 高频首屏**，把散落在请假、风险、宿舍、困难、奖助、处分、谈话、归档等业务里的「今天谁要处理、哪些学生要盯」聚合到一处，让不同角色进系统第一眼就知道该干什么。它本身**不产生业务数据、无独立状态机**，是各业务的**只读聚合 + 待办直达 + 下钻入口**（依据：`13A-学工中心全业务流程设计总册.md` §3.1 ⑥「无独立状态机」L215、§3.2 ⑥ L240）。

它由两个三级页面组成：
- **学工总览**（角色化驾驶舱）：给学工处（全校）、学院学工（本学院）、校领导（汇总）看指标卡 + 趋势 + 待办 / 风险 / 宿舍异常概览，逐卡下钻到业务列表。
- **辅导员工作台**：给辅导员 / 班主任看「我的班级 / 今日待办 / 我的风险学生 / 待审请假 / 待谈话」，一键进学生 360、一键处理待办。

### 1.2 真实学校谁用、解决什么
| 角色 | 真实场景 | 工作台解决的痛点 |
|---|---|---|
| 辅导员 / 班主任 | 每天带几百学生，早上开机第一件事：今天有哪些请假要审、哪些风险学生要跟、哪些谈话计划到期 | 不用逐个业务菜单翻，一页聚合 + 待办直达，处理完自动销账 |
| 学院学工负责人 | 掌握本院学工全貌、督办辅导员 | 本院指标 + 辅导员待办完成率排行，发现掉队班级 |
| 学工处管理员 | 全校学工态势、给校领导汇报 | 全校指标 + 学院风险 / 待办排行 + 趋势，逐层下钻核对 |
| 校领导 | 看总体不看明细 | 汇总驾驶舱视图（默认脱敏、只读） |

**业务价值一句话**：把「找事做」变成「按工作台提示做」，是学工中心留住辅导员日活、支撑投标「智慧学工驾驶舱」话术的核心入口（对标精华原则 1 / 11，见 §2）。

---

## 2. 三家成熟系统对标表（严格按 CLAUDE.md §0.0 十点结构）

> 主依据：`13A-学工中心-商业化对标审计与补丁建议（第一轮）.md`（对标对象声明 L6；15 条精华 L71–103；缺口表 L107–130；逐模块 §5 首页 L138 / 工作台 L140）。厂商级细粒度特性该审计未逐条列出，以下按「审计综合口径 + 行业常识」填写，**凡涉及具体厂商独有做法均标（需人工确认）**，不作为确定结论。

### 对标对象 A：正方（教务起家、学工模块）
- **核心流程**：以「教务 + 学工一体化」为底，工作台侧重「待办 + 通知 + 快捷入口」，学工待办常与教务待办（学业预警等）混排（需人工确认：正方工作台是否默认教务学工混排）。
- **角色**：校 / 院 / 系三级管理员、辅导员、学生；数据范围随组织层级下发。
- **字段**：待办标题 / 类型 / 来源 / 截止 / 处理入口；指标卡以「人数 / 待办数」为主。
- **亮点**：组织层级数据范围成熟、待办与流程引擎耦合紧、下钻到教务明细顺。
- **缺点**：学工侧看板相对偏「通知列表」，辅导员「学生 360 聚合」深度较弱（需人工确认）。

### 对标对象 B：强智（教务 + 学工 + 迎新一体）
- **核心流程**：角色化门户 / 工作台 + 消息待办中心 + 多角色首页 preset；辅导员端聚合本人班级待办与学生名册。
- **角色**：校领导驾驶舱、学院、辅导员、班主任、学生；辅导员按带班班级授权。
- **字段**：指标卡（在校 / 请假 / 违纪 / 资助 / 预警）、待办（来源 / 截止 / 状态）、班级概览（班级 / 人数 / 风险数）。
- **亮点**：多角色 preset 首页、班级维度聚合、迎新→学工数据贯通较完整。
- **缺点**：批量催办 / 同生多风险合并等辅导员减负能力厂商间参差（需人工确认）。

### 对标对象 C：青果（学工 / 迎新 / 资助见长）
- **核心流程**：辅导员工作台强调「学生画像 + 今日事务 + 谈心谈话 / 家校记录」联动；资助、困难、心理台账化成熟。
- **角色**：学工处、学院、辅导员、班主任、宿管、资助 / 心理专员、学生。
- **字段**：学生画像多维标签、谈话 / 家校 / 风险记录、资助 / 困难台账。
- **亮点**：辅导员动线围绕「学生画像 + 今日待办」组织（正是精华原则 11），台账 / 导出 / 审计口径规整。
- **缺点**：驾驶舱多层级钻取（校→院→专业→班→辅导员→学生）深度厂商间不一（需人工确认）。

### ① 三家共同具备的核心能力（= 本项目工作台必须具备的基础能力）
1. **分角色 preset 首页**：领导看驾驶舱、学院看分布、辅导员看待办、学生看进度（精华原则 1，审计 L75）。
2. **统一待办 / 消息中心**：所有业务待办汇聚一处、可直达处理页、处理后销账（精华原则 6/7）。
3. **指标卡 + 下钻**：汇总数字可点开到明细列表，且首页数字与列表数字对账一致（精华原则 9，审计 L91）。
4. **辅导员动线围绕「学生画像 + 今日待办」聚合**（精华原则 11，审计 L95）。
5. **数据范围按组织 / 带班关系裁剪**，前端不放大范围，后端裁定（精华原则 5/6）。
6. **敏感字段脱敏 + 授权查看 + 审计留痕**（精华原则 5，审计 L83）。

### ② 三家里最值得吸收的最佳做法
- **青果的「辅导员画像 + 今日待办」动线**：工作台默认落在辅导员最高频的两件事上（本项目已在 §3.2 设计为「360 最高频入口」，总册 L247）。
- **强智的「多角色首页 preset + 班级维度聚合」**：一套 dashboard 接口按 currentRole 自动出不同视图（本项目已在 API #1 `rolePreset` 设计，契约 L58）。
- **正方的「组织层级数据范围 + 待办与流程引擎耦合」**：待办完结由业务 service 在同事务回写（本项目已用 `t_unified_todo.status=DONE` 回写机制，总册 L237）。

### ③ 本项目当前已有能力（底座证据）
- **设计层已齐备**：dashboard 契约 #1（契约 L53）、counselor 四接口 #2–#5（契约 L76–79）、移动教师工作台 #128（契约 L493）、统计下钻 #109（契约 L398）。
- **机制已复用**：统一待办 `t_unified_todo`（去重键 source_module+source_biz_id+todo_type+assignee_id，总册 L29）、8 类统一消息 `t_unified_message`（总册 L29）、数据范围 `resolve_teacher_scope`/`getStudentAffairsScope`（权限总控 L5）、审计 `t_security_audit_log`（权限总控 L5）。
- **规划状态**：`13A-学工中心全量规划施工图.md` L31 标「学工看板：部分完成 / 已有 affairs dashboard、class、cadre 能力 / 未建独立 PC」。

### ④ 缺失的生产级闭环（缺口，来自审计 §5）
- 学工总览：**多层级钻取只到列表未到 校→院→专业→班→辅导员→学生**；缺「今日必须处理 / 即将超期」两卡（审计 L138）。
- 辅导员工作台：**今日待办无紧急度排序**、**无同生多风险合并**、**无一键联系学生 / 家长**、**工作量未自动沉淀**、缺「长期未跟进 / 待回访」卡（审计 L114/L140）。
- 独立 PC 页尚未落地（施工图 L31「未建独立 PC」）。

### ⑤ 本卡必须补齐（本轮施工目标）
1. 落地两个独立 PC 页（学工总览、辅导员工作台），串接**真实**待办 / 风险 / 指标，禁止假统计（B 包卡 §3.1 备注 L56「不得用假统计填充」）。
2. 学工总览：三角色 preset、8 类指标卡、待办列表、风险列表、逐卡下钻、首页-列表 0 差异对账（总册 §3.1 ⑰ L226；对账要求审计 L91）。
3. 辅导员工作台：myClasses / todayTodos / riskStudents / pendingLeave / 待谈话聚合、快速搜索进 360、待办直达并自动销账（总册 §3.2 ⑰ L251）。
4. 全页三态（loading / empty / error）、数据范围裁剪、敏感脱敏、下钻二次鉴权（B 包卡 §3.1/§3.2 验收行）。

### ⑥ 进 backlog（能力池 / 补强包，本卡不做成假功能）
- 今日待办紧急度排序、同生多风险合并、一键联系、工作量自动沉淀、长期未跟进卡（补丁 P-01，审计 L184–209；标注「随施工包 A 落地」）。
- 学院排行导出、自定义卡片布局、趋势图细化（总册 §3.1 ⑰ P2P3 L226）。
- 批量催办、辅导员日志（总册 §3.2 ⑰ P2P3 L251）。
- 上述均为 planned 补强，本卡只登记为 backlog，不在本轮标 implemented。

### ⑦ 禁止做成假功能（红线）
- 禁止假指标 / 假待办 / 假趋势填充页面（B 包卡 L56）。
- 禁止把全校待办发给辅导员（B 包卡 §3.2 L74「严禁把全校待办给辅导员」）。
- 禁止前端放大数据范围、禁止前端隐藏当权限（CLAUDE.md §3.4；权限总控 L70）。
- 禁止在工作台内重做各业务处理页——只做聚合 + 跳转（总册 §3.2 ⑯ L250）。
- planned 页在真实施工完成前，不得因占位页存在就标 implemented / partial（§42.4）。

---

## 3. 三级页面清单与状态（对齐施工图与 navPlan）

| 三级页面 | navPlan 状态 | 施工目标路由（设计草案） | 实现形态 | 优先级 | 阻断 PC | 阻断上线 | 依据 |
|---|---|---|---|---|---|---|---|
| 学工总览 | `planned`/待施工/未注册路由 | `/admin/student-affairs/dashboard`（B 包卡 §3.1 L44；总册 §3.1 ⑮ 默认页 `/admin/student-affairs` L224） | 独立页 | P0 | 是 | 是 | navPlan L81；B 包卡 §7 L314 |
| 辅导员工作台 | `planned`/待施工/未注册路由 | `/admin/student-affairs/counselor-workbench`（B 包卡 §3.2 L62）或 `/admin/student-affairs/workbench`（总册 §3.2 ⑮ L249）——**路由二选一需人工确认统一** | 独立页 | P0 | 是 | 是 | navPlan L81；B 包卡 §7 L316 |

> **口径对齐说明**：navPlan（L81）将本模块收敛为「学工总览 + 辅导员工作台」2 个三级；而 `全量规划施工图.md` §2 与 B 包施工卡 §7 把「今日待办 / 学生风险概览 / 请假审批概览 / 宿舍异常概览 / 重点学生提醒」列为学工看板下的看板分栏三级（施工图 L57–64；B 包卡 L314–320）。二者不冲突：**这些分栏是「学工总览」页内的 panel（同路由 `?panel=` 分栏），不是独立菜单三级**（B 包卡 §7「实现形态=看板分栏，父页=学工总览」L315–320）。本卡以 navPlan 的 2 个三级为菜单事实，看板分栏作为「学工总览」页内结构在 §4/§8 展开。
> **路由待确认**：辅导员工作台路由存在 `counselor-workbench`（B 包卡）与 `workbench`（总册）两种写法，开发前须由甲方 / navPlan 统一（需人工确认）。

---

## 4. 业务流程与状态机

### 4.1 状态机结论
本模块**无独立业务状态机**（总册 §3.1 ⑥ L215、§3.2 ⑥ L240）。它消费下游状态，本身不改写：
- 待办状态复用 `t_unified_todo`：`PENDING / DONE / CANCELLED`（总册 §3.2 ⑥ L240）。待办**完结由各业务 service 在动作成功的同一事务内回写 `status=DONE`**，工作台只读、不自行改待办态（总册 §1.4 约定 L65、§3.2 主流程 4 L237）。
- 指标卡数字口径由各业务状态机终态 / 在途态定义（总册 §3.1 ⑥ L215、⑭ L223，示例：`逾期未销假数 = count(t_cs_leave where affairs_status=OVERDUE and tenant)`）。

### 4.2 学工总览主流程（已在总册 §3.1 ③ 设计，L208–212）
1. 进入 `/admin/student-affairs` → 前端携 `activeContextId` 调 `GET /api/v1/student-affairs/dashboard?semester=&date_range=`。
2. 后端解析 `tenant_id / current_role / data_scope`（token 上下文，**前端不传租户 / 范围**），按角色 preset 组装：`summaryCards / todoList / riskStudents / workflowPending / classOverview / warningTrends / recentActivities`。
3. 学工处视图追加「学院风险与待办排行」（按 `college_id` group by）；学院视图同构指标限本学院。
4. 风险学生卡点击→跳该生学生 360；待办点击→按 `todo.action_url` 跳处理页。
- **异常降级**：范围内无数据→空卡片 +「当前身份范围暂无数据」；聚合超时→分卡异步加载，单卡失败卡内 error 不拖整页（总册 §3.1 ④ L213）。
- **辅导员访问本页自动 302 至辅导员工作台**（总册 §3.1 ⑧ L217）。

### 4.3 辅导员工作台主流程（已在总册 §3.2 ③ 设计，L233–237）
1. PC `/admin/student-affairs/workbench`（或教师小程序）→ `GET /api/v1/student-affairs/counselor/workbench`。
2. 后端 `getCounselorScope(user)`（= `resolve_teacher_scope` 包装）→ 得 classNames / studentNos → 组装：我的班级 / 我的学生数 / 今日待办 / 待审请假 / 风险学生 / 学业预警 / 待谈话 / 困难生数 / 处分跟进 / 就业未填报 / 实习异常 / 毕设异常。
3. 子接口：`counselor/students`（快速搜索，scope 内检索）、`counselor/todos`、`counselor/risk-students`。
4. 待办卡点击→`action_url` 直达；处理完成后待办由业务 service 自动完结。
- **异常**：scope 解析为空→「未配置带班范围，请联系学院管理员」（非 500）；搜索越权学号→`assertCounselorCanAccessStudent` 失败→403 + 审计（总册 §3.2 ④ L238）。

### 4.4 责任人 / 超期升级
- 工作台不定义超期升级；升级发生在各业务（如请假逾期转风险 OVERDUE、风险 ESCALATED）。工作台通过「即将超期 / 逾期待办」卡**呈现**这些状态，供辅导员及时处理（缺口卡「即将超期」待补，审计 L138）。

---

## 5. 表单字段与校验规则

> 本模块为只读聚合页，**无业务落表表单**（总册 §3.1 ⑨「无落表」L218、§3.2 ⑨「无新表」L243）。仅有「查询 / 筛选」入参与「敏感查看原因」输入。逐项如下。

### 5.1 学工总览 — 查询入参（GET dashboard）
| 字段 | 类型 | 必填 | 校验 | 敏感级 | 依据 |
|---|---|---|---|---|---|
| semester | string | 否 | 学期编码，空=按默认周期 | 无 | 契约 #1 L53 |
| dateRange / date_range | string | 否 | 日期区间，遵循公共日期组件；空=不限（§40 筛选默认不限） | 无 | 契约 #1 L53；CLAUDE.md §40 |
| tenant / role / scope | —（禁传） | — | **前端禁止传租户 / 角色 / 范围**，一律 token+scope 解析 | 无 | 总册 §3.1 ⑧ L217 |

### 5.2 辅导员工作台子接口 — 查询入参
| 接口 | 字段 | 类型 | 必填 | 校验 | 依据 |
|---|---|---|---|---|---|
| counselor/students | keyword | string | 否 | 姓名 / 学号，scope 内检索 | 契约 #3 L77 |
| counselor/students | classId | string | 否 | 必在本人带班范围内 | 契约 #3 L77 |
| counselor/students | riskLevel | enum | 否 | HIGH/MEDIUM/LOW（枚举需人工确认全集） | 契约 #3 L77 |
| counselor/todos | status | enum | 否 | PENDING/DONE/CANCELLED | 契约 #4 L78；总册 §3.2 ⑥ L240 |
| counselor/todos | todoType | enum | 否 | 取值域限统一待办 todo_type（需人工确认全集） | 契约 #4 L78 |
| counselor/risk-students | riskLevel/source/status | enum | 否 | 枚举需人工确认全集 | 契约 #5 L79 |
| 各分页接口 | page/pageSize | int | 否 | page≥1，pageSize 上限需人工确认 | 契约 #3–#5 |

### 5.3 敏感查看原因（下钻触发时，复用画像 #8）
| 字段 | 类型 | 必填 | 校验 | 敏感级 | 依据 |
|---|---|---|---|---|---|
| field | enum | 是 | 联系方式 / 家庭 / 身份证 | 强敏感 | 契约 #8 L112 |
| reason | string | 是 | **≥5 字** | 强敏感 | 契约 #8 L112 |

---

## 6. 权限矩阵与数据范围

> 依据：`00-系统管理中心-权限角色模块授权与权责边界设计.md` L262–265（学工角色 / 数据范围）、L70（四层裁定：权限点→数据范围→敏感→审批节点）；总册 §3.1 ⑦⑧ L216–217、§3.2 ⑦⑧ L241–242；契约 #1–#5 权限点列。

### 6.1 权限点（permissionCode，命名遵循 CLAUDE.md §10.3）
| 权限点 | 含义 | 归属页面 | 依据 |
|---|---|---|---|
| `studentAffairs.dashboard.view` | 进入学工总览 | 学工总览 | 契约 #1 L53；总册 §3.1 ⑦ L216 |
| `studentAffairs.dashboard.collegeRank.view` | 学院排行卡（**仅学工处**） | 学工总览 | 总册 §3.1 ⑦ L216 |
| `studentAffairs.counselor.dashboard.view` | 进入辅导员工作台 | 辅导员工作台 | 契约 #2 L76；总册 §3.2 ⑦ L241 |
| `studentAffairs.counselor.student.view` | 我的学生列表 / 快速搜索 | 辅导员工作台 | 契约 #3 L77 |
| `studentAffairs.counselor.todo.handle` | 待办读取 / 处理直达 | 辅导员工作台 | 契约 #4 L78 |
| `studentAffairs.counselor.risk.handle` | 风险学生读取 / 处置直达 | 辅导员工作台 | 契约 #5 L79 |
| `studentAffairs.student.sensitiveView` | 下钻查看完整敏感字段 | 下钻至画像时 | 契约 #8 L112 |

### 6.2 角色 × 可见 / 可操作 × 数据范围
| 角色 | 学工总览 | 辅导员工作台 | 数据范围（scopeType） | 范围来源（真实业务关系） | 依据 |
|---|---|---|---|---|---|
| 学工处管理员 | 可见（全校 + 学院排行卡） | 可下钻辅导员 | `SCHOOL` | 全校 | 权限总控 L262；总册 §3.1 ⑧ L217 |
| 学院学工负责人 | 可见（本学院，排行是否可见**需现场确认**） | 可下钻本院辅导员 | `COLLEGE` | 本学院 | 权限总控 L263（需人工确认）；总册 ⑱ L227 |
| 辅导员 | **自动 302 至工作台** | 可见可操作（本人班级） | `CLASS`/`ADVISOR`（COUNSELOR_CLASSES） | 辅导员-班级 / 学生绑定 `t_teacher_student_scope` + `t_affairs_counselor_binding` | 权限总控 L264；总册 §3.2 ⑧ L242 |
| 班主任 | 自动 302 至工作台 | 可见可操作（本班） | `CLASS` | 班主任-班级绑定 | 权限总控 L265；总册 §3.2 ⑧ L242 |
| 校领导 | 可见（汇总、只读、默认脱敏） | 不适用 | `SCHOOL`（汇总） | 全校汇总 | B 包卡 §3.1 定位 L45 |
| 学生令牌 | **403**（require_staff） | 403 | — | — | 总册 §3.1 ② L207；契约 #1 错误码 L68 |

### 6.3 数据范围铁律
- 范围一律后端 `getStudentAffairsScope` / `getCounselorScope`（=`resolve_teacher_scope`）解析，**前端禁传范围参数**（总册 §3.1 ⑧ L217）。
- 辅导员范围**来自真实带班绑定**，不是「因为叫辅导员就看全校」（CLAUDE.md §3.3；权限总控 L264）。
- scope 为空且非 ADMIN → **空列表**（TENANT_FALLBACK 不放行），不得回退成全租户可见（契约 #2 错误码 L102）。
- 「看得见=能处理」：列表与写操作共用同一 scope 函数（总册 §3.2 ⑧ L242）。
- 下钻到明细页 **二次 403 校验**（B 包卡 §3.1 L50「详情跳转再次 403 校验」）。

---

## 7. 敏感字段脱敏与审计（CLAUDE.md §6 红线）

| 项 | 规则 | 依据 |
|---|---|---|
| 脱敏字段 | 手机号 / 身份证 / 家庭经济默认脱敏展示（`phoneMasked` `idCardMasked`）；心理**仅显示「需关注」标记，不显示明细**（普通老师只见标记） | 契约 profile 示例 L117；总册 §3.9 心理最小可见；施工图 L64「心理关注概览 D 包敏感权限后开放」 |
| 查看完整 | 走 `POST /students/{id}/sensitive/reveal`，必填 `reason≥5 字`，一次性返回不缓存 | 契约 #8 L112 |
| 审计留痕 | 敏感查看写 `t_security_audit_log`，`action=SENSITIVE_VIEW`，reason 入 detail；辅导员快速搜索查看学生 360 记 `resource=student_profile` | 契约 #8 审计列 L112；总册 §3.2 ⑪ L245 |
| 页面浏览不审计 | 进入工作台 / 总览页本身不审计；仅下钻敏感动作按目标业务规则审计 | 总册 §3.1 ⑪ L220、§3.2 ⑪ L245 |
| 导出审计 | 看板 / 工作台导出写导出台账，导出只导当前范围、脱敏（见 §10） | B 包卡 §3.1 L51；§3.2 L69 |
| 水印 | 敏感导出 / 明细页带水印（复用 `AppWatermark`，展示层，不替代后端审计） | CLAUDE.md §41 安全红线；§6 |
| 最小授权 | 学院排行卡仅学工处；心理明细除非授权不展示；校领导默认脱敏汇总 | 总册 §3.1 ⑦ L216；权限总控 L262 |

> **安全红线**：脱敏 / 授权 / 审计**由后端裁定**，前端隐藏不等于有权限（权限总控 L70）。工作台聚合接口必须过 `require_staff + scope` 链（总册 §3.1 ⑯ L225）。

---

## 8. API 契约草案

> 全部**复用已有契约**（`13A-学工中心API契约草案.md` #1–#5、#109、#128），本模块不新增业务写接口。错误码遵循既有 401/403/404/409/422 体系（契约总纲 L4、L42）。

### 8.1 学工总览
| # | 方法 / 路径 | 入参 | 出参 data 要点 | 权限点 | 审计 | 依据 |
|---|---|---|---|---|---|---|
| 1 | `GET /api/v1/student-affairs/dashboard` | semester?、dateRange?（角色 / 范围 token 解析） | `rolePreset` / `summaryCards[]` / `todoList[]` / `riskStudents[]` / `workflowPending{}` / `classOverview[]` / `warningTrends[]` / `recentActivities[]` | `studentAffairs.dashboard.view` | 无（读） | 契约 #1 L53–66 |

看板分栏（同页 `?panel=`，非独立接口，来源见 B 包卡 §8.1 L393–397）：
- `todos` → `GET /dashboard/todos`（`t_unified_todo`）
- `risk` → `GET /dashboard/risk-students`
- `leave` → 请假待审聚合（`t_affairs_leave_application`）
- `dorm` → `t_affairs_night_absence` + `t_affairs_dorm_inspection`
- `key-students` → `t_affairs_profile_extension.tags` + 风险 + 超期请假聚合

### 8.2 辅导员工作台
| # | 方法 / 路径 | 入参 | 出参 data 要点 | 权限点 | 审计 | 依据 |
|---|---|---|---|---|---|---|
| 2 | `GET /api/v1/student-affairs/counselor/workbench` | 无 | `myClasses / todayTodos / riskSummary / academicWarnings / pendingLeave / difficultStudents / employmentUnfilled / internshipExceptions / gdExceptions` | `studentAffairs.counselor.dashboard.view` | 无 | 契约 #2 L76 |
| 3 | `GET /api/v1/student-affairs/counselor/students` | keyword?、classId?、riskLevel?、page/pageSize | `list[{studentId,studentNo,realName,className,riskLevel,tags[]}]` | `studentAffairs.counselor.student.view` | 无 | 契约 #3 L77 |
| 4 | `GET /api/v1/student-affairs/counselor/todos` | status?、todoType?、page/pageSize | `list[{todoId,todoType,sourceModule,studentId,title,dueAt,status}]` | `studentAffairs.counselor.todo.handle` | 无 | 契约 #4 L78 |
| 5 | `GET /api/v1/student-affairs/counselor/risk-students` | riskLevel?、source?、status?、page/pageSize | `list[{riskId,studentId,realName,source,riskLevel,status,assignedAt}]` | `studentAffairs.counselor.risk.handle` | 无 | 契约 #5 L79 |

### 8.3 关联复用接口
| # | 方法 / 路径 | 用途 | 依据 |
|---|---|---|---|
| 128 | `GET /api/v1/mobile/teacher/affairs/workbench` | 教师小程序移动工作台聚合 | 契约 #128 L493 |
| 109 | `GET /api/v1/student-affairs/stats/{metricGroup}` | 指标下钻（含 counselor-kpi 待办完成率） | 契约 #109 L398、L409 |
| 8 | `POST /api/v1/student-affairs/students/{id}/sensitive/reveal` | 下钻敏感查看 | 契约 #8 L112 |

### 8.4 错误码
| 码 | 场景 | 依据 |
|---|---|---|
| 401001 | 未登录 | 契约 #1 L68 |
| 403001 | 学生令牌 / 非辅导员班主任角色 / 无任何学工权限点 | 契约 #1 L68、#2 L102 |
| 403002 | 具体学生越权（scope 内无该生） | 契约 #2 L102 |
| 404 | 学生 / 班级不存在 | 契约总纲错误码 |
| 409 | 状态冲突（下钻处理时，工作台本身不产生） | 契约总纲 |
| 422 | 入参校验失败（如 reason<5 字） | 契约 #8 L112 |

> **补强接口（backlog，不在本轮）**：`GET /counselor/workload-summary`（工作量沉淀）与新增参数键 `studentAffairs.counselor.followGapDays`（补丁 P-01，审计 L202–206）——标 planned，本卡不实现。

---

## 9. 数据表与迁移（MySQL utf8mb4）

> **核心结论：本模块无需新建任何表**。工作台是只读聚合，全部复用现有 `t_unified_*` / `t_affairs_*` / `t_workflow_*` / `t_student_*` / 教务与六大生命周期既有表。**严禁建平行看板 / 待办 / 消息表**（总册 §1「禁止自建消息表」L29；契约 §复用 L523「学工待办与消息不建新端点」；CLAUDE.md §37.9 核心表不乱建）。

| 表 | 复用 / 新增 | 工作台用途 | 关键约束 | 依据 |
|---|---|---|---|---|
| `t_unified_todo` | 复用 | 待办列表 / 今日待办 / 待办完成率 | 去重键 `source_module+source_biz_id+todo_type+assignee_id`；状态 PENDING/DONE/CANCELLED | 总册 §1 L29、§3.2 ⑥ L240 |
| `t_unified_message` | 复用 | 消息角标未读数 | 仅 8 类消息类型，只增不改 | 总册 §1 L29 |
| `t_affairs_risk_record` / `t_affairs_risk_event` | 复用 | 风险学生列表 / 风险概览 | 按 scope 过滤未关闭 | 总册 §3.1 ③ L210；B 包卡 §5.3 L266 |
| `t_workflow_task` / `t_workflow_instance` | 复用 | 待审请假等 workflowPending | PENDING 按处理人 | 总册 §3.1 ③ L210、§3.2 ③ L235 |
| `t_student_profile` | 复用（只读） | 学生数 / 快速搜索 / 画像跳转 | **不得复制形成双主数据** | 总册 §3.1 ⑯ L225；B 包卡 §3.3 L92 |
| `t_class` | 复用 | 我的班级 / classOverview | — | 总册 §3.2 ③ L235 |
| `t_teacher_student_scope` | 复用 | 辅导员 / 班主任数据范围 | `resolve_teacher_scope` | 权限总控 L5、L264 |
| `t_affairs_counselor_binding` | 复用 | 辅导员-班级绑定 | — | B 包卡 §3.2 表 L64 |
| `t_affairs_dashboard_metric` | 复用（若已建） | 看板指标缓存 | 存在性**需人工确认** | B 包卡 §3.1 表 L46 |
| `t_acad_warning` | 复用（只读引用） | 学业预警数 | 教务域**只读**，不在学工重录 | 总册 §3.2 ③ L235；索引 L41 |
| `t_emp_*` / `t_internship_*` / `t_gd_*` | 复用（只读口径） | 就业未填报 / 实习异常 / 毕设异常卡 | 读既有统计口径，不复制数据 | 总册 §3.1 ⑯ L225、§3.2 ⑯ L250 |
| `t_security_audit_log` / `t_affairs_audit_trail` | 复用 | 敏感查看 / 导出审计、recentActivities | append-only | 权限总控 L5；总册 §3.1 ③ L210 |

- **迁移动作**：本模块**不产生 Alembic 迁移**（无新表 / 无字段变更）。若后续补强包新增 `followGapDays` 参数，走 `t_platform_config` KV（无需建表，权限总控 L5），仍不需迁移。
- **MySQL 规范**：所依赖新表均已在 `数据表与迁移策略草案.md` 按 utf8mb4 + tenant_id + 审计字段 + 软删除建立（审计 L42「26 张新表 + 复用」）；本卡不重复定义。
- **需人工确认**：`t_affairs_dashboard_metric` 是否已在库中真实存在、字段结构（B 包卡引用但未见迁移证据）。

---

## 10. Excel 导入导出

> 本模块两页均为**只读聚合页**：**无 Excel 导入**（无业务录入）。仅「导出当前视图台账」。统一接入公共 Excel 底座 `backend/app/services/excel/` + 前端 `AppExportButton` / `AppExportConfirm`（CLAUDE.md §38.13；索引 L21）。

| 能力 | 是否需要 | 规则 | 依据 |
|---|---|---|---|
| 下载模板 / 上传 xlsx / 错误行下载 | **不适用** | 工作台无导入 | 只读页 |
| 导出当前范围 | 需要 | 按当前筛选 / 角色范围导出（学工总览指标 / 辅导员待办 / 风险学生列表） | B 包卡 §6 验收 L304「看板 / 画像摘要导出」 |
| 脱敏 | 强制 | 导出脱敏敏感字段（手机 / 身份证 / 家庭 / 心理明细一律不导出） | B 包卡 §3.1 L51；§7 |
| 导出审计 | 强制 | 写导出台账，含操作人 / 范围 / 时间 | B 包卡 §3.1 L51 |
| 文件名 | 规范 | 含模块名 + 学校 / 租户 + 时间（CLAUDE.md §38.8） | CLAUDE.md §38 |
| 水印 | 需要 | 导出 / 打印带水印 | CLAUDE.md §41 |

- **实现红线**：导出走真实后端 + 真实审计，**不得 mock 导出成功**（CLAUDE.md §40 安全红线；§38.9）。
- **需人工确认**：辅导员工作台「待办 / 风险学生」是否允许辅导员导出（涉学生名单 + 联系方式，属敏感导出，须理由 + 审计；B 包卡 §3.2 L69「批量导出需理由」）。

---

## 11. 移动端入口

> 依据：`13A-学工中心移动端入口设计.md`；契约 #128 L493；总册 §3.1 ⑮ L224、§3.2 ⑮ L249。

| 端 | 入口 | 口径 | 依据 |
|---|---|---|---|
| 学生小程序 | **无工作台**（学生不看工作台，看各业务进度页） | — | 总册 §3.1 ⑮ L224 |
| 教师小程序 | 工作台 Tab（`pages/teacher/*` 追加学工分组卡片）→ `GET /api/v1/mobile/teacher/affairs/workbench` | 高频聚合：`todos / pendingLeave / riskStudents / overdueLeave / dormExceptions`（可读 + 直达处理，写操作全部走 `/mobile/teacher/*` 包装） | 契约 #128 L493、L504；总册 §3.2 ⑯ L250 |
| 学工处 / 学院 PC 驾驶舱 | 移动端不承载（复杂多层级下钻仍走 PC） | — | 总册 §3.1 定位 |

- 移动端体验红线（审计 L174）：弱网草稿（工作台为只读，主要保证「防重复提交处理动作」）、敏感字段**不本地缓存**、状态错误码逐码提示。
- **可写口径**：教师移动工作台的处理 / 转派 / 提醒动作**必须走 `/mobile/teacher` 后端包装并过 scope**，不得前端直改（总册 §3.2 ⑯ L250）。

---

## 12. 验收标准（页面级用例）

> 结合 B 包卡 §6 验收清单（L298–306）与 §3.1/§3.2 验收行。两页均标「阻断 PC 试运行 + 阻断正式上线」（B 包卡 §7 L314/L316）。

### 12.1 学工总览
- [ ] 进入：`studentAffairs.dashboard.view` 有权可进；学生令牌→403001；无任何学工权限点→403001。
- [ ] 角色 preset：学工处见全校 + 学院排行卡；学院见本院、无排行卡（或按现场确认）；辅导员访问自动 302 至工作台。
- [ ] 数据范围：跨学院 / 跨租户不串数（B 包卡 §6「指标不串租户」L55）。
- [ ] 下钻对账：每张指标卡可点开到明细列表，**首页数字与列表数字 0 差异**（审计原则 9 L91；冻结表 §8 验收）。
- [ ] 三态：无数据→空卡 +「当前身份范围暂无数据」；单卡失败→卡内 error 不拖整页；加载→骨架屏（总册 §3.1 ④ L213）。
- [ ] 脱敏 + 审计：风险学生姓名脱敏；下钻敏感字段填原因≥5 字并写 SENSITIVE_VIEW。
- [ ] 导出：导当前范围、脱敏、写导出台账、带水印。
- [ ] 无假按钮 / 无假统计（B 包卡 L56）；旧路由 `/admin/student-affairs` 兼容不 404（若曾有旧看板入口，redirect，需人工确认旧入口）。

### 12.2 辅导员工作台
- [ ] 进入：`studentAffairs.counselor.dashboard.view` 有权可进；非辅导员 / 班主任→403001。
- [ ] 数据范围：**只见本人绑定班级 / 学生**；scope 为空→「未配置带班范围」文案（非 500）；越权学号→403002 + 审计。**严禁把全校待办给辅导员**（B 包卡 §3.2 L74）。
- [ ] 待办直达 + 销账：待办点击直达处理页；下游处理完成后该待办在工作台消失（`status=DONE` 回写，总册 L237）。
- [ ] 快速搜索：按姓名 / 学号 scope 内检索命中进 360；越权检索被拒 + 审计。
- [ ] 三态：无待办→完成态「今日已完成」；失败可重试（B 包卡 §3.2 L70）。
- [ ] 脱敏 + 审计：学生联系方式默认脱敏；查看 360 记 `resource=student_profile`；批量导出需理由。
- [ ] 公共组件：禁止自写指标卡 / 状态标签 / 权限按钮 / 批量条（B 包卡 §6 L306；CLAUDE.md §40/§41）。
- [ ] 移动端：教师小程序工作台 #128 与 PC 待办口径一致、同源不重复计数。

---

## 13. 依据文档索引（每条关键结论标来源 + 行号）

| 结论 | 来源文件 | 章节 / 行号 |
|---|---|---|
| 模块=2 个 planned 三级（学工总览 / 辅导员工作台） | `frontend/src/config/navPlan.js` | L81；`P()` 定义 L24–26 |
| 学工总览无状态机 / 只读聚合 / 三角色 preset / 8 卡 / 下钻 | `13A-学工中心全业务流程设计总册.md` | §3.1 L204–227 |
| 辅导员工作台聚合 / 四子接口 / 待办直达销账 / scope | 同上 | §3.2 L229–252 |
| dashboard 契约 #1（入参 / 出参 / 权限 / 错误码） | `13A-学工中心API契约草案.md` | §1 L49–68 |
| counselor 四接口 #2–#5 | 同上 | §2 L72–102 |
| 移动教师工作台 #128 / 统计下钻 #109 / 敏感查看 #8 | 同上 | L493、L398/L409、L112 |
| 三家对标（正方 / 强智 / 青果）+ 15 条精华 + 缺口表 | `13A-学工中心-商业化对标审计与补丁建议（第一轮）.md` | L6、L71–103、L107–130、§5 L138/L140 |
| 辅导员减负四件套补强（backlog） | 同上 | 补丁 P-01 L184–209 |
| 学工角色 / 数据范围 / 四层裁定 / 敏感 | `00-系统管理中心-权限角色模块授权与权责边界设计.md` | L70、L262–265、L5 |
| B 包页面卡（路由 / 数据来源 / 组件 / 验收 / 看板分栏） | `13A-学工中心B包-PC高频主线生产级施工卡.md` | §3.1 L40–56、§3.2 L58–74、§7 L308–384、§8.1 L389–397 |
| 规划状态「部分完成 / 未建独立 PC」+ 三级入口清单 | `13A-学工中心全量规划施工图.md` | L31、§2 L55–64 |
| 待办 / 消息复用不建新表、8 类消息 | 总册 / 契约 | 总册 §1 L29；契约 §复用 L523 |
| 表复用不建平行表、只读引用教务 | `文档关联索引.md` | §2 L38–47 |
| Excel 底座接入 / 打印导出归档模板 | `文档关联索引.md` | §导入导出 L21 |
| 规划占位页规则（planned 可点击进占位页、不标 implemented） | `CLAUDE.md` | §42 |

**需人工确认清单（读不到 / 有歧义的点）**：
1. 辅导员工作台路由 `counselor-workbench`（B 包卡）vs `workbench`（总册）——统一取值。
2. 学工处首页默认统计周期按学期还是学年（总册 ⑱ L227）。
3. 学院排行卡是否对学院管理员可见，还是仅学工处（总册 ⑱ L227；权限总控 L263）。
4. 班主任与辅导员是否同权同视图；「今日待办」是否含教务侧学业预警待办混排（总册 ⑱ L252）。
5. `t_affairs_dashboard_metric` 是否真实存在及字段结构（B 包卡引用，无迁移证据）。
6. 辅导员是否允许导出待办 / 风险学生名单（敏感导出口径）。
7. 各筛选枚举全集（riskLevel / todoType / source / status）——需与后端枚举核对。
8. 旧看板 / 在校服务是否有需 redirect 的历史入口（施工图 L51「在校服务过渡收口」）。

---

## 14. 施工顺序与依赖

### 14.1 前置依赖（必须先就绪）
| 依赖 | 说明 | 状态 |
|---|---|---|
| 数据范围函数 | `getStudentAffairsScope` / `getCounselorScope`（=`resolve_teacher_scope`） | 底座已有（权限总控 L5） |
| 统一待办 / 消息 | `t_unified_todo` / `t_unified_message` 及标已读端点 | 复用已有（契约 L523） |
| 权限点注册 | `studentAffairs.dashboard.*` / `studentAffairs.counselor.*` 在系统管理落库 | 需核对是否已注册（需人工确认） |
| 学生画像页 | 下钻目标（学生 360） | B 包同批（施工图 L32「部分完成」） |
| 各业务列表页 | 指标卡 / 待办下钻目标（请假 / 风险 / 宿舍等） | B 包 B3 / C 包并行 |

### 14.2 建议施工顺序（先总览后工作台，先真数据后补强）
1. **Step 1**：搭 PC 页壳（`AppPageShell` + `AppMetricCard` + `AppToolbar`），接 `GET /dashboard` 真数据出指标卡（禁止假统计）。→ commit `feat(student-affairs): add student-affairs dashboard shell with real metrics`
2. **Step 2**：学工总览三角色 preset + 逐卡下钻 + 首页-列表 0 差异对账 + 三态。→ commit `feat(student-affairs): dashboard role preset and drilldown`
3. **Step 3**：辅导员工作台 `GET /counselor/workbench` + 四子接口 + 快速搜索进 360 + 待办直达销账 + scope 裁剪。→ commit `feat(student-affairs): add counselor workbench with scope`
4. **Step 4**：敏感脱敏 / 导出审计 / 水印 / 权限按钮接公共组件；教师小程序 #128 对齐。→ commit `feat(student-affairs): workbench sensitive masking and export audit`
5. **Step 5**：navPlan 将两叶子从 `P('学工总览','辅导员工作台')` 改为 `I(label, path)`（**由甲方在导航施工时统一操作，本卡不改**），占位路径自动让位，即「做完一个亮一个」验收信号（§42.5）。
6. **Step 6（backlog，另起施工包 A）**：补丁 P-01 辅导员减负四件套（紧急度排序 / 多风险合并 / 一键联系 / 工作量沉淀）——标 planned，不并入本轮 implemented。

### 14.3 风险点
- **假闭环风险**：MEMORY 记录教务中心曾「前端假闭环」；本模块严守 B 包卡「不得用假统计填充」（L56），所有卡必须接真实后端。
- **数据范围放大风险**：辅导员 scope 为空时若回退全租户即越权——必须走空列表策略（契约 #2 L102）。
- **口径撞车风险**：工作台待办完成率 / 谈话数等须与各业务 stats 同源（同一 stats 函数），杜绝两套数（补丁 P-01 说明 L196）。
- **路由 / 权限点未确认**：见 §13 需人工确认清单第 1、7 条，开发前须与后端 + navPlan 对齐。
- **占位页边界**：施工完成前保持 planned，不得因占位页存在把模块标 implemented（§42.4）。

### 14.4 commit 粒度建议
按 §14.2 每步一个 commit，均以 `feat(student-affairs):` 前缀；不混入其它模块改动；不提交 dist / node_modules / .env / .claude（B 包卡强制边界 L13）。完成后按 §35 更新 `docs/施工记录/历史欠账.md`，登记本轮关闭 / 新增欠账（如补丁 P-01 列 backlog）。

---

> **本卡边界声明**：本文档仅为设计施工卡，未改动任何代码 / navPlan / 配置 / 迁移。两个三级页面当前为 `planned`，其路由 / API / 字段均引用现有设计文档（已标行号来源），非本卡臆造；凡设计文档未覆盖处已在 §13 标「需人工确认」。
