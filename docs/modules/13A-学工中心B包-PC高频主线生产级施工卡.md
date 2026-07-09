# 13A 学工中心 B 包-PC 高频主线生产级施工卡

> B 包是下一轮真实开发优先级最高的包。本文件是施工任务卡，不是本轮实现记录。

## 1. B 包范围

| 分段 | 模块 | 目标 | 建议提交 |
|---|---|---|---|
| B1 | 学工看板 + 学生画像 | 让辅导员/学院/学工处能从看板进入学生 360，并看到风险、请假、宿舍、资助、处分、谈话摘要 | `feat(student-affairs): add dashboard and student profile construction` |
| B2 | 班级管理 + 宿舍管理 | 建立班级/辅导员/宿舍数据范围基础和宿舍异常闭环 | `feat(student-affairs): add class and dorm management construction` |
| B3 | 请假销假 + 风险预警 | 打通学生申请、教师审批、销假、异常与风险处置 | `feat(student-affairs): add leave and risk workflow construction` |

强制边界：B 包不修数字迎新公共底座，不改 orientation 主链路，不改 internship、graduation、academic-affairs、miniapp 主链路，不提交 dist、node_modules、`.env`、`.claude`、query。

## 2. 页面施工卡字段标准

每张页面卡必须覆盖 37 项：页面名称、所属模块、建议路由、页面定位、使用角色、入口、数据来源、后端 API、数据表、查询条件、列表字段、详情字段、指标卡、按钮、状态机、审批流、权限、数据范围、敏感脱敏、审计、Excel 导入导出、空态、错误态、加载态、重试、画像联动、风险联动、看板联动、现有系统跳转、公共组件、后端测试、前端验收、是否阻断 PC 试运行、是否阻断正式上线、开发优先级、建议提交、备注。

## 2.1 B 包三级模块开发与关联布局

| 二级目录 | 三级模块 | 开发动作 | 页面布局 | 关联关系 |
|---|---|---|---|---|
| 学工看板 | 总看板 | 接聚合指标、待办、风险、宿舍异常；钻取到业务页 | 顶部筛选 + 指标卡 + 多列表分栏 + 右侧快捷入口 | 画像、风险、请假、宿舍 |
| 学工看板 | 辅导员工作台 | 接本人班级/学生待办，支持处理/转派/提醒 | 左侧班级筛选 + 中央待办 + 右侧重点学生 | 待办、画像、风险 |
| 学生画像 | 学生 360 | 聚合主档、迎新、请假、宿舍、资助、处分、谈话、风险 | 顶部学生卡 + 标签页 + 右侧敏感/风险/审计 | 所有业务回链画像 |
| 学生画像 | 成长事件/审计 | 展示来源事件、原单跳转、敏感查看审计 | 时间线 + 来源详情抽屉 + 审计抽屉 | 归档、风险、统计 |
| 班级管理 | 班级列表 | 组织/班级/辅导员绑定查询与导出 | 指标卡 + 筛选栏 + 主表 + 批量条 | 看板数据范围 |
| 班级管理 | 班级详情 | 学生名单、风险/请假/宿舍摘要 | 左表 + 右侧班级摘要 + 学生画像跳转 | 画像、风险、宿舍 |
| 班级管理 | 干部/绑定 | 干部任免、辅导员绑定、导入导出 | 双标签页 + 选择器 + 操作结果 | 权限数据范围 |
| 宿舍管理 | 宿舍基础 | 楼栋/房间/床位台账、导入导出 | 楼栋树 + 房间表 + 床位详情 | 画像宿舍卡 |
| 宿舍管理 | 入住调宿 | 入住、退宿、调宿审批、床位冲突 | 列表 + 详情抽屉 + 审批面板 | 风险、看板 |
| 宿舍管理 | 检查夜不归宿 | 检查、整改、夜不归宿、转风险 | 异常列表 + 文件区 + 风险按钮 | 风险预警 |
| 请假销假 | 请假审批 | 请假列表、详情、审批、退回、驳回 | 筛选表 + 详情抽屉 + 审批时间线 | 看板、画像 |
| 请假销假 | 延期销假 | 延期审批、销假确认、逾期转风险 | 待办表 + 确认面板 + 异常提示 | 风险预警 |
| 风险预警 | 风险列表 | 风险来源聚合、分派、等级筛选 | 风险表 + 来源入口 + 批量分派 | 看板、画像 |
| 风险预警 | 处置随访 | 接收、转派、处置、随访、关闭 | 主详情 + 随访时间线 + 审计区 | 归档、统计 |

## 3. B1 页面卡

### 3.1 学工总看板

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 学工总看板；学工看板；`/admin/student-affairs/dashboard` |
| 定位/角色/入口 | PC 高频首页；辅导员、学院负责人、学工处、校领导；左侧菜单“学工中心-看板” |
| 数据来源/API/表 | 请假、宿舍、风险、画像、资助、处分聚合；`GET /api/v1/student-affairs/dashboard`、`GET /dashboard/todos`、`GET /dashboard/risk-students`；`t_affairs_dashboard_metric`、各业务表 |
| 查询/列表/详情 | orgId、classId、dateStart/dateEnd、riskLevel；待办列表、风险学生列表、异常宿舍列表；钻取到学生画像/业务详情 |
| 指标卡/按钮 | 在校学生、今日请假、待销假、宿舍异常、风险待处置、资助待审；刷新、导出、钻取、切换组织 |
| 状态机/审批流 | 看板无业务状态机，只展示下游状态；待办跳审批任务 |
| 权限/数据范围 | 按角色范围裁剪；校领导默认汇总；详情跳转再次 403 校验 |
| 脱敏/审计/Excel | 手机/身份证/家庭经济脱敏；导出写台账；看板导出只导当前范围 |
| 空错加载重试 | 无指标显示 0；接口错显示重试；加载骨架屏 |
| 联动 | 点击学生进入画像；风险指标进风险列表；看板接受业务回写刷新 |
| 现有跳转/组件 | 迎新只摘要外链；用 `AppPageShell`、`AppMetricCard`、`AppToolbar`、`AppExportButton`、`AppRiskTag` |
| 测试/验收/阻断 | 测 401/403/范围/空态/导出审计；PC 验收指标不串租户；阻断 PC 试运行和正式上线 |
| 优先级/提交/备注 | P0；B1 提交；不得用假统计填充 |

