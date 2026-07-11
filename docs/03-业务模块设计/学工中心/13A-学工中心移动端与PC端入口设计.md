# 13A 学工中心移动端与PC端入口设计（六端汇总）



> 依据：[需求输入](../跨模块融合/_13-需求输入-V1.1.md)、[集成事实速查](../跨模块融合/_13-现有系统集成事实速查.md)；页面编号与路由基准：[13A-学工中心页面树与路由设计.md](./13A-学工中心页面树与路由设计.md)；移动端逐页规格：[13A-学工中心移动端入口设计.md](./13A-学工中心移动端入口设计.md)；跨端一致性：[13A-13B-跨端一致性与数据联动矩阵.md](../跨模块融合/13A-13B-跨端一致性与数据联动矩阵.md)。跨夹路径总表见 [文档关联索引.md](./文档关联索引.md)。

> 命名口径（裁定）：13A = `student-affairs`（PC `/admin/student-affairs/*`、权限点 `studentAffairs.*`、模块授权项 `student-affairs`）。

> 图例：★=V1 必做；☆=P2/P3；◇=随学生 PC 门户（09B）落地时接入，V1 不开。本文只做设计，不写代码、不改路由。



---



## 1. 六端总览



| 端 | 13A 入口形态 | V1 | 说明 |

|---|---|---|---|

| E1 学校PC管理端 | 一级菜单「学工中心」+ 90 页路由树 | ★（69 页） | 全量管理端，adminMenu 挂载 |

| E2 学生PC门户 | 门户「学工服务」分组 6 入口 | ◇ | 随 09B 落地时接入；V1 学生入口以小程序为准 |

| E3 教师PC工作台 | 学工首页角色 preset + 辅导员工作台 + 审批处置页 | ★ | 现为 /admin 内多角色工作台（09A 形态） |

| E4 学生小程序 | 服务大厅「学工服务」宫格 11 入口 | ★（8 个） | 引用《13A-学工中心移动端入口设计.md》第二章 |

| E5 教师移动端 | 工作台扩展 + 8 入口 | ★ | 引用同文档第三章；重操作回 PC（§3.9 总表） |

| E6 平台运营端 | 模块授权项 `student-affairs` 开关 + 学工规则组 | ★ | 复用现有平台管理端，不新建 |



---



## 2. E1 学校 PC 管理端入口



### 2.1 菜单挂载点与 adminMenu 接入方式



现状（证据：frontend/src/config/adminMenu.js）：

- `ADMIN_MENU` 为跨模块导航唯一事实来源，二级树结构（分组 → 叶子 {key,label,path,moduleCode,permissionKey}）；

- 可见性由 `getVisibleAdminMenu(ctx)` 按 `ctx.currentRole.roleType`（ROLE_TYPE 白名单 ROLE_MODULE_ALLOW）与 `ctx.permissionActions` 过滤；

- 铁律：不硬编码校名（品牌来自 ctx.tenantBrandConfig）、不硬编码角色、路径与 router/index.js 及模块 routes 文件一致（kebab-case）。



13A 接入设计（描述性契约，不改代码）：



1. **新增一级分组** `student-affairs`（label「学工中心」），插在「学生中心」分组之后；叶子节点示例：



| key | label | path | moduleCode | permissionKey |

|---|---|---|---|---|

| sa-home | 学工首页 | /admin/student-affairs | STUDENT_AFFAIRS | studentAffairs.dashboard.view |

| sa-workbench | 辅导员工作台 | /admin/student-affairs/workbench | STUDENT_AFFAIRS | studentAffairs.counselor.dashboard.view |

| sa-students | 学生信息与画像 | /admin/student-affairs/students | STUDENT_AFFAIRS | studentAffairs.student.view |

| sa-classes | 班级管理 | /admin/student-affairs/classes | STUDENT_AFFAIRS | studentAffairs.class.view |

| sa-leave | 请假管理 | /admin/student-affairs/leave | STUDENT_AFFAIRS | studentAffairs.leave.view |

| sa-aid | 困难认定 | /admin/student-affairs/aid/batches | STUDENT_AFFAIRS | studentAffairs.aid.view |

| sa-funding | 奖助勤贷 | /admin/student-affairs/funding/projects | STUDENT_AFFAIRS | studentAffairs.funding.view |

| sa-discipline | 违纪处分 | /admin/student-affairs/discipline | STUDENT_AFFAIRS | studentAffairs.discipline.view |

| sa-risk | 心理与风险预警 | /admin/student-affairs/risk | STUDENT_AFFAIRS | studentAffairs.risk.view（心理列表另有强权限点 psy.view） |

| sa-talk | 谈心谈话 | /admin/student-affairs/talk/plans | STUDENT_AFFAIRS | studentAffairs.talk.view |

| sa-dorm | 宿舍与公寓 | /admin/student-affairs/dorm/buildings | STUDENT_AFFAIRS | studentAffairs.dorm.view |

| sa-archive | 学工归档 | /admin/student-affairs/archive/batches | STUDENT_AFFAIRS | studentAffairs.archive.view |

| sa-stats | 学工统计 | /admin/student-affairs/stats | STUDENT_AFFAIRS | studentAffairs.stats.view |



2. **ROLE_MODULE_ALLOW 扩展**：`SCHOOL_ADMIN`、`COUNSELOR` 白名单加入 `STUDENT_AFFAIRS`；`ACADEMIC_STAFF` 不加入（学工非其职责域）；`AUDITOR` 仅经审计视图访问；`PLATFORM` 保持仅 PLATFORM。角色内细分（学工处/学院学工/辅导员/宿管/资助/心理）由 permissionKey + 数据范围函数收敛，不在菜单层硬编码。

3. **路由注册形态**：新增 `frontend/src/modules/studentAffairs/`（api/ routes/ views/ 三段式），routes 文件导出后并入 router/index.js 的 moduleRoutes 展平数组（与既有 11 模块相同接入模式）；静态段（create/stats/config）先于 `:id` 动态段注册。

4. **模块授权联动**：`GET /api/v1/authz/modules` 返回项中 `student-affairs` 状态为 SUSPENDED 时整组菜单隐藏、EXPIRED_READONLY 时打只读标（authz 1.10 已有 readonly 打标机制，证据：backend/app/api/v1/authz.py 183~193 行）。



