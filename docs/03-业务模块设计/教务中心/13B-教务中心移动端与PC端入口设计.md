# 13B 教务中心移动端与PC端入口设计（六端汇总）



> 依据：[需求输入](../跨模块融合/_13-需求输入-V1.1.md)、[集成事实速查](../跨模块融合/_13-现有系统集成事实速查.md)；页面编号与路由基准：[13B-教务中心页面树与路由设计.md](./13B-教务中心页面树与路由设计.md)；移动端逐页规格：[13B-教务中心移动端入口设计.md](./13B-教务中心移动端入口设计.md)；跨端一致性：[13A-13B-跨端一致性与数据联动矩阵.md](../跨模块融合/13A-13B-跨端一致性与数据联动矩阵.md)。跨夹路径总表见 [文档关联索引.md](./文档关联索引.md)。

> 命名口径（裁定）：13B = `academic-affairs`（PC `/admin/academic-affairs/*`、权限点 `academicAffairs.*`、模块授权项 `academic-affairs`）。**既有 13B 文档中的 `/admin/academic-affairs/*`、`academicAffairs.*` 字样按本裁定统一替换**；页面编号、页面树、V1 划分不变。

> 与既有模块区隔：`/admin/academic/*`（学业过程模块，frontend/src/modules/academic/）路由与表（t_acad_*）保持不动；教务中心新页一律 `/admin/academic-affairs/*`、新表 `t_aa_*`；成绩/预警/补考重修**读写既有 t_acad_* 表**不建平行表。

> 图例：★=V1 必做；☆=P2/P3；◇=随学生 PC 门户（09B）落地时接入，V1 不开。本文只做设计，不写代码、不改路由。



---



## 1. 六端总览



| 端 | 13B 入口形态 | V1 | 说明 |

|---|---|---|---|

| E1 学校PC管理端 | 一级菜单「教务中心」+ 23 组页面树 | ★ | 与既有「学业过程」菜单并存互链 |

| E2 学生PC门户 | 门户「教务服务」分组（09B.8 学业过程入口位） | ◇ | 随 09B 落地；V1 学生入口以小程序为准 |

| E3 教师PC工作台 | 教务首页教师视图 + 任务确认/课表/预警处置 | ★ | /admin 内多角色工作台（09A 形态） |

| E4 学生小程序 | 首页「教务服务」宫格 9 入口 | ★（7 个） | 引用《13B-教务中心移动端入口设计.md》第二章 |

| E5 教师移动端 | 工作台扩展 + 6 入口 | ★（3 个） | 引用同文档第三章；成绩录入等回 PC |

| E6 平台运营端 | 模块授权项 `academic-affairs` 开关 + 教务规则组 | ★ | 复用现有平台管理端，不新建 |



---



## 2. E1 学校 PC 管理端入口



### 2.1 菜单挂载点与 adminMenu 接入方式



现状（证据：frontend/src/config/adminMenu.js、frontend/src/router/index.js）：

- 「学生中心」分组内已有叶子 `{ key:'academic', label:'学业过程', path:'/admin/academic', moduleCode:'ACADEMIC' }`——保留不动；

- 菜单可见性经 `getVisibleAdminMenu(ctx)`（角色白名单 ROLE_MODULE_ALLOW + permissionKey）过滤。



13B 接入设计：



1. **新增一级分组** `academic-affairs`（label「教务中心」），与「学生中心」「教学实践」并列；既有「学业过程」叶子保留在原分组（历史数据入口），后续版本再评估是否收编为教务中心子菜单（页面树 §1.1 决策）。叶子节点：



| key | label | path | moduleCode | permissionKey |

|---|---|---|---|---|

| aa-home | 教务首页 | /admin/academic-affairs | ACADEMIC_AFFAIRS | academicAffairs.dashboard.view |

| aa-terms | 学年学期与校历 | /admin/academic-affairs/terms | ACADEMIC_AFFAIRS | academicAffairs.term.view |

| aa-roll | 学籍管理 | /admin/academic-affairs/roll/students | ACADEMIC_AFFAIRS | academicAffairs.roll.view |

| aa-roll-changes | 学籍异动 | /admin/academic-affairs/roll/changes | ACADEMIC_AFFAIRS | academicAffairs.rollChange.view |

| aa-orgs | 专业与班级（只读复用组织表） | /admin/academic-affairs/majors | ACADEMIC_AFFAIRS | academicAffairs.org.view |

| aa-programs | 培养方案 | /admin/academic-affairs/programs | ACADEMIC_AFFAIRS | academicAffairs.program.view |

| aa-courses | 课程库 | /admin/academic-affairs/courses | ACADEMIC_AFFAIRS | academicAffairs.course.view |

| aa-tasks | 教学任务 | /admin/academic-affairs/teaching-tasks/batches | ACADEMIC_AFFAIRS | academicAffairs.teachingTask.view |

| aa-schedule | 排课与课表 | /admin/academic-affairs/schedule/overview | ACADEMIC_AFFAIRS | academicAffairs.schedule.view |

| aa-grades | 成绩管理 | /admin/academic-affairs/grades/stats | ACADEMIC_AFFAIRS | academicAffairs.grade.view |

| aa-warnings | 学业预警 | /admin/academic-affairs/warnings | ACADEMIC_AFFAIRS | academicAffairs.warning.view |

| aa-graduation | 毕业资格审核 | /admin/academic-affairs/graduation/batches | ACADEMIC_AFFAIRS | academicAffairs.graduation.view |

| aa-stats | 教务统计 | /admin/academic-affairs/stats | ACADEMIC_AFFAIRS | academicAffairs.stats.view |



（☆P2 组：调停课/选课/考务/补考重修/教材/教室/评价/等级考试/教学计划/归档——菜单由权限点隐藏，不做占位页。）



2. **ROLE_MODULE_ALLOW 扩展**：`SCHOOL_ADMIN`、`ACADEMIC_STAFF` 白名单加入 `ACADEMIC_AFFAIRS`；`COUNSELOR` 不整组加入，仅经异动列表（本班只读）与预警联动页的 permissionKey 单点放行；`PLATFORM` 不变。

3. **路由注册形态**：新增 `frontend/src/modules/academicAffairs/`（api/routes/views），routes 并入 router/index.js moduleRoutes 展平数组；避开既有 academic.routes.js 前缀，静态段先于动态段注册。