### 3.2 辅导员工作台

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 辅导员工作台；学工看板；`/admin/student-affairs/counselor-workbench` |
| 定位/角色/入口 | 辅导员每日处理入口；辅导员、班主任；看板待办卡片 |
| 数据来源/API/表 | 绑定班级、待办、风险、请假、谈话计划；`GET /counselor/workbench`；`t_affairs_counselor_binding`、`t_unified_todo` |
| 查询/列表/详情 | 我的班级、状态、时间；待审批、待随访、待销假、待谈话；详情跳各业务页 |
| 指标卡/按钮 | 今日待办、超期待办、重点关注、未销假；处理、转交、批量提醒 |
| 状态机/审批流 | 读取下游任务状态；转交流程需记录原因 |
| 权限/数据范围 | 仅绑定班级/学生；班主任只看所属班级 |
| 脱敏/审计/Excel | 默认脱敏；批量导出需理由；所有转交/提醒审计 |
| 空错加载重试 | 无待办显示完成态；失败可重试 |
| 联动 | 学生名进画像；风险/请假/宿舍进详情；回写看板 |
| 现有跳转/组件 | 统一待办可跳转；用 `AppBatchActionBar`、`AppPermissionButton`、`AppStatusTag` |
| 测试/验收/阻断 | 测绑定范围、转交权限、批量动作；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B1；严禁把全校待办给辅导员 |

### 3.3 学生画像主页

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 学生画像；学生画像；`/admin/student-affairs/students/:studentId/profile` |
| 定位/角色/入口 | 学生 360 总入口；辅导员、班主任、学院、学工处、授权老师；看板/班级/风险/请假跳入 |
| 数据来源/API/表 | 学生主档、学籍、迎新、请假、宿舍、资助、处分、谈话、风险；`GET /students/{id}/profile`；`t_affairs_profile_extension`、`t_affairs_growth_event` |
| 查询/列表/详情 | studentId；时间线按事件类型筛选；基础信息、联系方式、班级、宿舍、风险等级、事件流 |
| 指标卡/按钮 | 请假次数、宿舍异常、风险等级、资助记录、处分记录；编辑标签、敏感解锁、导出画像摘要 |
| 状态机/审批流 | 无主状态机；展示各事件状态 |
| 权限/数据范围 | 详情强校验；超范围 403；心理详情仅授权可见 |
| 脱敏/审计/Excel | 身份证/手机/家庭经济/心理敏感脱敏；敏感解锁必须填原因并审计；导出默认不含敏感 |
| 空错加载重试 | 无事件显示空时间线；接口失败可重试 |
| 联动 | 画像是风险、看板、归档主入口；支持跳业务原单 |
| 现有跳转/组件 | 迎新、教务、宿舍、资助原系统链接；用 `AppSensitiveText`、`AppAuditTrail`、`AppWorkflowTimeline` |
| 测试/验收/阻断 | 测敏感授权、审计、跨班级 403、导出脱敏；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B1；不得复制学生主档形成双主数据 |

### 3.4 学生成长事件与审计抽屉

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 成长事件抽屉；学生画像；`/admin/student-affairs/students/:studentId/events` |
| 定位/角色/入口 | 查看单个学生事件流；有画像权限角色；画像页时间线 |
| 数据来源/API/表 | 画像事件、业务来源；`GET /students/{id}/events`、`GET /students/{id}/audit-trail`；`t_affairs_growth_event`、`t_affairs_audit_trail` |
| 查询/列表/详情 | eventType、dateRange、sourceModule；事件时间、标题、状态、来源、操作者；原单摘要 |
| 指标卡/按钮 | 无；跳原单、申请敏感查看、导出摘要 |
| 状态机/审批流 | 事件跟随来源状态 |
| 权限/数据范围 | 来源明细二次鉴权；无权仅看摘要或隐藏 |
| 脱敏/审计/Excel | 审计不可导出敏感详情；查看审计本身写安全日志 |
| 空错加载重试 | 无事件空态；错误保留画像主信息 |
| 联动 | 与画像、归档、风险闭环 |
| 现有跳转/组件 | 原单跳转；`AppDescriptionList`、`AppAuditTrail`、`AppFilePreview` |
| 测试/验收/阻断 | 测源单权限、敏感隐藏、审计列表；阻断正式上线 |
| 优先级/提交/备注 | P1；B1；事件必须可追溯来源 |

## 4. B2 页面卡

### 4.1 班级列表

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 班级列表；班级管理；`/admin/student-affairs/classes` |
| 定位/角色/入口 | 管理班级与负责人；辅导员、班主任、学院、学工处；菜单“班级管理” |
| 数据来源/API/表 | 组织/学生主数据、辅导员绑定；`GET /classes`；`t_affairs_counselor_binding` |
| 查询/列表/详情 | 学院、专业、年级、辅导员、关键词；班级、人数、辅导员、风险数、请假数；跳详情 |
| 指标卡/按钮 | 班级数、学生数、未绑定班级；新增绑定、导出、批量分配 |
| 状态机/审批流 | 绑定启用/停用；无审批 |
| 权限/数据范围 | 学院只本院；辅导员只本人绑定 |
| 脱敏/审计/Excel | 导出班级名单按范围裁剪；分配写审计 |
| 空错加载重试 | 无班级提示联系管理员；失败重试 |
| 联动 | 班级进入画像列表、看板筛选、风险范围 |
| 现有跳转/组件 | 组织架构联动；`AppOrgCascader`、`AppTeacherPicker`、`AppExportButton` |
| 测试/验收/阻断 | 测范围、批量绑定、导出；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B2；不修改组织主数据 |