### 2.2 PC 管理端入口清单（按功能组汇总，页面级明细见页面树文档）



| 页面/功能组 | 路由（前缀 /admin/student-affairs） | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|

| 学工首页（角色 preset 6 区块） | `/` | 处/院/辅/班 | ★ | BasePortalLayout、Dashboard 卡片模式、stats 聚合 | docs/03-业务模块设计/学工中心/13A-学工中心页面树与路由设计.md §2-01、backend/app/api/v1/stats.py |

| 辅导员工作台（7 区块） | `/workbench` | 辅/班（处/院预览） | ★ | 工作台卡片、t_unified_todo 列表组件 | 同上 §2-02、backend/app/api/v1/todo.py |

| 学生列表/画像/时间线 | `/students`、`/students/:studentId/profile`、`/timeline` | 处/院/辅/班/心(授权)/资(业务) | ★ | 学生360聚合（mobile teacher student/{id} 的 PC 版扩展）、MobileSensitiveText 同源脱敏规则 | backend/app/services/mobile_teacher_service.py、backend/app/models/student.py |

| 班级管理 5 页 | `/classes/*` | 处/院/辅/班 | ★ | 组织表 t_college/t_major/t_class 直读 | backend/app/models/org.py |

| 请假管理 8 页（列表/详情/代录/审批/销假/续假/统计/配置） | `/leave/*` | 处/院/辅/班（节点人审批） | ★ | Workflow 审批组件、t_cs_leave 扩展 | backend/app/models/campus_service.py、backend/app/models/approval.py |

| 困难认定 8 页 | `/aid/*` | 处/资/院/辅 | ★ | 导入导出管线、脱敏+审计守卫 | backend/app/services/domain_export_service.py、frontend/src/security/guards/export.guard.js |

| 奖助勤贷 12 页 | `/funding/*` | 处/资/院/辅（07-9 考核 ☆P2） | ★（11 页） | 统一资助抽象、公示组件复用困难认定 | docs/03-业务模块设计/学工中心/13A-学工中心页面树与路由设计.md §3.5 |

| 违纪处分 7 页 | `/discipline/*` | 处/院/辅（登记）、节点人（审批） | ★ | Workflow、t_cs_discipline 升级 | backend/app/models/campus_service.py |

| 心理与风险 6+1 页 | `/risk/*`（09-7 测评 ☆P3） | 处/院/辅/心（强权限） | ★ | 风险表新建、心理沿用 t_cs_mental_record 强权限 | backend/app/models/campus_service.py |

| 谈心谈话 5 页 | `/talk/*` | 辅/班/心（处/院看统计） | ★ | — | docs/03-业务模块设计/学工中心/13A-学工中心页面树与路由设计.md §3.8 |

| 宿舍与公寓 8+3 页 | `/dorm/*`（智能排宿/纪律/文明寝室 ☆） | 处/宿/院/辅 | ★（8 页） | t_cs_dorm_record/exception 扩展、迎新分宿数据衔接 | backend/app/models/campus_service.py、backend/app/models/orientation.py |

| 家校/活动/荣誉测评 16 页 | `/family/*`、`/activities/*`、`/honors` 等 | 处/院/辅 | ☆ P2/P3 | — | docs/03-业务模块设计/学工中心/13A-学工中心页面树与路由设计.md §3.10 |

| 学工归档 5 页 | `/archive/*` | 处/院（辅补缺） | ★ | 导出水印管线、t_export_task 留痕 | backend/app/services/domain_export_service.py |

| 学工统计 | `/stats` | 处/院（辅本班切片） | ★ | stats_service 扩展聚合 | backend/app/services/stats_service.py |



**降级与守卫**：全站强制登录（无 token 跳 /login）→ 权限点守卫（无权限渲染 noPermission 态）→ 数据范围后端校验（403002/404001+审计）；demo-school 写操作 403 引导沙箱（证据：frontend/src/router/index.js、_13-现有系统集成事实速查.md §2/§9）。



### 2.3 页面级入口与菜单归属明细（90 页 → 13 菜单叶子）



> 页面编号/路由/角色与《13A-学工中心页面树与路由设计.md》§3 逐行对齐（该文档为唯一基准）；本表新增「归属菜单叶子」列，说明每页从哪个 adminMenu 叶子进入。角色缩写：处=学工处；院=学院学工；辅=辅导员；班=班主任；心=心理老师；宿=宿管；资=资助老师。



**首页 / 工作台 / 学生画像 / 班级（叶子 sa-home / sa-workbench / sa-students / sa-classes）**



| 页 | 页面 | 路由（省略 /admin/student-affairs） | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 01 | 学工首页 | `/` | 处/院/辅/班（角色 preset） | ★ | sa-home（登录后默认页） |

| 02 | 辅导员工作台 | `/workbench` | 辅/班（处/院预览） | ★ | sa-workbench |

| 03-1 | 学生列表 | `/students` | 处/院/辅/班/心(授权)/资(业务) | ★ | sa-students |

| 03-2 | 学生画像详情 | `/students/:studentId/profile` | 同上（越权 403+审计） | ★ | sa-students（行点击） |

| 03-3 | 成长时间线 | `/students/:studentId/timeline` | 同 03-2 | ★ | sa-students（画像页签） |

| 04-1 | 班级列表 | `/classes` | 处/院/辅/班 | ★ | sa-classes |

| 04-2 | 班级详情 | `/classes/:classId` | 同上（范围内） | ★ | sa-classes |

| 04-3 | 班级学生 | `/classes/:classId/students` | 同上 | ★ | sa-classes（详情页签） |

| 04-4 | 班级画像 | `/classes/:classId/profile` | 同上 | ★ | sa-classes（详情页签） |

| 04-5 | 班级材料 | `/classes/:classId/materials` | 同上 | ★ | sa-classes（详情页签/归档补缺） |



**请假管理（叶子 sa-leave）**



| 页 | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 05-1 | 请假列表 | `/leave` | 处/院/辅/班 | ★ | sa-leave |

| 05-2 | 请假详情 | `/leave/:leaveId` | 同上（范围内） | ★ | sa-leave（行/待办/消息） |

| 05-3 | 新增请假（代录） | `/leave/create` | 辅/院/处 | ★ | sa-leave（列表按钮） |

| 05-4 | 请假审批 | `/leave/:leaveId/approve` | 当前节点人（辅→院→处） | ★ | 统一待办直达 |