4. **模块授权联动**：authz /modules 新增 `academic-affairs` 项；既有「学业过程」保持独立授权项，两者可分别开关（关系声明见 §7.2）。



### 2.2 PC 管理端入口清单（按功能组汇总，页面级明细见页面树文档）



| 页面/功能组 | 路由（前缀 /admin/academic-affairs） | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|

| 教务首页（教务处/学院教务/教师三视图） | `/` | 教务处/学院教务/教师 | ★ | Dashboard preset、stats 聚合 | docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md §2-01、backend/app/services/stats_service.py |

| 学年学期与校历 7 页（列表/新增/编辑/校历/节次/发布/归档☆） | `/terms/*` | 教务处（学院看） | ★（6 页） | 状态机 DRAFT/PUBLISHED/FROZEN/ARCHIVED；发布同步课表/工作台/学生端 | 同上 §3.1 |

| 学籍管理 10 页（档案/注册批次/核对/异动列表/详情/代录/审批/统计；学年注册☆） | `/roll/*` | 教务处/学院教务/辅导员（本班只读）/节点人 | ★（8 页） | t_student_profile 单一写入口 + t_aa_status_change 异动流水 + Workflow | backend/app/models/student.py、backend/app/models/approval.py、docs/03-业务模块设计/教务中心/13B-教务中心与现有系统融合设计.md §1 |

| 专业/班级一览（只读复用） | `/majors`、`/classes` | 教务处/学院教务 | ★ | t_college/t_major/t_class 直读 | backend/app/models/org.py |

| 培养方案 8 页（列表/新增/详情/编制/课程配置/审核/发布；版本对比☆） | `/programs/*` | 教务处/学院教务/专业负责人 | ★（7 页） | 版本化方案表；审批走 Workflow | docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md §3.3 |

| 课程库 6 页（列表/新增/详情/编辑/审核/导入） | `/courses/*` | 课程负责人/学院教务/教务处 | ★ | 导入管线 dry-run→confirm | backend/app/services/domain_import_service.py |

| 教学任务 7 页（批次/生成/核对/教师确认/审核；统计☆） | `/teaching-tasks/*` | 教务处/学院教务/专业负责人/教师 | ★（6 页） | Workflow + t_unified_todo | docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md §3.4 |

| 排课与课表（V1=导入+查看+冲突检测+发布：课表导入/总课表/班级课表/教师课表/冲突报告/发布；排课工作台等☆） | `/schedule/*` | 教务处/学院教务（课表查看含教师） | ★（6 页） | 导入管线、校历数据 | 同上 §2-08 |

| 调停课 4 页 | `/course-adjustments/*` | 教师发起/学院/教务审 | ☆P2 | Workflow | 同上 §2-09 |

| 选课/考务与缓考 12 页 | `/enrollment/*`、`/exams/*` | 教务处/学院教务/节点人 | ☆P2 | Workflow、导出管线 | 同上 §2-10/11 |

| 成绩管理（V1：学生成绩单/成绩统计；录入/审核/发布/更正☆P2） | `/grades/*` | 教务处/学院教务/教师（录入 P2） | ★（2 页） | **读写既有 t_acad_grade 扩展字段，不建平行表** | backend/app/models/academic.py、docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md §2-12 |

| 补考/重修/免修 6 页 | `/makeup/*`、`/retake/*`、`/exemptions/*` | 教务处/学院教务 | ☆P2 | 扩展既有 t_acad_makeup/t_acad_retake | backend/app/models/academic.py |

| 学业预警 4 页（规则配置/列表/处置/统计） | `/warnings/*` | 教务处/学院教务/辅导员（处置） | ★ | **扩展既有 t_acad_warning 与 close/escalate/assign/remind API，不新建预警表**；规则接平台规则中心 | backend/app/models/academic.py、backend/app/api/v1/academic.py |

| 毕业资格审核 8 页（批次/新增/预审结果/学生预审详情/异常处理/学院初审/教务终审/名单导出） | `/graduation/*` | 教务处/学院教务/节点人 | ★ | 预审引擎实时读六域（见联动矩阵 L-10）；导出水印+t_export_task | backend/app/services/domain_export_service.py |

| 教材/教室/评价/等级考试/教学计划/归档 | `/textbooks/*` 等 | 教务处/学院教务 | ☆P2/P3 | 复用导出/水印/审计管线 | docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md §2-16~21 |

| 教务统计总览 | `/stats` | 教务处/学院教务 | ★ | stats_service 扩展（注册率/任务完成率/冲突数/挂科率/预警数/毕业通过率） | backend/app/services/stats_service.py |



**守卫与降级**：同 13A（强制登录→权限点→数据范围后端校验+审计；demo-school 只读锁引导沙箱）。PC 仅教职工：`require_staff`，学生令牌 403（证据：_13-现有系统集成事实速查.md §2）。



### 2.3 页面级入口与菜单归属明细（V1 ★58 页逐页；☆50 页按组归并）



> 页面编号（#1~#108）、路由、角色与《13B-教务中心页面树与路由设计.md》§3 逐行对齐（路由前缀按裁定替换为 /admin/academic-affairs）；本表新增「归属菜单叶子」列。



**教务首页与校历（叶子 aa-home / aa-terms）**



| # | 页面 | 路由（省略前缀） | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 1 | 教务首页 | `/` | 教务处/学院教务/教师（角色视图） | ★ | aa-home |

| 2 | 学期列表 | `/terms` | 教务处（管）/学院教务（看） | ★ | aa-terms |

| 3 | 学年学期新增 | `/terms/create` | 教务处 | ★ | aa-terms（列表按钮） |

| 4 | 学年学期编辑 | `/terms/:termId/edit` | 教务处（DRAFT 态） | ★ | aa-terms |

| 5 | 校历编辑 | `/terms/:termId/calendar` | 教务处 | ★ | aa-terms |

| 6 | 节次配置 | `/terms/:termId/time-slots` | 教务处 | ★ | aa-terms |

| 7 | 校历发布 | `/terms/:termId/publish` | 教务处 | ★ | aa-terms（校历编辑→去发布） |

| 8 | 校历归档查看 | `/terms/:termId/archive` | 教务处/学院教务（只读） | ☆P2 | 隐藏 |