### 4.2 班级详情与学生名单

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 班级详情；班级管理；`/admin/student-affairs/classes/:classId` |
| 定位/角色/入口 | 查看班级学生与学工摘要；辅导员、班主任、学院；班级列表 |
| 数据来源/API/表 | 学生主档、画像扩展、风险、请假；`GET /classes/{id}`、`GET /classes/{id}/students` |
| 查询/列表/详情 | keyword、riskLevel、dormStatus、leaveStatus；学号、姓名、宿舍、风险、请假、联系方式脱敏 |
| 指标卡/按钮 | 班级人数、重点关注、当前请假、宿舍异常；导出、批量提醒、进入画像 |
| 状态机/审批流 | 无主流程 |
| 权限/数据范围 | classId 必须在角色范围内 |
| 脱敏/审计/Excel | 联系方式脱敏；导出名单写审计 |
| 空错加载重试 | 无学生空态；加载分页 |
| 联动 | 画像、风险、请假、宿舍 |
| 现有跳转/组件 | 学籍详情只跳现有学生中心；`AppStudentPicker`、`AppStatusTag` |
| 测试/验收/阻断 | 测跨班级 403、分页、导出范围；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B2 |

### 4.3 班干部与辅导员绑定

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 班干部/绑定；班级管理；`/admin/student-affairs/classes/:classId/cadres-bindings` |
| 定位/角色/入口 | 维护班干部、辅导员/班主任绑定；学院、学工处、授权辅导员；班级详情 |
| 数据来源/API/表 | `GET/POST /classes/{id}/cadres`、`GET/POST /classes/{id}/counselor-bindings`；`t_affairs_class_cadre`、`t_affairs_counselor_binding` |
| 查询/列表/详情 | activeOnly、role；干部姓名、任职、起止；绑定老师、类型、有效期 |
| 指标卡/按钮 | 无；新增、停用、换届、批量导入 |
| 状态机/审批流 | active/inactive；可配置是否需学院确认 |
| 权限/数据范围 | 学院/学工处可维护，普通辅导员按授权维护干部 |
| 脱敏/审计/Excel | 导入 xlsx；错误行导出；任免/绑定审计 |
| 空错加载重试 | 未设置空态 |
| 联动 | 数据范围、看板、班级详情 |
| 现有跳转/组件 | 教师/学生选择器；`AppTeacherPicker`、`AppStudentPicker`、`AppOperationResult` |
| 测试/验收/阻断 | 测唯一约束、停用历史、导入错误行；阻断正式上线 |
| 优先级/提交/备注 | P1；B2 |

### 4.4 宿舍楼栋/房间/床位

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 宿舍基础数据；宿舍管理；`/admin/student-affairs/dorms/buildings` |
| 定位/角色/入口 | 维护楼栋房间床位；宿管员、学工处、系统授权人员；菜单“宿舍管理” |
| 数据来源/API/表 | `GET/POST /dorm/buildings`、`/rooms`、`/beds`；`t_affairs_dorm_building`、`t_affairs_dorm_room`、`t_affairs_dorm_bed` |
| 查询/列表/详情 | 校区、楼栋、楼层、房间、入住状态；床位、学生、状态、容量 |
| 指标卡/按钮 | 床位总数、空床、满员房间；新增、启停、导入、导出 |
| 状态机/审批流 | enabled/disabled、occupied/vacant/locked |
| 权限/数据范围 | 宿管员只授权楼栋；辅导员仅查看学生住宿 |
| 脱敏/审计/Excel | 批量导入房间床位；导出不含敏感联系方式；配置审计 |
| 空错加载重试 | 无床位提示导入/新增；错误重试 |
| 联动 | 班级、画像、风险、宿舍异常 |
| 现有跳转/组件 | 无后勤系统则学工自建基础台账；`AppOrgCascader`、`AppExportButton` |
| 测试/验收/阻断 | 测唯一房间/床位、楼栋范围、导入错误；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B2 |

### 4.5 入住、退宿与调宿

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 入住调宿；宿舍管理；`/admin/student-affairs/dorms/assignments` |
| 定位/角色/入口 | 管理学生住宿变更；宿管员、辅导员、学院；宿舍管理 |
| 数据来源/API/表 | `GET /dorm/assignments`、`POST /dorm/checkin`、`POST /dorm/transfers/{id}/actions/*`；`t_affairs_dorm_checkin_record`、`t_affairs_dorm_transfer_request` |
| 查询/列表/详情 | 学生、班级、楼栋、状态、时间；当前床位、申请床位、原因、审批记录 |
| 指标卡/按钮 | 当前入住、调宿待审、空床；入住、退宿、发起调宿、审批 |
| 状态机/审批流 | draft/submitted/dorm_review/counselor_review/approved/rejected/moved/archived |
| 权限/数据范围 | 宿管楼栋范围 + 辅导员学生范围交叉校验 |
| 脱敏/审计/Excel | 批量入住 xlsx；调宿审批审计；导出床位台账 |
| 空错加载重试 | 无记录空态；冲突提示床位已占用 |
| 联动 | 画像宿舍卡、风险夜不归宿、看板异常 |
| 现有跳转/组件 | 学生选择器、审批面板；`AppApprovalPanel`、`AppWorkflowTimeline` |
| 测试/验收/阻断 | 测床位并发、范围、非法状态流转；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B2 |

### 4.6 宿舍检查与夜不归宿

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 宿舍检查；宿舍管理；`/admin/student-affairs/dorms/inspections`、`/night-absence` |
| 定位/角色/入口 | 检查登记和异常处置；宿管员、辅导员、学工处；宿舍菜单/看板异常 |
| 数据来源/API/表 | `GET/POST /dorm/inspections`、`GET/POST /dorm/night-absence`；`t_affairs_dorm_inspection`、`t_affairs_night_absence` |
| 查询/列表/详情 | 楼栋、房间、日期、状态、风险等级；扣分项、整改、学生、处置人 |
| 指标卡/按钮 | 待整改、夜不归宿、重复异常；登记、确认、转风险、关闭 |
| 状态机/审批流 | 检查 draft/submitted/confirmed/rectifying/rectified/closed；夜不归宿 pending/assigned/handling/closed/false_positive |
| 权限/数据范围 | 宿管按楼栋，辅导员按学生，学工处全校 |
| 脱敏/审计/Excel | 异常导出脱敏；转风险写审计 |
| 空错加载重试 | 无异常显示良好态 |
| 联动 | 异常进入风险、画像、看板 |
| 现有跳转/组件 | `AppRiskTag`、`AppFileList`、`AppBatchActionBar` |
| 测试/验收/阻断 | 测转风险去重、楼栋范围、关闭审计；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B2 |