| 05-5 | 销假确认 | `/leave/:leaveId/cancel-confirm` | 辅（本班） | ★ | 统一待办直达 |

| 05-6 | 续假审批 | `/leave/:leaveId/extension` | 按续假总天数定节点 | ★ | 统一待办直达 |

| 05-7 | 请假统计 | `/leave/stats` | 处/院（辅本班切片） | ★ | sa-leave/sa-stats 下钻 |

| 05-8 | 请假规则配置 | `/leave/config` | 处（接平台规则中心） | ★ | sa-leave（管理组） |



**困难认定（叶子 sa-aid）**



| 页 | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 06-1 | 认定批次列表 | `/aid/batches` | 处/资/院 | ★ | sa-aid |

| 06-2 | 批次详情与配置 | `/aid/batches/:batchId` | 处/资（院只读） | ★ | sa-aid |

| 06-3 | 认定申请列表 | `/aid/applications` | 处/资/院/辅 | ★ | sa-aid |

| 06-4 | 申请详情 | `/aid/applications/:applyId` | 同上（家庭经济脱敏，看完整必审计） | ★ | sa-aid（行/待办） |

| 06-5 | 申请审核（班评/初审/复审/终审同页分节点） | `/aid/applications/:applyId/review` | 当前节点人 | ★ | 统一待办直达 |

| 06-6 | 公示管理 | `/aid/publicity` | 处/资 | ★ | sa-aid |

| 06-7 | 困难学生库 | `/aid/difficult-students` | 处/资/院/辅（脱敏+水印） | ★ | sa-aid |

| 06-8 | 认定统计 | `/aid/stats` | 处/资/院 | ★ | sa-aid/sa-stats 下钻 |



**奖助勤贷（叶子 sa-funding）**



| 页 | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 07-1 | 资助项目列表 | `/funding/projects` | 处/资 | ★ | sa-funding |

| 07-2 | 项目批次配置 | `/funding/batches/:batchId` | 处/资 | ★ | sa-funding |

| 07-3 | 资助申请列表 | `/funding/applications` | 处/资/院/辅 | ★ | sa-funding |

| 07-4 | 资助申请详情 | `/funding/applications/:applyId` | 同上（范围内） | ★ | sa-funding（行/待办） |

| 07-5 | 资助申请审核 | `/funding/applications/:applyId/review` | 当前节点人（辅→院评审→校复核） | ★ | 统一待办直达 |

| 07-6 | 公示管理 | `/funding/publicity` | 处/资 | ★ | sa-funding |

| 07-7 | 获奖/受助名单 | `/funding/results` | 处/资/院 | ★ | sa-funding |

| 07-8 | 勤工岗位管理 | `/funding/work-study/jobs` | 资/用工部门管理员 | ★ | sa-funding |

| 07-9 | 勤工月度考核 | `/funding/work-study/assessments` | 资/用工部门管理员 | ☆P2 | sa-funding（权限点隐藏） |

| 07-10 | 贷款登记列表 | `/funding/loans` | 资/辅（本班） | ★ | sa-funding |

| 07-11 | 贷款登记详情/核对 | `/funding/loans/:loanId` | 资/辅（核对节点） | ★ | sa-funding（行/待办） |

| 07-12 | 资助统计 | `/funding/stats` | 处/资/院 | ★ | sa-funding/sa-stats 下钻 |



**违纪处分（叶子 sa-discipline）**



| 页 | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 08-1 | 处分列表 | `/discipline` | 处/院/辅（字段收敛） | ★ | sa-discipline |

| 08-2 | 处分登记 | `/discipline/create` | 辅/院/处 | ★ | sa-discipline（列表按钮） |

| 08-3 | 处分详情 | `/discipline/:caseId` | 处/院/辅（范围内） | ★ | sa-discipline（行/待办/画像页签） |

| 08-4 | 处分审批 | `/discipline/:caseId/approve` | 节点人（院→处→严重时校级） | ★ | 统一待办直达 |

| 08-5 | 处分解除申请 | `/discipline/:caseId/remove-apply` | 辅（代发起）/学生（小程序发起） | ★ | sa-discipline（详情按钮） |

| 08-6 | 处分解除审批 | `/discipline/remove/:removeId/approve` | 节点人（辅→院→处终审） | ★ | 统一待办直达 |

| 08-7 | 处分统计 | `/discipline/stats` | 处/院 | ★ | sa-discipline/sa-stats 下钻 |



**心理与风险（叶子 sa-risk）**



| 页 | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 09-1 | 风险列表 | `/risk` | 处/院/辅（心理来源仅心/授权辅见明细） | ★ | sa-risk |

| 09-2 | 风险详情 | `/risk/:riskId` | 同上（按来源收敛） | ★ | sa-risk（行/待办/画像） |

| 09-3 | 风险处置 | `/risk/:riskId/handle` | 被分派责任人 | ★ | 统一待办直达 |

| 09-4 | 心理关注列表 | `/risk/psychological` | 心/授权辅（强权限） | ★ | sa-risk（sensitive 标记） |

| 09-5 | 风险规则配置 | `/risk/config` | 处（接平台规则中心） | ★ | sa-risk（管理组） |

| 09-6 | 风险统计 | `/risk/stats` | 处/院（导出默认不含心理明细） | ★ | sa-risk/sa-stats 下钻 |

| 09-7 | 心理测评集成 | `/risk/psychological/assessments` | 心 | ☆P3 | 隐藏 |



**谈心谈话（叶子 sa-talk）**



| 页 | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 10-1 | 谈话计划 | `/talk/plans` | 辅/班/心（处/院看统计） | ★ | sa-talk |

| 10-2 | 谈话记录列表 | `/talk/records` | 辅/班/心（本人）；处/院汇总 | ★ | sa-talk |

| 10-3 | 新增谈话记录 | `/talk/records/create` | 辅/班/心 | ★ | sa-talk（列表/风险转谈话） |

| 10-4 | 谈话记录详情 | `/talk/records/:recordId` | 记录人/授权角色（心理类强权限） | ★ | sa-talk（行/时间线） |

| 10-5 | 谈话统计 | `/talk/stats` | 处/院（工作量） | ★ | sa-talk/sa-stats 下钻 |



**宿舍与公寓（叶子 sa-dorm）**