**学籍与组织（叶子 aa-roll / aa-roll-changes / aa-orgs）**



| # | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 9 | 学籍档案列表 | `/roll/students` | 教务处（全校）/学院教务（本院） | ★ | aa-roll |

| 10 | 学籍档案详情 | `/roll/students/:studentId` | 同上（scope 校验） | ★ | aa-roll（行点击） |

| 11 | 入学注册批次 | `/roll/registration` | 教务处/学院教务 | ★ | aa-roll |

| 12 | 注册名单核对 | `/roll/registration/:batchId/check` | 学院教务（核）→教务处（审） | ★ | aa-roll/统一待办 |

| 13 | 学年注册 | `/roll/annual-registration` | 教务处/学院教务 | ☆P2 | 隐藏 |

| 14 | 异动申请列表 | `/roll/changes` | 教务处/学院教务/辅导员（本班只读） | ★ | aa-roll-changes |

| 15 | 异动申请详情 | `/roll/changes/:changeId` | 同上（scope 校验） | ★ | aa-roll-changes（行点击） |

| 16 | 异动代录新增 | `/roll/changes/create` | 教务处/学院教务 | ★ | aa-roll-changes（代录按钮） |

| 17 | 异动审批 | `/roll/changes/:changeId/approve` | 节点人（辅导员/原学院/目标学院/教务处） | ★ | 统一待办直达 |

| 18 | 异动统计 | `/roll/changes/stats` | 教务处/学院教务 | ★ | aa-roll-changes/aa-stats 下钻 |

| 19 | 专业一览 | `/majors` | 教务处/学院教务（只读复用组织表） | ★ | aa-orgs |

| 20 | 班级一览 | `/classes` | 同上 | ★ | aa-orgs |



**培养方案与课程库（叶子 aa-programs / aa-courses）**



| # | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 21 | 方案列表 | `/programs` | 教务处/学院教务/专业负责人 | ★ | aa-programs |

| 22 | 方案新增 | `/programs/create` | 教务处/专业负责人 | ★ | aa-programs |

| 23 | 方案详情 | `/programs/:programId` | 全教务角色（只读） | ★ | aa-programs（行点击） |

| 24 | 方案编制 | `/programs/:programId/edit` | 专业负责人（DRAFT/RETURNED） | ★ | aa-programs |

| 25 | 方案课程配置 | `/programs/:programId/courses` | 专业负责人（DRAFT/RETURNED） | ★ | aa-programs（编制→课程配置） |

| 26 | 方案审核 | `/programs/:programId/approve` | 学院教务（初审）→教务处（终审） | ★ | 统一待办直达 |

| 27 | 版本对比 | `/programs/:programId/versions/compare` | 教务角色 | ☆P2 | 隐藏 |

| 28 | 方案发布 | `/programs/:programId/publish` | 教务处 | ★ | aa-programs（审核通过后） |

| 29 | 课程列表 | `/courses` | 教务角色/教师（只读） | ★ | aa-courses |

| 30 | 课程新增 | `/courses/create` | 课程负责人/学院教务 | ★ | aa-courses |

| 31 | 课程详情 | `/courses/:courseId` | 全教务角色（只读） | ★ | aa-courses（行点击） |

| 32 | 课程编辑 | `/courses/:courseId/edit` | 课程负责人（DRAFT/RETURNED） | ★ | aa-courses |

| 33 | 课程审核 | `/courses/:courseId/approve` | 学院教务→教务处（终审启用） | ★ | 统一待办直达 |

| 34 | 课程库导入 | `/courses/import` | 教务处/学院教务 | ★ | aa-courses（导入按钮） |



**教学任务与课表（叶子 aa-tasks / aa-schedule）**



| # | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 35 | 任务批次列表 | `/teaching-tasks/batches` | 教务处/学院教务/专业负责人 | ★ | aa-tasks |

| 36 | 任务批次新增 | `/teaching-tasks/batches/create` | 教务处 | ★ | aa-tasks |

| 37 | 任务生成 | `/teaching-tasks/batches/:batchId/generate` | 教务处 | ★ | aa-tasks |

| 38 | 任务核对 | `/teaching-tasks/batches/:batchId/check` | 学院教务/专业负责人 | ★ | aa-tasks/统一待办 |

| 39 | 教师确认 | `/teaching-tasks/batches/:batchId/teacher-confirm` | 任课教师（本人任务） | ★ | 统一待办/教务首页教师视图 |

| 40 | 任务审核 | `/teaching-tasks/batches/:batchId/approve` | 教务处 | ★ | 统一待办直达 |

| 41 | 任务统计 | `/teaching-tasks/stats` | 教务处/学院教务 | ☆P2 | 隐藏 |

| 44 | 课表导入 | `/schedule/import` | 教务处/学院教务 | ★ | aa-schedule（V1 数据来源） |

| 45 | 总课表 | `/schedule/overview` | 教务处/学院教务/督导 | ★ | aa-schedule |

| 46 | 班级课表 | `/schedule/class/:classId` | 教务处/学院教务/辅导员（本班） | ★ | aa-schedule（下钻） |

| 47 | 教师课表 | `/schedule/teacher/:teacherId` | 教务处/学院教务；教师看本人 | ★ | aa-schedule（下钻/教师视图） |

| 49 | 冲突报告 | `/schedule/batches/:batchId/conflicts` | 教务处/学院教务 | ★ | aa-schedule/导入结果页 |

| 50 | 课表发布 | `/schedule/batches/:batchId/publish` | 教务处 | ★ | aa-schedule（冲突清零后） |

| 42/43/48/51 | 排课批次/手工排课工作台/教室课表/课表导出 | `/schedule/batches` 等 | 教务处/学院教务 | ☆P2 | 隐藏 |



**成绩与学业预警（叶子 aa-grades / aa-warnings；成绩数据落既有 t_acad_grade）**



| # | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 72 | 学生成绩单 | `/grades/transcript/:studentId` | 教务处/学院教务/辅导员（scope 校验） | ★ | aa-grades/学籍详情/预警处置页 |

| 75 | 成绩统计 | `/grades/stats` | 教务处/学院教务 | ★（基础口径） | aa-grades |