## 5. B3 页面卡

### 5.1 请假列表与详情

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 请假管理；请假销假；`/admin/student-affairs/leaves`、`/leaves/:id` |
| 定位/角色/入口 | 管理学生请假；辅导员、学院、学工处、学生端来源；菜单/看板待办 |
| 数据来源/API/表 | 扩展 `t_cs_leave`；`GET /leave`、`GET /leave/{id}`；`t_affairs_leave_application` |
| 查询/列表/详情 | 学生、班级、请假类型、状态、起止、是否逾期；详情含目的地、联系人、附件、审批流 |
| 指标卡/按钮 | 当前请假、逾期、待销假；审批、退回、驳回、代请假、导出 |
| 状态机/审批流 | draft/submitted/counselor_review/college_review/student_affairs_review/approved/rejected/returned/cancelled/overdue/closed |
| 权限/数据范围 | 学生本人；辅导员绑定；学院本院；学工处全校 |
| 脱敏/审计/Excel | 电话脱敏；请假导出需理由；代请假与审批审计 |
| 空错加载重试 | 无请假空态；非法状态提示 |
| 联动 | 画像请假卡、看板指标、风险规则 |
| 现有跳转/组件 | 小程序学生申请；`AppApprovalPanel`、公共日期组件、`AppExportButton` |
| 测试/验收/阻断 | 测 401/403/状态流转/范围/日期校验；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B3；不得新建重复请假主表 |

### 5.2 延期与销假

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 延期销假；请假销假；`/admin/student-affairs/leaves/extensions-cancellations` |
| 定位/角色/入口 | 闭环请假后续；学生、辅导员、学院；请假详情/待办 |
| 数据来源/API/表 | `POST /leave/{id}/extensions`、`POST /leave/{id}/cancellations`、`POST /leave/cancellations/{id}/confirm`；`t_affairs_leave_extension`、`t_affairs_leave_cancellation` |
| 查询/列表/详情 | 状态、学生、时间；延期理由、返校时间、附件、确认人 |
| 指标卡/按钮 | 待确认销假、延期待审、逾期未归；确认、驳回、转风险 |
| 状态机/审批流 | 延期 submitted/review/approved/rejected；销假 submitted/confirmed/rejected/auto_closed |
| 权限/数据范围 | 学生本人提交，审批按流程任务 |
| 脱敏/审计/Excel | 导出默认不含联系电话；确认写审计 |
| 空错加载重试 | 无待办空态 |
| 联动 | 逾期进风险和看板 |
| 现有跳转/组件 | 小程序销假入口；`AppWorkflowTimeline`、`AppFilePreview` |
| 测试/验收/阻断 | 测超期、非法延期、重复销假、转风险；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B3 |

### 5.3 风险预警列表

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 风险预警；风险预警；`/admin/student-affairs/risks` |
| 定位/角色/入口 | 学生风险发现与分派；辅导员、学院、学工处、校领导摘要；菜单/看板/画像 |
| 数据来源/API/表 | 请假、宿舍、处分、心理授权摘要、手工登记；`GET /risk/events`；`t_affairs_risk_event`、`t_affairs_risk_rule` |
| 查询/列表/详情 | 风险等级、类型、状态、来源、组织、时间；学生、触发原因、处置人、下一次跟进 |
| 指标卡/按钮 | 高风险、待分派、逾期未跟进、已关闭；新增、分派、处置、关闭、导出 |
| 状态机/审批流 | new/assigned/handling/following/closed/ignored；高风险关闭需复核 |
| 权限/数据范围 | 辅导员看绑定学生；学院本院；校领导看汇总；心理敏感仅授权摘要 |
| 脱敏/审计/Excel | 风险原因脱敏；心理详情不导出；查看/导出全审计 |
| 空错加载重试 | 无风险显示正常态；失败重试 |
| 联动 | 画像风险卡、看板风险指标、归档风险摘要 |
| 现有跳转/组件 | 来源原单跳转；`AppRiskTag`、`AppSensitiveText`、`AppExportConfirm` |
| 测试/验收/阻断 | 测规则触发、去重、范围、心理隐藏；阻断 PC 试运行 |
| 优先级/提交/备注 | P0；B3 |

### 5.4 风险处置与随访

| 字段 | 内容 |
|---|---|
| 页面名称/模块/路由 | 风险处置详情；风险预警；`/admin/student-affairs/risks/:id` |
| 定位/角色/入口 | 风险闭环工作页；处置人、学院、学工处；风险列表/画像 |
| 数据来源/API/表 | `GET /risk/events/{id}`、`POST /risk/events/{id}/handles`、`POST /risk/events/{id}/followups`、`POST /risk/events/{id}/close`；`t_affairs_risk_handle`、`t_affairs_risk_followup` |
| 查询/列表/详情 | id；风险详情、来源、处置记录、随访计划、附件、审计 |
| 指标卡/按钮 | 无；接收、转派、记录处置、添加随访、关闭、升级 |
| 状态机/审批流 | assigned -> handling -> following -> closed；高风险关闭复核 |
| 权限/数据范围 | 处置人/上级可见；转派目标必须在范围内 |
| 脱敏/审计/Excel | 敏感信息按来源权限显示；每次查看和处置审计 |
| 空错加载重试 | 无权限 403；记录失败可重试 |
| 联动 | 处置结果写画像、看板、归档 |
| 现有跳转/组件 | 心理来源只显示授权摘要；`AppApprovalPanel`、`AppAuditTrail`、`AppFileList` |
| 测试/验收/阻断 | 测非法关闭、复核、转派范围、敏感审计；阻断正式上线 |
| 优先级/提交/备注 | P0；B3；不得伪造心理诊断 |

## 6. B 包验收清单