| 页 | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 11-1 | 房源管理 | `/dorm/buildings` | 处/宿（负责楼栋） | ★ | sa-dorm |

| 11-2 | 入住与床位分配 | `/dorm/allocation` | 处/宿/院 | ★ | sa-dorm |

| 11-3 | 调宿申请列表 | `/dorm/transfers` | 处/宿/院/辅 | ★ | sa-dorm |

| 11-4 | 调宿审批 | `/dorm/transfers/:transferId/approve` | 节点人（辅→宿管，床位校验） | ★ | 统一待办直达 |

| 11-5 | 宿舍检查任务 | `/dorm/inspections` | 处/宿 | ★ | sa-dorm |

| 11-6 | 检查记录录入 | `/dorm/inspections/:taskId/records` | 宿（负责楼栋） | ★ | sa-dorm |

| 11-7 | 宿舍异常 | `/dorm/exceptions` | 处/宿/院/辅 | ★ | sa-dorm（首页异常卡直达） |

| 11-8 | 宿舍统计 | `/dorm/stats` | 处/院/宿 | ★ | sa-dorm/sa-stats 下钻 |

| 11-9~11-11 | 智能排宿/公寓纪律/文明寝室 | `/dorm/smart-allocation` 等 | 处/宿/院 | ☆P2 | 隐藏 |