| 68~71/73/74 | 成绩任务/录入/审核/发布/更正申请/更正审核 | `/grades/tasks` 等 | 教师/学院教务/教务处 | ☆P2 | 隐藏 |

| 82 | 预警规则配置 | `/warnings/rules` | 教务处（接平台规则中心） | ★ | aa-warnings |

| 83 | 学业预警列表 | `/warnings` | 教务处/学院教务/辅导员（本班） | ★ | aa-warnings/首页卡片 |

| 84 | 预警处置 | `/warnings/:warningId/handle` | 辅导员/学院教务（复用既有处置 API） | ★ | 统一待办/列表行 |

| 85 | 预警统计 | `/warnings/stats` | 教务处/学院教务 | ★ | aa-warnings/aa-stats 下钻 |



**毕业资格审核（叶子 aa-graduation）**



| # | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 86 | 审核批次列表 | `/graduation/batches` | 教务处/学院教务 | ★ | aa-graduation |

| 87 | 审核批次新增 | `/graduation/batches/create` | 教务处 | ★ | aa-graduation |

| 88 | 预审结果列表 | `/graduation/batches/:batchId/precheck` | 教务处/学院教务（本院） | ★ | aa-graduation |

| 89 | 学生预审详情 | `/graduation/batches/:batchId/students/:studentId` | 同上 + 辅导员（本班只读） | ★ | 预审结果行点击 |

| 90 | 异常处理 | `/graduation/batches/:batchId/exceptions` | 学院教务/辅导员（补充说明） | ★ | 预审结果 tab/统一待办 |

| 91 | 学院初审 | `/graduation/batches/:batchId/college-review` | 学院教务 | ★ | 统一待办直达 |

| 92 | 教务终审 | `/graduation/batches/:batchId/final-review` | 教务处 | ★ | 统一待办直达 |

| 93 | 名单导出 | `/graduation/batches/:batchId/export` | 教务处（用途必填≥5字，水印留痕） | ★ | 终审完成页 |



**统计与 ☆ 后置组**



| # | 页面 | 路由 | 角色 | V1 | 归属叶子 |

|---|---|---|---|---|---|

| 108 | 教务统计总览 | `/stats` | 教务处/学院教务（scope 过滤） | ★（基础） | aa-stats |

| 52~67 | 调停课 4 页/选课 4 页/考务缓考 8 页 | `/course-adjustments/*`、`/enrollment/*`、`/exams/*` | 教师/学院教务/教务处/节点人 | ☆P2 | 隐藏 |

| 76~81 | 补考/重修/免修 6 页 | `/makeup/*`、`/retake/*`、`/exemptions/*` | 教务处/学院教务/教师 | ☆P2 | 隐藏 |

| 94~107 | 教材 3/教室 3/评价 3/等级考试 2/教学计划 1/归档 2 | `/textbooks/*` 等 | 教务处/学院教务/督导 | ☆P2/P3 | 隐藏 |



**计数核对**：PC 页面 108（V1 ★58 / ☆50），与页面树文档 §3.9 一致（全端合计 123，V1 68）。



---



## 3. E3 教师 PC 工作台入口



> 现状同 13A §3：教师 PC = /admin 内多角色工作台（09A），authz activeContext 驱动菜单与数据范围（backend/app/api/v1/authz.py 1.6~1.11）。教务侧身份：教务处管理员/学院教务员/专业负责人/任课教师/督导（09A 6.3/6.7/6.8/6.10）。



| 入口 | 页面/路由 | 角色（activeContext） | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|

| 教务首页·教务处视图 | /admin/academic-affairs | 教务处管理员 | ★ | Dashboard preset（任务/排课/成绩/异动/预警/毕业指标卡） | docs/08-历史记录与归档/source-design/09A（6.3）、docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md §2-01 |

| 教务首页·学院视图 | 同页 preset | 学院教务员 | ★ | 本学院切片（COLLEGE scope） | 同上 |

| 教务首页·教师视图 | 同页 preset | 任课教师 | ★ | 今日课程/授课班级/成绩录入任务(P2)/监考(P2)/学生名单卡 | 同上（09A 6.10：任课教师 V1 弱化，仅保留必要视图） |

| 教师课表 | /admin/academic-affairs/schedule/teacher/:teacherId | 任课教师（本人）/教务 | ★ | 读已发布课表 | docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md §3.4 |

| 教学任务教师确认 | /teaching-tasks/batches/:batchId/teacher-confirm | 任课教师 | ★ | t_unified_todo 待办直达 | 同上 |

| 方案编制/审核 | /programs/:programId/edit·approve | 专业负责人/学院教务/教务处 | ★ | Workflow 审批组合页 | 同上 §3.3 |

| 学籍异动审批 | /roll/changes/:changeId/approve | 节点人（辅导员/原学院/目标学院/教务处） | ★ | Workflow + version 乐观锁 | backend/app/models/approval.py |

| 学业预警处置 | /warnings/:warningId/handle | 辅导员/学院教务员（分派责任人） | ★ | 复用既有 t_acad_warning 处置 API 家族 | backend/app/api/v1/academic.py |

| 成绩录入/审核 | /grades/tasks/:taskId/input·review | 任课教师/学院教务 | ☆P2（V1 成绩为导入+查看） | 既有 t_acad_grade | backend/app/models/academic.py |