| 验收项 | B1 | B2 | B3 |
|---|---|---|---|
| 401/403/跨租户 | 必测 | 必测 | 必测 |
| 数据范围 | 看板、画像 | 班级、宿舍楼栋 | 请假、风险 |
| 敏感脱敏 | 画像必测 | 学生联系方式 | 风险/请假联系方式 |
| 审计 | 敏感查看/导出 | 绑定/调宿/导入 | 审批/处置/导出 |
| Excel | 看板/画像摘要导出 | 班干部、床位、入住导入导出 | 请假/风险导出 |
| 空错加载 | 所有页面 | 所有页面 | 所有页面 |
| 公共组件 | 禁止自写基础件 | 禁止自写基础件 | 禁止自写基础件 |

## 7. B 包三级页面全量索引（开发前契约核对用）

> 下列页面为 B 包必须覆盖的全部三级入口。`父页/面板` 表示与同路由 Tab 或看板分栏合并实现；独立页须单独路由与验收。

| 二级模块 | 三级页面 | 路由建议 | 实现形态 | 父页/面板 | 优先级 | 阻断 PC | 阻断上线 |
|---|---|---|---|---|---|---|---|
| 学工看板 | 学工总览 | `/admin/student-affairs/dashboard` | 独立页 | — | P0 | 是 | 是 |
| 学工看板 | 今日待办 | 同上 `?panel=todos` | 看板分栏 | 学工总览 | P0 | 是 | 是 |
| 学工看板 | 辅导员待办 | `/admin/student-affairs/counselor-workbench` | 独立页 | — | P0 | 是 | 是 |
| 学工看板 | 学生风险概览 | `/dashboard?panel=risk` | 看板分栏 | 学工总览 | P0 | 是 | 是 |
| 学工看板 | 请假审批概览 | `/dashboard?panel=leave` | 看板分栏 | 学工总览 | P0 | 是 | 是 |
| 学工看板 | 宿舍异常概览 | `/dashboard?panel=dorm` | 看板分栏 | 学工总览 | P0 | 是 | 是 |
| 学工看板 | 重点学生提醒 | `/dashboard?panel=key-students` | 看板分栏 | 学工总览 | P0 | 是 | 是 |
| 学生画像 | 学生主档摘要 | `/students/:id/profile#basic` | 画像 Tab | 学生360 | P0 | 是 | 是 |
| 学生画像 | 学籍状态摘要 | `#academic` | 画像 Tab | 学生360 | P0 | 是 | 是 |
| 学生画像 | 班级信息 | `#class` | 画像 Tab | 学生360 | P0 | 是 | 是 |
| 学生画像 | 家庭与联系人摘要 | `#family` | 画像 Tab | 学生360 | P0 | 是 | 是 |
| 学生画像 | 请假记录摘要 | `#leave` | 画像 Tab | 学生360 | P0 | 是 | 是 |
| 学生画像 | 宿舍信息摘要 | `#dorm` | 画像 Tab | 学生360 | P0 | 是 | 是 |
| 学生画像 | 风险标签 | `#risk` | 画像 Tab | 学生360 | P0 | 是 | 是 |
| 学生画像 | 成长时间线 | `/students/:id/events` | 抽屉/Tab | 学生360 | P1 | 否 | 是 |
| 学生画像 | 数据变更日志入口 | `#audit` | 画像 Tab | 学生360 | P1 | 否 | 是 |
| 班级管理 | 班级列表 | `/admin/student-affairs/classes` | 独立页 | — | P0 | 是 | 是 |
| 班级管理 | 班级详情 | `/classes/:classId` | 独立页 | — | P0 | 是 | 是 |
| 班级管理 | 班级学生 | `/classes/:classId#students` | 详情 Tab | 班级详情 | P0 | 是 | 是 |
| 班级管理 | 辅导员绑定 | `/classes/:classId/cadres-bindings#counselor` | 详情 Tab | 班干部绑定页 | P1 | 否 | 是 |
| 班级管理 | 班主任绑定 | 同上 `#head-teacher` | 详情 Tab | 班干部绑定页 | P1 | 否 | 是 |
| 班级管理 | 班干部管理 | 同上 `#cadres` | 详情 Tab | 班干部绑定页 | P1 | 否 | 是 |
| 班级管理 | 班级通讯录 | `/classes/:classId#contacts` | 详情 Tab | 班级详情 | P1 | 是 | 是 |
| 班级管理 | 班级风险概览 | `/classes/:classId#risk` | 详情 Tab | 班级详情 | P0 | 是 | 是 |
| 班级管理 | 班级请假统计 | `#leave-stats` | 详情 Tab | 班级详情 | P1 | 否 | 否 |
| 班级管理 | 班级宿舍统计 | `#dorm-stats` | 详情 Tab | 班级详情 | P1 | 否 | 否 |
| 班级管理 | 班级档案入口 | `#archive` | 详情 Tab | 班级详情 | P2 | 否 | 否 |
| 宿舍管理 | 宿舍看板 | `/admin/student-affairs/dorms/dashboard` | 独立页 | — | P0 | 是 | 是 |
| 宿舍管理 | 楼栋管理 | `/dorms/buildings` | 独立页 | 宿舍基础 | P0 | 是 | 是 |
| 宿舍管理 | 房间管理 | `/dorms/buildings#rooms` | Tab | 宿舍基础 | P0 | 是 | 是 |
| 宿舍管理 | 床位管理 | `/dorms/buildings#beds` | Tab | 宿舍基础 | P0 | 是 | 是 |
| 宿舍管理 | 入住管理 | `/dorms/assignments#checkin` | Tab | 入住调宿 | P0 | 是 | 是 |
| 宿舍管理 | 退宿管理 | `#checkout` | Tab | 入住调宿 | P0 | 是 | 是 |
| 宿舍管理 | 调宿申请 | `/dorms/transfers` | 独立页 | — | P0 | 是 | 是 |
| 宿舍管理 | 调宿审批 | `/dorms/transfers?status=pending` | 列表筛选 | 调宿申请 | P0 | 是 | 是 |
| 宿舍管理 | 宿舍检查 | `/dorms/inspections` | 独立页 | — | P0 | 是 | 是 |
| 宿舍管理 | 夜不归宿 | `/dorms/night-absence` | 独立页 | — | P0 | 是 | 是 |
| 宿舍管理 | 宿舍异常 | `/dorms/exceptions` | 独立页 | — | P0 | 是 | 是 |
| 宿舍管理 | 宿舍统计摘要 | `/dorms/dashboard#stats` | 看板分栏 | 宿舍看板 | P1 | 否 | 否 |
| 宿舍管理 | 宿舍归档入口 | `#archive` | 外链 D | 宿舍看板 | P2 | 否 | 否 |
| 请假销假 | 请假看板 | `/admin/student-affairs/leaves/dashboard` | 独立页 | — | P0 | 是 | 是 |
| 请假销假 | 请假申请列表 | `/leaves?tab=applications` | Tab | 请假管理 | P0 | 是 | 是 |
| 请假销假 | 请假审批 | `/leaves?tab=approvals` | Tab | 请假管理 | P0 | 是 | 是 |
| 请假销假 | 续假申请 | `/leaves/extensions-cancellations#extension` | Tab | 延期销假 | P0 | 是 | 是 |
| 请假销假 | 续假审批 | 同上 `?status=pending` | 筛选 | 延期销假 | P0 | 是 | 是 |
| 请假销假 | 销假管理 | `#cancellation` | Tab | 延期销假 | P0 | 是 | 是 |
| 请假销假 | 归寝核验 | `/leaves/return-dorm-check` | 独立页 | — | P1 | 是 | 是 |
| 请假销假 | 长假审批 | `/leaves?type=long` | 筛选 | 请假审批 | P0 | 是 | 是 |
| 请假销假 | 外出备案 | `/leaves/outbound-records` | 独立页 | — | P1 | 否 | 是 |
| 请假销假 | 请假异常 | `/leaves/exceptions` | 独立页 | — | P0 | 是 | 是 |
| 请假销假 | 超期未销假 | `/leaves/overdue` | 独立页 | — | P0 | 是 | 是 |
| 请假销假 | 请假规则配置 | `/leaves/rules` | 独立页 | — | P1 | 否 | 是 |
| 请假销假 | 请假台账 | `/leaves/ledger` | 独立页 | — | P1 | 否 | 是 |
| 请假销假 | 请假统计 | `/leaves/stats` | 摘要 D | 请假看板 | P2 | 否 | 否 |
| 请假销假 | 请假归档入口 | `#archive` | 外链 D | 请假看板 | P2 | 否 | 否 |
| 风险预警 | 风险看板 | `/admin/student-affairs/risks/dashboard` | 独立页 | — | P0 | 是 | 是 |
| 风险预警 | 风险学生 | `/risks?tab=students` | Tab | 风险列表 | P0 | 是 | 是 |
| 风险预警 | 学业风险摘要 | `/risks?type=academic` | 筛选/卡片 | 风险看板 | P1 | 否 | 否 |
| 风险预警 | 请假异常风险 | `?type=leave` | 筛选 | 风险看板 | P0 | 是 | 是 |
| 风险预警 | 夜不归宿风险 | `?type=night-absence` | 筛选 | 风险看板 | P0 | 是 | 是 |
| 风险预警 | 心理关注风险摘要 | `?type=psych` | 筛选 | 风险看板 | P1 | 否 | 是 |
| 风险预警 | 违纪风险 | `?type=discipline` | 筛选 C联动 | 风险看板 | P1 | 否 | 是 |
| 风险预警 | 经济困难风险 | `?type=aid` | 筛选 C联动 | 风险看板 | P1 | 否 | 是 |
| 风险预警 | 实习异常风险 | `?type=internship` | 外链摘要 | 风险看板 | P2 | 否 | 否 |
| 风险预警 | 多维风险合并 | `/risks/merge-rules` | 独立页 | — | P1 | 否 | 是 |
| 风险预警 | 风险处置 | `/risks/:id#handle` | 详情 Tab | 风险处置详情 | P0 | 是 | 是 |
| 风险预警 | 风险跟进 | `#followup` | 详情 Tab | 风险处置详情 | P0 | 是 | 是 |
| 风险预警 | 风险关闭 | `#close` | 详情动作 | 风险处置详情 | P0 | 是 | 是 |
| 风险预警 | 风险规则配置 | `/risks/rules` | 独立页 | — | P1 | 否 | 是 |
| 风险预警 | 风险统计摘要 | `/risks/dashboard#stats` | 看板分栏 D | 风险看板 | P2 | 否 | 否 |