**家校/活动/荣誉测评（P2/P3，V1 菜单隐藏）**：12-1~12-3（/family/*）、13-1~13-9（/activities、/volunteer、/clubs、/organizations、/second-class、/party-league、/moral-score）、14-1~14-4（/honors、/evaluation、/ideology-team、/counselor-assessment），共 16 页，全部 ☆，由权限点隐藏不做占位页。



**归档与统计（叶子 sa-archive / sa-stats）**



| 页 | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 15-1 | 归档批次列表 | `/archive/batches` | 处/院（辅见涉己补缺） | ★ | sa-archive |

| 15-2 | 创建归档批次 | `/archive/batches/create` | 处 | ★ | sa-archive |

| 15-3 | 批次详情（档案包） | `/archive/batches/:batchId` | 处/院/辅（范围内） | ★ | sa-archive（行/补缺待办） |

| 15-4 | 完整性审核与确认 | `/archive/batches/:batchId/review` | 院（完整性）→处（确认） | ★ | 统一待办直达 |

| 15-5 | 归档统计 | `/archive/stats` | 处/院 | ★ | sa-archive/首页归档率卡 |

| 16-1 | 统计总览 | `/stats` | 处/院（辅本班切片） | ★ | sa-stats |



**计数核对**：PC 页面 90（V1 ★69 / ☆21），与页面树文档 §6 一致。



---



## 3. E3 教师 PC 工作台入口



> 现状：教师 PC 即 /admin 管理端内的多角色工作台（09A 修订形态）——默认页 AdminWorkbenchView，authz 按 activeContext 下发菜单/按钮/数据范围（证据：frontend/src/views/AdminWorkbenchView.vue、backend/app/api/v1/authz.py 1.6~1.11）。13A 不新建教师端工程，只做「身份化入口」。



| 入口 | 页面/路由 | 角色（activeContext） | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|

| 辅导员工作台 | /admin/student-affairs/workbench | 辅导员/班主任 | ★ | 09A 工作台卡片模式 + getCounselorScope（resolve_teacher_scope 封装） | docs/08-历史记录与归档/source-design/09A（6.9）、backend/app/services/mobile_teacher_service.py |

| 学工首页·学工处视图 | /admin/student-affairs | 学工处管理员 | ★ | Dashboard preset | docs/08-历史记录与归档/source-design/09A（6.4 学工处工作台） |

| 学工首页·学院视图 | /admin/student-affairs（同页 preset） | 学院学工管理员 | ★ | 同上（本学院切片） | 同上 |

| 请假审批 | /admin/student-affairs/leave/:leaveId/approve | 当前节点人（辅→院→处） | ★ | 审批中心组件 + workflow task version 乐观锁 | frontend/src/modules/approval/、backend/app/models/approval.py |

| 困难/奖助/处分/调宿审批 | /aid/…/review、/funding/…/review、/discipline/…/approve、/dorm/transfers/…/approve | 各节点人 | ★ | 同上（统一「业务详情+任务操作区」组合页） | docs/03-业务模块设计/学工中心/13A-学工中心页面树与路由设计.md §1-4 |

| 风险处置/谈话记录 | /risk/:riskId/handle、/talk/records/create | 被分派责任人/辅/心 | ★ | — | 同上 §3.7/§3.8 |

| 宿管工作台入口 | /dorm/buildings、/dorm/inspections | 宿管（scope_type=DORM_BUILDING） | ★ | t_teacher_student_scope 扩枚举 | backend/app/models/teacher_scope.py |

| 资助老师入口 | /aid、/funding（业务范围过滤） | 资助老师（AID_STUDENT） | ★ | 同上 | 同上 |

| 心理老师入口 | /risk/psychological | 心理老师（PSY_STUDENT，强权限） | ★ | 菜单 sensitive 标记机制（adminMenu 已有 sensitive 字段） | frontend/src/config/adminMenu.js |

| 统一待办入口 | 顶栏待办数 + /admin/approval | 全教职工 | ★ | t_unified_todo 同源计数 | backend/app/api/v1/todo.py |



**身份切换规则**（沿用 09A/authz 现状）：切换 activeContext 后菜单/待办/数据范围整体刷新（authz 1.8 返回 menusChanged=true），不同身份权限不合并；13A 各工作台视图按 contextType 渲染 preset，不写死角色菜单。



---



## 4. E2 学生 PC 门户入口（◇ 随 09B 落地时接入）



> 现状如实标注：09B 设计已存在（docs/08-历史记录与归档/source-design/09B）；主工程有门户壳 frontend/src/layouts/StudentPortalLayout.vue（学生轻菜单：首页/待办/消息/材料/毕设/实习/就业/个人中心，硬约束禁止管理端菜单）；独立骨架工程 student-portal/ 有 `/portal/home`、`/portal/:module` 模板路由与 ModuleDisabledView/NotEnabledView 降级组件；后端有门户配置管理端 API（backend/app/api/v1/student_portal_admin.py）。**业务路由未全量实现，本轮不开学生 PC 门户，V1 学生入口以小程序为准。**



13A 门户入口规划（落地时接入，全部 ◇）：



| 入口 | 门户页面/路由（student-portal 工程） | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|

| 学工服务分组页 | /portal/student-affairs（经 /portal/:module 模板注册） | 学生本人 | ◇ | ModuleCard、moduleRegistry 注册制 | student-portal/src/platform/moduleRegistry.js |

| 我的请假（长表单/材料增强） | /portal/student-affairs/leave | 学生本人 | ◇ | FileDropzone（大文件）、StatusTag | student-portal/src/components/FileDropzone.vue |

| 困难认定申请（长表单场景，PC 优势项） | /portal/student-affairs/aid | 学生本人 | ◇ | SensitiveText、ProgressTimeline | student-portal/src/components/SensitiveText.vue |

| 奖助申请与公示结果 | /portal/student-affairs/funding | 学生本人 | ◇ | 同上 | 同上 |

| 我的宿舍/调宿申请 | /portal/student-affairs/dorm | 学生本人 | ◇ | DataPanel | student-portal/src/components/DataPanel.vue |

| 我的处分/解除申请 | /portal/student-affairs/discipline | 学生本人 | ◇ | StatusTag | — |

| 我的待办/消息（学工条目自动汇入） | /portal/home、TodoPanel | 学生本人 | ◇（门户框架项） | TodoPanel（读 t_unified_todo/message，与小程序同源） | student-portal/src/components/TodoPanel.vue |



**接入原则**：① 与小程序共用同一 student_id/API（`/api/v1/mobile/affairs/*`）/待办/消息/审计（09B §1.3），门户不新建业务端点；② 模块未开通渲染 NotEnabledView，到期渲染 ModuleDisabledView（菜单灰显、历史可查、写按钮隐藏，09B §3.3）；③ 门户菜单经 StudentPortalLayout 的 menus props 注入「学工服务」项，禁止出现管理端菜单。



---



## 5. E4 学生小程序入口（★ V1 学生唯一入口）



> 页面级 41 项规格全部引用《13A-学工中心移动端入口设计.md》第二章（S-01~S-11），本节只给汇总清单与挂载设计，不重复展开。



### 5.1 入口清单



| # | 入口 | 页面路径 | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|---|

| S-01 | 我的请假（列表/详情/新增） | pages/student/affairs/leave/list·detail·create | 学生本人 | ★ | 既有 campus-service 请假提交页升级重定向；MobileGlobalState/createSubmitLock | docs/03-业务模块设计/学工中心/13A-学工中心移动端入口设计.md S-01/§4.2、miniapp/src/pages.json |

| S-02 | 销假/续假 | pages/student/affairs/leave/cancel·extension | 学生本人 | ★ | 同上 | 同上 S-02 |

| S-03 | 困难申请（批次驱动） | pages/student/affairs/aid/apply·detail | 学生本人 | ★ | MobileSensitiveText（家庭经济脱敏）、分步表单本地暂存 | 同上 S-03 |

| S-04 | 奖助申请 | pages/student/affairs/funding/list·apply·detail | 学生本人 | ★ | 422 拦截原因映射表单提示条 | 同上 S-04 |

| S-05 | 勤工申请 | pages/student/affairs/work-study/jobs·detail·my | 学生本人 | ★基础 | — | 同上 S-05 |

| S-06 | 我的处分（生效后可见+解除申请） | pages/student/affairs/discipline/my·detail·remove-apply | 学生本人 | ★ | t_cs_discipline「只回数量」原则升级为生效后可见明细 | 同上 S-06、backend/app/models/campus_service.py |

| S-07 | 我的谈话摘要（心理类不下发） | pages/student/affairs/talk/my | 学生本人 | ★ | 后端出口过滤，前端零敏感判断 | 同上 S-07 |

| S-08 | 我的宿舍（信息/调宿/检查结果） | pages/student/affairs/dorm/my·transfer | 学生本人 | ★ | — | 同上 S-08 |

| S-09 | 我的活动 | pages/student/affairs/activities/* | 学生本人 | ☆P2 | — | 同上 S-09 |

| S-10 | 德育积分 | pages/student/affairs/moral-score/my | 学生本人 | ☆P2 | — | 同上 S-10 |

| S-11 | 家校联系人 | pages/student/affairs/family/contacts | 学生本人 | ☆P2-lite（V1 只读查看） | MobileSensitiveText（t_student_contact 出口脱敏） | 同上 S-11、backend/app/models/student.py |



### 5.2 底部导航与服务大厅挂载



1. **不新增底部 tab**：沿用既有学生端导航（首页/消息/我的等，miniapp/src/pages.json 现状），13A 全部入口收进首页「学工服务」宫格分组（08A「一个服务大厅」原则，docs/08-历史记录与归档/source-design/08A §7）。

2. **宫格排序（V1）**：请假 → 我的宿舍 → 困难认定（批次亮起）→ 奖助学金（批次亮起）→ 勤工助学 → 我的处分（有生效记录才显示）→ 谈心谈话 → 家校联系人；P2 增补活动/德育积分后重排一次（引用移动端入口设计 §4.3）。

3. **角标规则**：宫格/消息角标 = t_unified_todo（本人未处理）+ t_unified_message（本人未读）分组计数；点开即调「标已读」，onShow 重拉校准，禁止本地扣减不校准。

4. **消息深链**：WORKFLOW_RESULT/RETURNED_NOTICE→业务详情；DEADLINE_REMINDER→销假面板；PUBLISHED_NOTICE→批次页/宿舍页；STATUS_CHANGED→对应详情（映射表引用移动端入口设计 §4.3）。

5. **模块授权降级**：`student-affairs` 关闭 → 宫格分组整体不渲染（不出现空壳页/悬空跳转），在途单据经「我的申请」历史只读可查。



### 5.3 消息类型 → 学生端路由映射（统一消息驱动深链）



| 消息类型（t_unified_message） | 触发场景 | 点击跳转 |

|---|---|---|

| WORKFLOW_RESULT | 请假/困难/奖助/勤工/解除/调宿审批结果 | 对应业务详情页（S-01/S-03/S-04/S-05/S-06/S-08） |

| RETURNED_NOTICE | 各类申请被退回 | 对应表单页（RETURNED 态可修改重交） |

| DEADLINE_REMINDER | 请假到期前销假提醒 | S-02 销假面板（携单据 id） |

| PUBLISHED_NOTICE | 困难/奖助批次发布、排宿发布、勤工岗位发布 | S-03/S-04 批次页、S-08 宿舍页、S-05 岗位列表 |

| STATUS_CHANGED | 处分送达、谈话完成、检查异常、积分变动 | S-06 详情、S-07 摘要、S-08 结果页签、S-10 |

| RISK_ALERT | 学生侧一般不下发（教师侧为主）；家校提醒场景 P2 | —（P2 定义） |

| ARCHIVE_NOTICE | 学生侧不下发（教师补缺提醒） | — |



规则：点击即调既有「标已读」端点，角标实时递减；消息路由按 source_module + 业务 id 解析，目标不存在（已撤销）时 404 提示并回列表刷新（引用移动端入口设计 §1.4）。



---



## 6. E5 教师移动端入口（★）



> 逐页规格引用《13A-学工中心移动端入口设计.md》第三章（T-01~T-08）与 §3.9「移动端可办 vs 必须回 PC 总表」。



| # | 入口 | 页面路径 | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|---|

| T-01 | 教师工作台（学工角标聚合） | pages/teacher/workbench（既有页扩展）+ pages/teacher/affairs/todos | 辅/班/宿/心/资 | ★ | 既有工作台页扩展区块；t_unified_todo 同源计数 | miniapp/src/pages/teacher/workbench、docs/03-业务模块设计/学工中心/13A-学工中心移动端入口设计.md T-01 |

| T-02 | 请假审批（普通假移动终审；长假流转后回 PC） | pages/teacher/approvals/list·detail（既有审批页复用，新增 AFFAIRS_LEAVE 类型渲染） | 当前节点辅导员 | ★ | 既有移动审批包装 `POST /api/v1/mobile/teacher/approvals/{id}/approve|reject`（不新增端点） | miniapp/src/pages/teacher/approval、backend/app/services/mobile_teacher_service.py |

| T-03 | 风险处理（处置/转谈话/升级/关闭） | pages/teacher/affairs/risk/list·detail | 被分派责任人（心理明细强权限） | ★ | 既有 risk-students 页模式；区块级 MobileGlobalState | miniapp/src/pages/teacher/risk-students、同上 T-03 |

| T-04 | 谈话快速记录 | pages/teacher/affairs/talk/list·create | 辅/班/心 | ★ | 失败本地暂存纪要 | 同上 T-04 |

| T-05 | 困难核实（辅导员初审可移动；院/校审回 PC） | pages/teacher/affairs/aid/list·detail | 辅导员（COUNSELOR_REVIEW 节点） | ★部分 | MobileSensitiveText（家庭经济脱敏，无看完整入口） | 同上 T-05 |

| T-06 | 处分跟进（只读+催办；登记/审批回 PC） | pages/teacher/affairs/discipline/list·detail | 辅/院（范围内） | ★只读+催办 | 24h 催办限频（后端 409） | 同上 T-06 |

| T-07 | 宿舍异常（宿管上报/辅导员认领处置） | pages/teacher/affairs/dorm/exceptions·report·handle | 宿管（DORM_BUILDING）/辅导员 | ★ | t_cs_dorm_exception 扩展 | backend/app/models/campus_service.py、同上 T-07 |

| T-08 | 学生360简版（学工区块+时间线扩展） | pages/teacher/student/detail（既有页扩展） | 范围内教师（心理区块默认隐藏） | ★ | 既有 `GET /api/v1/mobile/teacher/student/{id}` 聚合扩展，不新建端点 | miniapp/src/pages/teacher/student-detail、backend/app/services/mobile_teacher_service.py |



### 6.2 移动端可办 vs 必须回 PC 总表（与移动端入口设计 §3.9 逐行对齐）



| 业务 | 移动端能做 | 必须回 PC 的环节（PC 页码） |

|---|---|---|

| 请假审批 | 普通假辅导员终审全流程；长假辅导员节点「同意并流转」；销假确认；续假审批 | 长假的学院/学工处节点（05-4/05-6） |

| 销假确认 | 辅导员核对返校证明并确认 | 批量逾期处理与 OVERDUE 批量转风险（05-1） |

| 风险处理 | 查看/填处置/转谈话/升级/关闭 | 风险规则配置（09-5，接平台规则中心）；批量分派 |

| 谈心谈话 | 快速记录、计划执行打勾 | 计划批量制定、工作量统计（10-1/10-5） |

| 困难核实 | 辅导员初审（通过/退回） | 班评录入、学院复审、学校终审与等级评定（06-5）；批次配置（06-2）；公示（06-6） |

| 奖助评审 | —（教师侧 V1 不做移动评审） | 全部评审节点（07-5）、批次配置（07-2）、公示（07-6）、名单确认（07-7） |

| 处分 | 只读跟进 + 催办（24h 限频） | 登记（08-2）、各级审批与严重处分终审（08-4）、解除审批（08-6） |

| 宿舍 | 宿管上报、辅导员认领处置、调宿移动审批（辅→宿管节点） | 房源管理（11-1）、床位批量分配（11-2）、检查批量录入（11-6） |

| 学生360 | 简版聚合查看（脱敏、心理默认隐藏） | 完整画像与隐私字段完整查看（03-2，填原因+审计） |

| 归档 | 收补缺待办提醒 | 批次创建/补缺上传/完整性审核/确认归档（15-1~15-4） |

| 规则/批次/公示类 | 只读知悉 | 全部配置动作（平台规则中心/各批次配置页） |

| 导入导出 | 不提供 | 全部回 PC（模板/dry-run/水印/t_export_task 留痕） |

| 统计分析 | 工作台计数卡 | 统计总览与下钻导出（16-1） |



---



## 7. E6 平台运营端入口（★）



> 复用现有平台管理端（/admin/platform + PLATFORM_ADMIN_TOKEN + require_platform_super_admin），不新建管理端（需求 §12、事实速查 §11）。证据：backend/app/api/v1/platform.py、backend/app/core/security.py、frontend/src/modules/platform/platform.routes.js。



### 7.1 入口清单



| 入口 | 页面/路由 | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|

| 模块授权项 `student-affairs` 开关 | /admin/platform/tenants/:tenantId（租户详情·模块授权区）+ /admin/platform/features | 平台超管 | ★ | 既有租户管控页 + authz /modules 数据源（新增一项） | backend/app/api/v1/authz.py（1.12）、frontend/src/modules/platform/platform.routes.js |

| 学工规则组（长假天数阈值/驳回原因长度/材料必传/处分考察期/风险分派规则） | /admin/platform/rules（规则中心 safe_rule，租户级覆盖） | 平台超管 | ★ | 既有 `GET/PUT /api/v1/platform/tenants/{id}/rules`（默认+覆盖合并、即刻生效校验） | backend/app/api/v1/platform.py（244~265 行） |

| 套餐包含关系 | /admin/platform/packages（套餐含 student-affairs 与否） | 平台超管 | ★ | 既有套餐/变更套餐流 | backend/app/api/v1/platform.py（change-package） |

| 演示/沙箱治理 | demo-school 只读锁、sandbox-school 0 点重置对 13A 同样生效 | 平台侧机制 | ★ | 既有中间件与重置脚本 | _13-现有系统集成事实速查.md §2、scripts/（reset_sandbox_school） |



### 7.2 学工规则组明细（接现有规则中心，租户级覆盖、即刻生效）



| 规则键（建议） | 含义 | 默认值（建议） | 校验 | 影响端与页面 |

|---|---|---|---|---|

| affairs.leave.longLeaveDays | 长假阈值（超过升级学院审批） | 3 天 | 1~30 整数 | E4 S-01 提交提示、E5 T-02 分流、E1 05-4 审批链 |

| affairs.leave.majorLeaveDays | 重大请假阈值（升级学工处） | 7 天 | ≥longLeaveDays | 同上 |

| affairs.leave.rejectReasonMin | 驳回原因最小长度 | 5 字 | 1~50 | E1/E5 全部审批页 422 校验 |

| affairs.leave.cancelProofRequired | 销假是否必传返校证明 | true | 布尔 | E4 S-02、E1 05-5 |

| affairs.aid.materialTypes | 困难认定必传材料类型 | 按批次配置 | 白名单 | E4 S-03、E1 06-2 |

| affairs.discipline.observePeriodMonths | 处分考察期时长 | 6 个月 | 1~24 | E4 S-06 解除按钮解锁、E1 08-5 |

| affairs.risk.autoAssignRules | 风险来源→责任人分派规则 | 学业→辅导员；心理→心理老师；宿舍→宿管+辅导员 | 枚举映射 | E1 09-1 分派、E5 T-03 待办 |

| affairs.dorm.remindLimitHours | 催办限频 | 24 小时 | 1~72 | E5 T-06 催办 409 |



规则读取方式：后端业务校验即刻按 `svc.effective_rules(tenant_id)`（默认+覆盖合并）执行；学工侧配置页（05-8/09-5）只做业务视角读取与提交，不新建规则存储（证据：backend/app/api/v1/platform.py 244~265 行、_13-现有系统集成事实速查.md §11）。



### 7.3 关闭 `student-affairs` 后的降级表现（六端统一口径）



| 端 | 降级表现 |

|---|---|

| E1 PC 管理端 | 「学工中心」菜单整组隐藏（adminMenu 按 moduleCode 过滤 + authz 1.10 readonly/隐藏标）；直输 URL → 后端 `/api/v1/student-affairs/*` 403（bizCode NO_PERMISSION），前端渲染 noPermission 态 |

| E2 学生 PC 门户 | 「学工服务」分组渲染 ModuleDisabledView / NotEnabledView（student-portal 既有降级组件），历史数据可查、写按钮隐藏 |

| E3 教师 PC 工作台 | 学工待办停发（新待办不生成）；在途 workflow 任务冻结只读并提示「模块已停用」；工作台学工卡片不渲染 |

| E4 学生小程序 | 「学工服务」宫格分组不渲染（无空壳页）；在途单据经历史入口只读；写 API 403 时统一文案提示 |

| E5 教师移动端 | 学工角标与业务页入口不渲染；深链进入 → 403 提示并返回 |

| E6 平台端 | 授权项状态可随时恢复；EXPIRED_READONLY（到期）与 SUSPENDED（停用）区分：到期=只读可查，停用=入口隐藏（沿用 authz 1.12 状态语义） |



**数据保全**：关闭不删数据；处分等事实数据仍被毕业预审/奖助校验实时读取（历史效力不消失，见跨端一致性矩阵 §3.6）。



---



## 8. 六端登录与身份注入一览



> 依据 _13-现有系统集成事实速查.md §2/§9：真实登录 `POST /api/v1/auth/login`（pbkdf2，失败 5 次锁 15 分钟），token claims 含 userId/userType/tid/tenantId/activeContextId/currentRoleCode，学生附 studentNo。



| 端 | 登录方式 | 身份注入 | 演示账号 |

|---|---|---|---|

| E1 PC 管理端 | /login 页账号密码（token 存 sessionStorage，无 token 跳 /login） | require_staff；currentRoleCode + activeContext 决定菜单与范围 | demo-school admin/123456（只读）、sandbox admin2 |

| E2 学生 PC 门户 | 门户独立 /login（student-portal 工程），同一 auth 端点 | 学生 token（userType=STUDENT），studentNo 注入所有 my 端点 | student/123456（随门户落地验证） |

| E3 教师 PC 工作台 | 同 E1（教师账号进入 / 默认工作台） | activeContext 切换身份（authz 1.8），权限不合并 | teacher/123456 |

| E4 学生小程序 | 小程序登录页（realFirst 真实登录，401 单飞刷新） | student_id 一律从 token 取，请求体不受理学生身份参数 | student·123456 / student2（沙箱） |

| E5 教师移动端 | 同一小程序工程，角色分流（role-switch 页） | resolve_teacher_scope(user) 决定列表与写校验范围 | teacher·123456 / teacher2 |

| E6 平台运营端 | E1 登录 + PLATFORM_ADMIN_TOKEN（require_platform_super_admin） | platformOnly 菜单，学校业务模块对平台角色隐藏 | 平台超管专用 |



## 9. 核心入口跳转链路（六端视角，3 条）



### 9.1 学生请假：一条单据穿六端



```

E4 学生小程序 服务大厅「请假」宫格 → pages/student/affairs/leave/create → 提交

  [POST /api/v1/mobile/affairs/leave → t_cs_leave(SUBMITTED) + t_workflow_task + t_unified_todo]

E5 教师移动端 T-01 工作台角标 +1 → T-02 审批（普通假移动终审；长假同意并流转）

E3/E1 教师PC 首页「请假待审」卡同步 → 长假学院节点 PC 05-4 审批 → 通过[APPROVED]

E4 学生收 WORKFLOW_RESULT → 到期 DEADLINE_REMINDER → S-02 销假 → E1 05-5 辅导员确认[CLOSED]

  → t_student_stage_event（360 时间线，E1 03-2 / E5 T-08 同一聚合）

E6 平台侧：长假阈值改动即刻影响分流；关闭模块后本链路新单停发、在途只读

E2 学生门户（落地后）：/portal/student-affairs/leave 同单同状态只读+可发起（同一 API）

```



### 9.2 辅导员一天的动线（跨端无缝接力）



```

早：E5 T-01 移动工作台（角标：请假 3 / 风险 1 / 困难核实 2）

  → T-02 审完 2 单普通假（待办 -2，PC 计数同步）

午：E3 PC 登录 → /admin/student-affairs/workbench

  → 区块B 今日待办（与移动端同一 t_unified_todo，已处理项不再出现）

  → 06-5 完成困难初审（材料并排比对，移动端只做过初审的不重复出现）

  → 09-3 处置风险 → 转谈话 10-3（riskId 回写）

晚：E5 T-04 移动补录一条现场谈话 → E1 10-2 列表即时可见 → 10-5 工作量统计 +1

全程：学生 360（E1 03-2 / E5 T-08）实时反映当天全部动作，无需任何手工同步

```



### 9.3 学工处批次动线（配置在 PC，触达在移动）



```

E1 学工处 06-1 新建困难认定批次 → 06-2 配置（时间窗/等级/材料）→ 发布

  [PUBLISHED_NOTICE 写 t_unified_message，按适用学生 receiver_id 精确投递]

E4 学生宫格「困难认定」亮起+「进行中」标签 → S-03 分步表单提交（强敏感脱敏回显）

E5/E3 班评→辅初审（移动可办）→ 院复审/校终审（回 PC 06-5）→ 06-6 公示

E1 06-7 困难库更新 → 07 助学金批次引用 → E4 S-04 奖助宫格亮起（校验读困难库）

E6 平台：demo-school 内本链路全程只读演示；sandbox 每晚重置可反复演练

```



## 10. 六端入口验收要点（每端 ≥2 条，含越权与重复项）



| 端 | 验收用例（通过标准） |

|---|---|

| E1 PC 管理端 | ① 学工处账号登录 → 菜单出现「学工中心」13 叶子，辅导员账号仅见范围内叶子与本班数据；② 学生令牌直输 /admin/student-affairs → 后端 403（require_staff）+ 审计；③ demo-school 账号任意写操作 → 403 且提示引导沙箱 |

| E2 学生 PC 门户 | ① V1 期间门户不提供学工业务入口（无悬空跳转）；② 门户落地后：模块未开通渲染 NotEnabledView，学生 A 无法访问学生 B 数据（同 token 注入原则） |

| E3 教师 PC 工作台 | ① 辅导员切换身份后菜单/待办/范围整刷（menusChanged）；② 同一审批任务 PC 与移动并发处理 → 后处理方收 409 APPROVAL_VERSION_CONFLICT |

| E4 学生小程序 | ① 学生提交请假 → 仅生成一条单据（重复提交 409），辅导员待办出现；② 学生 A 访问学生 B 请假详情 → 403/404 + 审计；③ 模块关闭 → 宫格不渲染、深链 403 文案统一 |

| E5 教师移动端 | ① 教师处理待办成功 → 移动列表消失且 PC 首页计数同步 -1；② 范围外学生详情 → 403002「不在管理范围」+ 审计；③ 长假单在移动端学院节点仅只读提示回 PC |

| E6 平台运营端 | ① 关闭 student-affairs → 六端按 §7.2 口径降级、恢复后入口回归；② 修改学工规则（长假阈值）→ 学校端审批分流即刻按新规则执行（规则中心即刻生效语义） |



## 11. 服务大厅宫格状态规则（E4 补充）



| 宫格 | 显示条件 | 置灰条件 | 角标来源 | 隐藏条件 |

|---|---|---|---|---|

| 请假 | 常驻 | — | 在途单状态（如「审批中」） | 模块关闭 |

| 我的宿舍 | 常驻 | 未分配宿舍时点入渲染 empty 态（不置灰） | 调宿在途 | 模块关闭 |

| 困难认定 | 常驻 | 批次未开放置灰+「未开放」 | 「进行中/审核中」标签 | 模块关闭 |

| 奖助学金 | 常驻 | 无开放批次置灰 | 我的申请状态 | 模块关闭 |

| 勤工助学 | 常驻 | 无开放岗位置灰 | 开放岗位数 | 模块关闭 |

| 我的处分 | 仅有生效记录的学生显示（避免负面标签泛化） | — | 解除申请在途 | 无记录/模块关闭 |

| 谈心谈话 | 常驻次级位置 | — | 新记录红点 | 模块关闭 |

| 家校联系人 | 常驻次级位置（V1 只读） | — | P2 变更待确认 | 模块关闭 |

| 我的活动 / 德育积分 | P2 上线后显示 | — | 报名/积分变动 | V1 一律不渲染（feature flag） |



## 12. 汇总



| 项 | 数量/结论 |

|---|---|

| E1 PC 管理端 | 菜单 1 组 13 叶子；页面 90（V1 69）；接入 adminMenu + moduleRoutes 展平模式 |

| E2 学生 PC 门户 | 7 入口，全部 ◇ 随 09B 落地；V1 学生入口以小程序为准（如实标注：门户壳与骨架工程存在、业务路由未全量实现） |

| E3 教师 PC 工作台 | 11 类身份化入口（/admin 内多角色工作台形态，不新建教师端） |

| E4 学生小程序 | 11 入口（V1 ★8），服务大厅宫格挂载，不新增底部 tab |

| E5 教师移动端 | 8 入口（全 V1，T-05 部分/T-06 只读+催办），13 类环节回 PC |

| E6 平台运营端 | 授权项 `student-affairs` + 学工规则组；关闭后六端降级口径统一 |