| 调停课发起/审批 | /course-adjustments/* | 教师/学院/教务 | ☆P2 | Workflow | docs/03-业务模块设计/教务中心/13B-教务中心页面树与路由设计.md §2-09 |

| 统一待办入口 | 顶栏待办数 + /admin/approval | 全教职工 | ★ | t_unified_todo 同源 | backend/app/api/v1/todo.py |



**身份切换**：同 13A §3（authz 1.8，切换后菜单/待办/范围整刷，权限不合并）；教务数据范围函数 getAcademicScope 设计为 resolve_teacher_scope 的封装（任课教师=本人课程学生、督导=授权课程学院，t_teacher_student_scope 扩枚举）。证据：backend/app/services/mobile_teacher_service.py、backend/app/models/teacher_scope.py。



---



## 4. E2 学生 PC 门户入口（◇ 随 09B 落地时接入）



> 现状如实标注（同 13A §4）：09B 设计存在；门户壳 frontend/src/layouts/StudentPortalLayout.vue 与独立骨架工程 student-portal/（/portal/:module 模板路由、ModuleDisabledView/NotEnabledView）存在；**业务路由未全量实现，本轮不开学生 PC 门户，V1 学生入口以小程序为准**。09B.8「学业过程PC入口」（我的学业首页/我的成绩/我的学分/学业预警/证书竞赛）即 13B 门户分组的落位。



| 入口 | 门户页面/路由（student-portal 工程） | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|

| 教务服务分组页 | /portal/academic-affairs（经 /portal/:module 模板注册） | 学生本人 | ◇ | ModuleCard、moduleRegistry | student-portal/src/platform/moduleRegistry.js |

| 我的课表（大屏周/学期视图，PC 优势项） | /portal/academic-affairs/schedule | 学生本人 | ◇ | DataPanel | student-portal/src/components/DataPanel.vue |

| 我的成绩与学分进度 | /portal/academic-affairs/grades | 学生本人 | ◇ | ProgressTimeline、StatusTag | student-portal/src/components/ProgressTimeline.vue |

| 我的学籍与异动申请（长表单+材料上传增强） | /portal/academic-affairs/roll | 学生本人 | ◇ | FileDropzone | student-portal/src/components/FileDropzone.vue |

| 我的考试/缓考申请 | /portal/academic-affairs/exams | 学生本人 | ◇（且待 P2 考务） | — | docs/08-历史记录与归档/source-design/09B（09B.8） |

| 学业预警（只读知悉） | /portal/academic-affairs/warnings | 学生本人 | ◇ | StatusTag | — |

| 毕业进度红绿灯 | /portal/academic-affairs/graduation-progress | 学生本人 | ◇ | 与小程序同口径同端点 | docs/03-业务模块设计/教务中心/13B-教务中心移动端入口设计.md §2.9 |

| 我的待办/消息（教务条目汇入） | /portal/home、TodoPanel | 学生本人 | ◇（门户框架项） | TodoPanel（t_unified_todo/message 同源） | student-portal/src/components/TodoPanel.vue |



**接入原则**：与小程序共用 student_id；新建走 `/api/v1/mobile/academic-affairs/*`，复用既有 `/api/v1/mobile/academic/my/*` 端点，不为门户另造端点；模块关闭/到期渲染既有降级组件；成绩等教务同步数据门户只读（09B §2.3「不能修改教务同步来的成绩」）。



---



## 5. E4 学生小程序入口（★ V1 学生唯一入口）



> 逐页 41 项规格引用《13B-教务中心移动端入口设计.md》第二章（2.1~2.9）。页面路径根按命名裁定为 `pages/student/academic-affairs/*`（原文档 `pages/student/academic-affairs/*` 字样替换，复用页除外）。



### 5.1 入口清单



| # | 入口 | 页面路径 | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|---|

| 2.1 | 我的课表（周视图） | pages/student/academic-affairs/schedule | 学生本人 | ★只读 | 校历/发布数据驱动；变更角标（调/停/补） | docs/03-业务模块设计/教务中心/13B-教务中心移动端入口设计.md §2.1 |

| 2.2 | 我的课程 | pages/student/academic-affairs/courses·course-detail | 学生本人 | ★只读 | 修读状态读 t_acad_grade.pass_status | 同上 §2.2、backend/app/models/academic.py |

| 2.3 | 我的考试 + 缓考申请 | pages/student/academic-affairs/exams·exam-deferral-form | 学生本人 | ☆P2（V1 宫格不渲染） | createSubmitLock + 409 在途唯一 | 同上 §2.3 |

| 2.4 | 我的成绩 | **复用既有** pages/student/academic 成绩骨架扩展（不重建页面） | 学生本人 | ★只读 | 既有 `GET /api/v1/mobile/academic/my/grades`（复用既有 academic 学业过程模块） 扩展响应字段，不新增平行端点 | miniapp/src/pages/student/academic/、同上 §2.4/§4.1 |

| 2.5 | 我的补考重修 | pages/student/academic-affairs/makeup-retake | 学生本人 | ☆P2 | 扩展 t_acad_makeup/retake | 同上 §2.5 |

| 2.6 | 我的学籍 | pages/student/academic-affairs/roll | 学生本人 | ★只读 | MobileSensitiveText（身份证/联系方式脱敏） | 同上 §2.6 |

| 2.7 | 异动申请（转专业/休学/复学/退学） | pages/student/academic-affairs/roll-change-form·list | 学生本人 | ★可写（**学生端唯一 V1 写入口**：提交/撤回/重新提交） | createSubmitLock + 服务端在途唯一 409；`POST /api/v1/mobile/academic-affairs/roll-changes` | 同上 §2.7 |

| 2.8 | 我的学业预警 | **复用既有**学业预警页骨架扩展 | 学生本人 | ★只读 | 既有 `GET /api/v1/mobile/academic/my/warnings`（复用既有 academic 学业过程模块）（直读 t_acad_warning） | 同上 §2.8、backend/app/models/academic.py |

| 2.9 | 毕业资格进度（红绿灯） | pages/student/academic-affairs/graduation-progress | 学生本人 | ★只读 | 与 PC 预审详情同口径；未入批次降级为实时学分进度（mode 字段） | 同上 §2.9 |



### 5.2 底部导航与服务大厅挂载



1. **不新增底部 tab**：全部入口收进学生首页「教务服务」宫格分组；「我的课表」置分组首位（高频），毕业年级学生「毕业进度」建议置顶展示、低年级折叠。

2. **V1 仅渲染 7 个 ★ 宫格**：P2 宫格（我的考试/补考重修）由 feature flag 控制不渲染，避免空壳页与悬空跳转（移动端入口设计 §1.2/§2.3 降级说明）。

3. **角标与消息深链**：t_unified_message 驱动——PUBLISHED_NOTICE（课表/成绩/考试发布）→对应页并定位变更周/新学期；STATUS_CHANGED（调停课/异动/预审结论）→详情；RISK_ALERT（预警）→我的学业预警；WORKFLOW_RESULT（异动审批结果）→异动详情（映射表引用移动端入口设计 §4.3）。

4. **无本地假状态**：realFirst 业务错误透出；异动提交断网不自动重发、表单保留；学生标识一律 token 取，越权后端 403/404+审计。

5. **模块授权降级**：`academic-affairs` 关闭 → 「教务服务」宫格分组不渲染；既有学业页（成绩/预警骨架）随「学业过程」模块授权独立判定。



### 5.3 消息类型 → 学生端路由映射（与移动端入口设计 §4.3 对齐）



| 消息类型（t_unified_message） | 触发场景 | 点击跳转 |

|---|---|---|

| PUBLISHED_NOTICE | 课表发布、成绩发布、考试发布（P2）、缓考安排（P2） | 我的课表（定位变更周）/我的成绩（定位新学期）/我的考试 |

| STATUS_CHANGED | 调停课变更、异动生效、预审结论变化 | 我的课表（变更角标）/我的学籍/毕业资格进度 |

| WORKFLOW_RESULT | 异动审批结果、缓考审批结果（P2） | 异动详情（APPROVED 引导查看我的学籍）/缓考详情 |

| RETURNED_NOTICE | 异动申请被退回 | 异动表单（RETURNED 态带原数据可重提） |

| RISK_ALERT | 学业预警生成 | 我的学业预警详情 |

| DEADLINE_REMINDER | 考前提醒（P2）、注册截止提醒 | 我的考试/我的学籍 |

| ARCHIVE_NOTICE | 学生侧不下发 | — |



规则：点击即调「标已读」端点递减角标；目标不存在时 404 提示回列表刷新；V1 未上线业务（考试类）的消息类型 V1 不产生，避免悬空深链。



---



## 6. E5 教师移动端入口（★3 + ☆3）



> 逐页规格引用《13B-教务中心移动端入口设计.md》第三章（3.1~3.6）与 §3.0「移动端可完成 vs 必须回 PC 清单表」。页面路径根 `pages/teacher/academic-affairs/*`。



| # | 入口 | 页面路径 | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|---|

| 3.1 | 今日课程 | pages/teacher/academic-affairs/today-courses | 任课教师 | ★ | 既有教师工作台页扩展「今日课程」卡直达；读已发布课表 | miniapp/src/pages/teacher/workbench、docs/03-业务模块设计/教务中心/13B-教务中心移动端入口设计.md §3.1 |

| 3.2 | 授课班级（学生名单） | pages/teacher/academic-affairs/classes | 任课教师（本人课程学生 scope） | ★ | can_teacher_view_student 四路判定；名单脱敏展示 | backend/app/services/mobile_teacher_service.py、同上 §3.2 |

| 3.3 | 成绩录入进度（只读） | pages/teacher/academic-affairs/grade-progress | 任课教师 | ☆P2（录入回 PC） | — | 同上 §3.3 |

| 3.4 | 调停课申请 | pages/teacher/academic-affairs/course-adjustment | 任课教师（发起）；审批走移动审批包装 | ☆P2 | 既有 `POST /api/v1/mobile/teacher/approvals/{id}/approve|reject`（审批节点复用） | 同上 §3.4、backend/app/services/mobile_teacher_service.py |

| 3.5 | 监考任务 | pages/teacher/academic-affairs/invigilation | 任课教师 | ☆P2（随考务） | — | 同上 §3.5 |

| 3.6 | 学业预警跟进 | 复用既有教师端预警处理入口扩展（工作台/待办直达） | 辅导员/学院教务员 | ★ | **复用既有 t_acad_warning 移动端处理端点**（close/escalate/assign/remind 家族），不新建 | backend/app/api/v1/mobile.py、同上 §3.6 |



### 6.2 移动端可完成 vs 必须回 PC 清单（与移动端入口设计 §3.0/§1.2 对齐）



| 业务 | 移动端能做 | 必须回 PC 的环节（PC 页码） |

|---|---|---|

| 课表 | 今日课程/本人课表查看（只读） | 课表导入（#44）、冲突处理（#49）、发布（#50）、排课工作台（#43 P2） |

| 教学任务 | 任务查看与确认提醒（待办直达） | 批次创建/生成/核对/审核（#36~#40，确认动作本体在 PC #39） |

| 成绩 | 录入进度只读（P2） | 成绩录入/审核/发布/更正全链（#68~#74 P2）；V1 成绩单查看在 PC #72 |

| 学业预警 | 列表/详情/处置（复用既有移动处理端点） | 规则配置（#82，接平台规则中心）、批量分派、统计导出（#85） |

| 学籍异动 | 审批节点通过/驳回（移动审批包装） | 代录新增（#16）、异动统计（#18）、注册批次核对（#12） |

| 调停课（P2） | 发起申请、审批节点 | 课表更新与冲突复核（教务侧） |

| 考务（P2） | 监考任务查看 | 考试批次/考场座位/监考安排/发布（#60~#64） |

| 毕业资格 | —（教师移动端不参与） | 批次/预审/异常处理/初审/终审/名单导出（#86~#93） |

| 培养方案/课程库 | 只读知悉 | 编制/课程配置/审核/发布/导入（#22~#34） |

| 导入导出 | 不提供 | 全部回 PC（dry-run/水印/t_export_task 留痕） |



教师移动端定位 = 查看/确认/审批/处置四类轻操作；凡涉批量、结构化编制、发布、导出的动作一律回 PC。



**审批一致性**：13B 全部移动审批（异动/方案/任务/调停课/缓考）= 新 workflow_code 复用既有移动审批包装端点，任务与 PC 同源（t_workflow_task + version 乐观锁，跨端 409 收敛）。



---



## 7. E6 平台运营端入口（★）



> 复用现有平台管理端（/admin/platform + PLATFORM_ADMIN_TOKEN），不新建。证据：backend/app/api/v1/platform.py、backend/app/core/security.py、frontend/src/modules/platform/platform.routes.js。



### 7.1 入口清单



| 入口 | 页面/路由 | 角色 | V1 | 复用组件 | 证据路径 |

|---|---|---|---|---|---|

| 模块授权项 `academic-affairs` 开关 | /admin/platform/tenants/:tenantId（模块授权区）+ /admin/platform/features | 平台超管 | ★ | authz /modules 数据源新增一项（状态语义沿用：启用/SUSPENDED/EXPIRED_READONLY） | backend/app/api/v1/authz.py（1.12、183~193 行 readonly 打标） |

| 教务规则组（学分上限/预警规则阈值与来源开关/毕业条件项开关/成绩构成比例边界/异动时间窗） | /admin/platform/rules（规则中心，租户级覆盖） | 平台超管 | ★ | 既有 `GET/PUT /api/v1/platform/tenants/{id}/rules`（默认+覆盖合并、即刻生效） | backend/app/api/v1/platform.py（244~265 行） |

| 套餐包含关系 | /admin/platform/packages | 平台超管 | ★ | 既有套餐/变更套餐流 | backend/app/api/v1/platform.py |

| 演示/沙箱治理 | demo-school 只读锁、sandbox-school 0 点重置对 13B 同样生效 | 平台侧机制 | ★ | 既有中间件 | _13-现有系统集成事实速查.md §2 |



### 7.2 教务规则组明细（接现有规则中心，租户级覆盖、即刻生效）



| 规则键（建议） | 含义 | 默认值（建议） | 校验 | 影响端与页面 |

|---|---|---|---|---|

| academic.warning.failCountThreshold | 触发预警的不及格门数 | 2 门/学期 | 1~10 | E1 #82 规则页、成绩发布后扫描、E4 我的学业预警 |

| academic.warning.gpaThreshold | 低绩点预警线 | 2.0 | 0~4 | 同上 |

| academic.warning.sources | 预警来源开关（挂科/低绩点/学分不足/缺考/未注册…） | 成绩类+注册类开（V1） | 枚举多选 | E1 #83 列表来源列、E5 3.6 跟进 |

| academic.rollChange.windowDays | 异动申请时间窗 | 开学后 30 天（转专业） | 1~90 | E4 2.7 提交校验、E1 #16 代录 |

| academic.rollChange.pendingUnique | 同类型在途申请唯一 | true | 布尔 | E4 2.7 重复 409、E1 #14 |

| academic.credit.maxPerTerm | 学期选课学分上限（P2） | 30 | 10~50 | 选课校验（P2） |

| academic.grade.composition | 成绩构成比例边界（平时/期末，P2） | 平时 ≤50% | 0~100 | 成绩录入校验（P2） |

| academic.graduation.conditions | 毕业条件项开关（学分/必修/实习/毕设/处分/费用/就业/归档） | 全开 | 枚举多选 | E1 #88 预审引擎、E4 2.9 红绿灯口径 |

| academic.suspend.remindDays | 休学到期提醒提前天数 | 30 天 | 7~90 | DEADLINE_REMINDER 触达学生+辅导员 |



规则读取方式：后端按 `svc.effective_rules(tenant_id)` 即刻生效；教务侧规则页（#82 等）只做业务视角读取与提交，不新建规则存储（证据：backend/app/api/v1/platform.py 244~265 行、_13-现有系统集成事实速查.md §11）。



### 7.3 关闭 `academic-affairs` 后的降级表现（六端统一口径）



| 端 | 降级表现 |

|---|---|

| E1 PC 管理端 | 「教务中心」菜单整组隐藏；`/api/v1/academic-affairs/terms|programs|...` 等 13B 新路径 403；**既有「学业过程」模块（/admin/academic，t_acad_* 查询骨架）随其独立授权项判定，不受本开关牵连**；已发布课表/成绩转历史只读 |

| E2 学生 PC 门户 | 「教务服务」分组渲染 ModuleDisabledView/NotEnabledView；历史成绩课表可查、写按钮隐藏 |

| E3 教师 PC 工作台 | 教务待办停发；在途 workflow 任务（异动/方案/任务审批）冻结只读并提示「模块已停用」；教师视图教务卡片不渲染 |

| E4 学生小程序 | 「教务服务」宫格分组不渲染；异动在途单历史只读；深链 403 统一提示 |

| E5 教师移动端 | 今日课程/授课班级/预警跟进入口不渲染（预警跟进若归属学业过程授权则单独判定）；写 API 403 |

| E6 平台端 | 可随时恢复；到期（EXPIRED_READONLY）=只读可查，停用（SUSPENDED）=入口隐藏 |



**数据保全与跨模块效力**：关闭不删数据；学籍状态（t_student_profile.student_status）作为主档事实继续被学工/实习/毕设/就业读取；已出毕业结论名单只读可导出（水印+留痕）。详见《13A-13B-跨端一致性与数据联动矩阵.md》§3.3/§3.8。



---



## 8. 六端登录与身份注入一览



> 依据 _13-现有系统集成事实速查.md §2/§9（与 13A 六端一致，此处仅列教务差异项）。



| 端 | 登录方式 | 教务侧身份注入要点 | 演示账号 |

|---|---|---|---|

| E1 PC 管理端 | /login 账号密码，require_staff | 教务处（全校）/学院教务（COLLEGE）/专业负责人（MAJOR）/任课教师（本人课程）四级范围，activeContext 决定首页 preset | demo-school admin（只读）/sandbox admin2 |

| E2 学生 PC 门户 | 门户 /login（随 09B） | 学生 token studentNo 注入全部 my 端点；成绩课表只读 | student/123456（门户落地验证） |

| E3 教师 PC 工作台 | 同 E1 | 任课教师视图 V1 弱化（09A 6.10）：今日课程/任务确认/名单为主 | teacher/123456 |

| E4 学生小程序 | 小程序真实登录 + 401 单飞 | my 端点后端自取 studentNo/tenant，前端不传学生标识 | student·123456 / student2 |

| E5 教师移动端 | 同一小程序工程角色分流 | resolve_teacher_scope；预警处置沿用既有移动处理端点鉴权 | teacher·123456 / teacher2 |

| E6 平台运营端 | E1 + PLATFORM_ADMIN_TOKEN | 教务规则组与授权项管理，学校业务数据不可见 | 平台超管专用 |



## 9. 核心入口跳转链路（六端视角，3 条）



### 9.1 成绩发布：一份成绩穿六端（V1 查看段 + P2 全链）



```

E1 教务处 课表/成绩数据导入（V1）或 P2 录入链（教师录入→学院审→教务发布）

  [写 t_acad_grade，置 PUBLISHED，触发预警扫描]

E4 学生 收 PUBLISHED_NOTICE → 「我的成绩」（复用既有页骨架）→ 明细/绩点/学分

E1/E5 预警命中 → t_acad_warning → 辅导员 PC #84 处置 或 移动端 3.6 跟进（同一记录）

E1 毕业预审（#88）学分/必修条件项自动重算 → E4 「毕业进度」红绿灯同步

E3 教师视图「成绩录入任务」（P2）状态推进可见

E6 平台：预警阈值规则变更 → 下次扫描即生效；关闭模块 → 成绩转历史只读

E2 门户（落地后）：/portal/academic-affairs/grades 同数据只读增强视图

```



### 9.2 学籍异动（转专业）：学生发起穿六端



```

E4 学生「异动申请」宫格 → 表单（类型/目标专业/材料）→ 提交

  [POST /api/v1/mobile/academic-affairs/roll-changes；在途唯一 409]

E5 辅导员移动审批（移动审批包装）或 E3/E1 PC 统一待办 → 初审

E1 原学院 #17 异动审批【同意转出】→ 目标学院【同意接收】→ 教务处终审

  [t_student_profile 专业/班级更新 + 培养方案版本重绑 + t_aa_status_change 流水]

E4 学生收 WORKFLOW_RESULT → 「我的学籍」显示新专业班级；「我的课表」下学期按新班级生成

E1 学工侧（13A）：班级画像/辅导员范围随主档班级变更自动切换（同读主档）

E6 平台：异动时间窗规则控制 E4 提交入口的开闭

```



### 9.3 课表发布：配置在 PC，触达在两移动端



```

E1 教务处 校历发布（#7，前置）→ 课表导入 #44（dry-run 行级错误）

  → 冲突报告 #49（教师/班级/教室/容量/周学时）→ 冲突清零 → 发布 #50

  [PUBLISHED_NOTICE 按班级学生与授课教师精确投递]

E4 学生「我的课表」周视图即时可见（教学周来自已发布校历）

E5 教师「今日课程」/E3 PC 教师课表 #47 同数据源

P2 调停课：教师发起 → 学院/教务审 → 课表更新 → 变更格子「调/停/补」角标 + STATUS_CHANGED

E6 平台：关闭模块 → 已发布课表转历史只读，新导入/发布停用

E2 门户（落地后）：大屏学期视图复用同端点

```



## 10. 六端入口验收要点（每端 ≥2 条，含越权与重复项）



| 端 | 验收用例（通过标准） |

|---|---|

| E1 PC 管理端 | ① 教务处账号见「教务中心」13 叶子且与「学业过程」菜单并存互链；② 学生令牌直输 /admin/academic-affairs → 403 + 审计；③ 校历未发布时任务批次创建被前置校验拦截（明确提示） |

| E2 学生 PC 门户 | ① V1 期间门户不提供教务业务入口；② 门户落地后成绩/课表只读（无修改按钮），模块关闭渲染 ModuleDisabledView |

| E3 教师 PC 工作台 | ① 任课教师视图只见本人课程/任务/名单（COURSE 范围），越权访问他人课程学生 403002；② 异动审批 PC 与移动并发 → 后处理方 409 并刷新 |

| E4 学生小程序 | ① 学生提交异动申请 → 仅一条在途单（重复 409 跳在途详情）；② 学生 A 访问学生 B 学籍/成绩 → 后端 403/404 + 审计（my 端点 token 注入）；③ 课表未发布 → empty 态不报错；④ P2 宫格（考试/补考重修）V1 不渲染 |

| E5 教师移动端 | ① 预警处置成功 → 移动列表消失、PC 预警列表状态同步；② 今日课程与 PC 教师课表同数据源（发布后一致）；③ 成绩录入入口移动端不出现（回 PC 提示） |

| E6 平台运营端 | ① 关闭 academic-affairs → 六端按 §7.2 降级且「学业过程」不受牵连；② 修改预警规则阈值 → 下次扫描即按新规则命中（规则中心即刻生效语义） |



## 11. 教务服务宫格状态规则（E4 补充）



| 宫格 | 显示条件 | 置灰/空态条件 | 角标来源 | 隐藏条件 |

|---|---|---|---|---|

| 我的课表 | 常驻（分组首位） | 课表未发布→empty「尚未发布」（不报错） | 调停课变更红点（P2） | 模块关闭 |

| 我的课程 | 常驻 | 教学任务未审定→empty「课程尚未生成」 | — | 模块关闭 |

| 我的成绩 | 常驻（既有入口保留位次） | 无已发布成绩→empty | 新发布学期红点 | 学业过程授权独立判定 |

| 我的学籍 | 常驻 | — | 异动在途状态 | 模块关闭 |

| 异动申请 | 常驻 | 不在时间窗→提交按钮置灰+原因 | 在途单状态 | 模块关闭 |

| 我的学业预警 | 常驻 | 无预警→empty 正向文案 | 未关闭预警红点 | 学业过程授权独立判定 |

| 毕业进度 | 常驻（毕业年级置顶，低年级折叠） | 未入批次→降级实时学分进度（mode 字段） | 结论变化红点 | 模块关闭 |

| 我的考试 / 补考重修 | P2 上线后显示 | — | 考前提醒 | V1 一律不渲染（feature flag） |



## 12. 汇总



| 项 | 数量/结论 |

|---|---|

| E1 PC 管理端 | 菜单 1 组 13 叶子（★组）+ ☆组权限点隐藏；页面树 23 组（V1 核心 12 组），/admin/academic 并存互链 |

| E2 学生 PC 门户 | 8 入口，全部 ◇ 随 09B 落地（门户壳与骨架工程存在、业务路由未全量实现，如实标注）；V1 学生入口以小程序为准 |

| E3 教师 PC 工作台 | 11 类身份化入口（教务处/学院教务/专业负责人/任课教师四视图），V1 8 类 |

| E4 学生小程序 | 9 入口（V1 ★7：课表/课程/成绩/学籍/异动(唯一可写)/预警/毕业进度），P2 宫格 feature flag 不渲染 |

| E5 教师移动端 | 6 入口（V1 ★3：今日课程/授课班级/预警跟进；成绩录入等回 PC） |

| E6 平台运营端 | 授权项 `academic-affairs` + 教务规则组；关闭后六端降级口径统一，且与「学业过程」独立授权解耦 |

| 命名裁定执行 | 全文使用 academic-affairs/academicAffairs；旧文档 academic-affairs 字样待修订替换 |