## 8. B 包三级页面施工卡（全量补充）

> 与 §3–§5 已写页面卡合并阅读。每张卡覆盖 43 项，压缩为六段：`定位`（1-8）、`数据流`（9-11）、`关联`（12-18）、`接口表`（19-24）、`流程权限`（25-29）、`导入导出态组件验收`（30-43）。未重复展开的页面与父页共用 API/权限，仅列差异。

### 8.1 学工看板补充面板

| 三级页面 | 定位 | 数据流 | 关联 | 接口表 | 流程权限 | 导入导出态组件验收 |
|---|---|---|---|---|---|---|
| 今日待办 | 路由：`/dashboard?panel=todos`；角色：与总看板同；入口：总看板左栏 | 来源：`GET /dashboard/todos`；处理：按类型筛选待办；下游：跳审批/风险/销假 | 画像钻取；风险/请假/宿舍看板指标；统计待办量；归档无 | `t_unified_todo`；筛选：type、逾期、班级 | 只读+跳转；范围同总看板；审计：批量提醒 | 无导入；空态「今日已完成」；`AppStatusTag`；测 403；P0；commit 随 dashboard |
| 学生风险概览 | `?panel=risk`；校领导/学院/辅导员 | 来源：`GET /dashboard/risk-students`；处理：分级列表；下游：风险列表/画像 | 画像风险区；风险全部类型；看板核心；统计高风险数 | 筛选：level、source；列表：学生、等级、来源、负责人 | 心理来源只摘要；范围裁剪；审计导出 | 导出脱敏；`AppRiskTag`；阻断 PC；P0 |
| 请假审批概览 | `?panel=leave` | 来源：请假待审聚合；处理：按班级/类型；下游：请假审批页 | 画像请假区；风险请假异常；看板待审数；统计请假率 | `t_affairs_leave_application`；按钮：批量提醒 | 审批人可见；审计 | 无导入；异常重试；`AppMetricCard`；P0 |
| 宿舍异常概览 | `?panel=dorm` | 来源：检查+夜不归宿+调宿异常；处理：异常列表；下游：宿舍异常/夜不归宿 | 画像宿舍区；风险夜不归宿；看板异常数；归档宿舍材料 | `t_affairs_night_absence`、`t_affairs_dorm_inspection` | 宿管楼栋+辅导员学生交叉；审计转风险 | 导出台账；`AppRiskTag`；P0 |
| 重点学生提醒 | `?panel=key-students` | 来源：风险+超期请假+未销假+重点关注标签；处理：提醒列表；下游：画像/风险 | 画像标签；风险高风险；看板重点提醒；统计重点人数 | `t_affairs_profile_extension.tags`；按钮：提醒、进画像 | 绑定范围；批量提醒审计 | 空态无重点；`AppBatchActionBar`；P0 |

### 8.2 学生画像摘要区块（merged 施工）

| 三级页面 | 定位 | 数据流 | 关联 | 接口表 | 流程权限 | 导入导出态组件验收 |
|---|---|---|---|---|---|---|
| 学生主档摘要 | `#basic`；跳 `/admin/student/:id` 原单 | 来源：学生主档只读；不产生主档变更 | 画像核心；迎新/教务外链；不关联实习毕设主流程 | `GET /students/{id}/profile#basic`；字段：学号、姓名、证件脱敏、手机脱敏 | 二次鉴权；敏感解锁审计 | `AppSensitiveText`；禁止学工内编辑主档；P0 |
| 学籍状态摘要 | `#academic`；教务外链 | 来源：教务学籍 API 摘要；下游：画像事件 | 看板无；统计学籍结构 D | 只读；状态：在读/休学/异动 | 教务范围；审计跳转 | 空态「暂无学籍摘要」；external-link；P0 |
| 班级信息 | `#class` | 来源：班级绑定+组织；下游：班级详情 | 班级管理；看板班级筛选 | `t_affairs_counselor_binding` | 班级范围 | `AppDescriptionList`；P0 |
| 家庭与联系人摘要 | `#family` | 来源：主档+家校 C；下游：家校联系 | 风险经济困难；C包补全；敏感脱敏 | 家庭字段脱敏；查看审计 | 资助/辅导员授权 | `AppSensitiveText`；导出不含明细；P0 |
| 请假记录摘要 | `#leave` | 来源：`t_cs_leave`；下游：请假详情 | 看板请假；风险请假；归档请假材料 D | 最近 N 条；状态标签 | 学生范围 | `AppStatusTag`；跳请假详情；P0 |
| 宿舍信息摘要 | `#dorm` | 来源：床位台账；下游：调宿/检查 | 风险夜不归宿；看板宿舍 | `t_affairs_dorm_bed` | 宿管/辅导员范围 | 空态未分配宿舍；P0 |
| 风险标签 | `#risk` | 来源：风险事件；下游：风险详情 | 看板风险；统计风险 D | `t_affairs_risk_event`；`AppRiskTag` | 心理只摘要 | 未授权隐藏心理来源；P0 |
| 成长时间线 | 见 §3.4 | — | — | — | — | — |
| 数据变更日志入口 | `#audit` | 来源：审计日志；下游：审计抽屉 | 归档审计；统计无 | `GET /students/{id}/audits` | 查看写安全日志 | `AppAuditTrail`；P1 |

### 8.3 班级 / 宿舍 / 请假 / 风险补充页

| 三级页面 | 路由 | 核心开发动作 | API 建议 | 状态机 | 权限范围 | 公共组件 | 优先级 | commit 建议 |
|---|---|---|---|---|---|---|---|---|
| 班级学生 | `classes/:id#students` | 分页名单、筛选、跳画像 | `GET /classes/{id}/students` | — | classId 范围 | `AppStudentPicker` | P0 | 随 class detail |
| 班级通讯录 | `#contacts` | 脱敏电话、导出审计 | `GET /classes/{id}/contacts` | — | 导出需理由 | `AppSensitiveText`、`AppExportConfirm` | P1 | 随 class detail |
| 班级风险/请假/宿舍统计 | `#risk` `#leave-stats` `#dorm-stats` | 只读指标卡，钻取业务页 | `GET /classes/{id}/summary` | — | 班级范围 | `AppMetricCard` | P1 | 随 class detail |
| 宿舍看板 | `/dorms/dashboard` | 空床、满员、异常、待调宿指标 | `GET /dorm/dashboard` | — | 楼栋范围 | `AppMetricCard` | P0 | `feat(student-affairs): add dorm dashboard` |
| 调宿申请/审批 | `/dorms/transfers` | 与 §4.5 入住调宿共用表，独立筛选待审 | `POST /dorm/transfers` | 同调宿状态机 | 宿管+辅导员交叉 | `AppApprovalPanel` | P0 | 随 dorm assignment |
| 宿舍异常 | `/dorms/exceptions` | 聚合检查+夜不归宿+未整改 | `GET /dorm/exceptions` | 各来源状态 | 楼栋/学生范围 | `AppRiskTag` | P0 | `feat(student-affairs): add dorm exceptions` |
| 请假看板 | `/leaves/dashboard` | 当前请假、待审、逾期、待销假 | `GET /leave/dashboard` | — | 范围裁剪 | `AppMetricCard` | P0 | `feat(student-affairs): add leave dashboard` |
| 请假申请列表 | `/leaves?tab=applications` | 与 §5.1 共用，Tab 分离申请视角 | `GET /leave?role=applicant` | 请假状态机 | 学生本人/辅导员代录 | `AppApprovalPanel` | P0 | 随 leave page |
| 归寝核验 | `/leaves/return-dorm-check` | 销假+宿舍联动核验 | `POST /leave/return-dorm-check` | submitted/confirmed | 辅导员/宿管 | 公共日期 | P1 | `feat(student-affairs): add return dorm check` |
| 外出备案 | `/leaves/outbound-records` | 长假目的地备案台账 | `GET/POST /leave/outbound` | 备案状态 | 学院范围 | `AppExportButton` | P1 | 随 leave |
| 请假异常/超期未销假 | `/leaves/exceptions`、`/overdue` | 定时任务扫描+待办 | `GET /leave/exceptions` | pending→risk | 辅导员范围 | `AppRiskTag` | P0 | 随 leave |
| 请假规则配置 | `/leaves/rules` | 天数、审批链、附件要求 | `GET/POST /leave/rules` | enabled/disabled | 学工处 | 学校参数联动 | P1 | `feat(student-affairs): add leave rules` |
| 请假台账 | `/leaves/ledger` | 筛选导出 xlsx 水印审计 | `POST /leave/exports` | — | 导出范围 | `AppExportConfirm` | P1 | 随 leave |
| 风险看板 | `/risks/dashboard` | 分级统计、来源分布、待处置 | `GET /risk/dashboard` | — | 汇总权限 | `AppMetricCard`、`AppRiskTag` | P0 | `feat(student-affairs): add risk dashboard` |
| 风险学生 | `/risks?tab=students` | 与 §5.3 列表共用 | `GET /risk/events` | 风险状态机 | 范围+心理摘要 | `AppRiskTag` | P0 | 随 risk list |
| 多维风险合并 | `/risks/merge-rules` | 同生多风险合并展示规则 | `GET/POST /risk/merge-rules` | — | 学工处配置 | `AppOperationResult` | P1 | 随 risk rules |
| 风险规则配置 | `/risks/rules` | 触发条件、等级、去重 | `GET/POST /risk/rules` | enabled | 学工处 | Excel 导入规则 | P1 | 随 risk list |

## 9. B 包三级页面关联矩阵

| 三级页面 | 上游来源 | 本页面处理 | 下游回流 | 学生画像 | 风险预警 | 学工看板 | 学工统计 | 学工归档 | 现有系统承接 | 是否新开发 | 所属包 | 优先级 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 学工总览 | 各业务聚合 | 指标+钻取 | 待办/统计/审计 | 学生摘要钻取 | 高风险/逾期 | 核心首页 | 指标来源 | 引用 | 迎新/在校服务 partial | 新开发 | B | P0 |
| 今日待办 | 统一待办 | 筛选/跳转 | 各业务处理 | 钻取 | 待处置 | 待办数 | 待办量 | — | 在校服务 partial | 新开发 | B | P0 |
| 辅导员工作台 | 绑定/待办 | 处理/转派 | 待办/审计 | 重点学生 | 跟进 | 我的待办 | 工作量 | 轨迹 | partial | 新开发 | B | P0 |
| 学生风险概览 | 风险聚合 | 分级列表 | 风险列表 | 风险区 | 全部类型 | 风险指标 | 风险统计 D | 风险材料 D | 心理摘要 D | 新开发 | B | P0 |
| 请假审批概览 | 请假待审 | 列表/提醒 | 请假审批 | 请假区 | 请假异常 | 待审数 | 请假率 D | 请假材料 D | 在校服务 partial | 新开发 | B | P0 |
| 宿舍异常概览 | 检查/夜不归宿 | 异常列表 | 宿舍页/风险 | 宿舍区 | 夜不归宿 | 异常数 | 宿舍统计 D | 宿舍材料 D | 报修 partial | 新开发 | B | P0 |
| 重点学生提醒 | 标签/风险/请假 | 提醒/进画像 | 画像/风险 | 标签 | 高风险 | 重点提醒 | 重点人数 D | — | — | 新开发 | B | P0 |
| 学生主档摘要 | 学生主档 | 只读展示 | 跳主档 | 基础区 | — | — | — | — | student 承接 merged | 桥接 | B | P0 |
| 学籍状态摘要 | 教务 | 摘要 | 外链教务 | 学籍区 | — | — | 学籍 D | — | academic 外链 | 摘要 | B | P0 |
| 班级信息 | 班级绑定 | 展示 | 班级详情 | 班级区 | — | 班级筛选 | — | — | 组织主数据 | 新开发 | B | P0 |
| 家庭与联系人摘要 | 主档/家校 | 脱敏展示 | 家校 C | 家庭区 | 经济困难 C | — | — | 联系材料 C | student 承接 | merged | B | P0 |
| 请假记录摘要 | 请假 | 最近记录 | 请假详情 | 请假区 | 请假风险 | 当前请假 | 请假 D | 请假 D | campus-service | 新开发 | B | P0 |
| 宿舍信息摘要 | 床位 | 当前住宿 | 调宿/检查 | 宿舍区 | 夜不归宿 | 宿舍异常 | 宿舍 D | 宿舍 D | dorm 承接 | 新开发 | B | P0 |
| 风险标签 | 风险事件 | 标签展示 | 风险详情 | 风险区 | 核心 | 风险学生 | 风险 D | 风险 D | 心理 D 摘要 | 新开发 | B | P0 |
| 成长时间线 | 各业务 | 时间线 | 归档 | 事件区 | 风险事件 | — | 事件 D | 事件目录 | 各源单 | 新开发 | B | P1 |
| 数据变更日志 | 审计 | 列表/抽屉 | 安全审计 | 审计入口 | — | — | — | 审计 | student 审计 | 新开发 | B | P1 |
| 班级列表~档案入口 | 组织/学生 | 见 §4 | 画像/看板 | 班级入口 | 班级风险 | 班级维度 | 班级统计 D | 班级档案 D | student | 新开发 | B | P0-P2 |
| 宿舍看板~归档入口 | 宿舍台账 | 见 §8.3 | 画像/风险 | 宿舍区 | 夜不归宿 | 宿舍指标 | 宿舍 D | 宿舍 D | campus-service | 新开发 | B | P0-P2 |
| 请假看板~归档入口 | 请假主数据 | 见 §8.3 | 画像/风险 | 请假区 | 请假异常 | 请假指标 | 请假 D | 请假 D | campus-service/miniapp | 新开发 | B | P0-P2 |
| 风险看板~统计摘要 | 多源风险 | 见 §8.3 | 画像/看板 | 风险区 | 核心 | 风险指标 | 风险 D | 风险 D | 实习外链 | 新开发 | B | P0-P2 |
