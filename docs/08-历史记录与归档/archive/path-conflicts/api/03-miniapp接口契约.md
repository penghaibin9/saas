# 03 · miniapp 接口契约

> 文档性质：miniapp（学生端+教师端）逐接口契约（本轮新增，非历史冻结）
> 适用端：学生小程序（`/api/v1/student-mini/*`）、教师移动工作台（`/api/v1/teacher-mobile/*`）
> 依据：共享事实底稿 §2；`miniapp/src/services/studentApi.js`、`teacherApi.js`、`request.js`；`miniapp/src/config/roles.config.js`、`env.js`；`miniapp/src/pages/student/service-apply/index.vue`、`weekly-report/index.vue`；引用历史冻结 `docs/api/00-API契约冻结总册.md`、`04-待办审批消息API.md`、`05-岗位实习API.md`
> 当前阶段声明：miniapp 纯 mock，可运行/可构建/可演示；`ENV.useMock=true`、`apiBaseUrl` 为空、`mockLatency=260ms`；以下"建议后端路径"为契约设计，后端尚未接入
> 生成日期：2026-07-04

---

## 一、当前 mock 机制说明

- 配置来源：`miniapp/src/config/env.js`：
  ```js
  export const ENV = {
    useMock: true,      // 是否使用 mock 数据（当前恒为 true）
    apiBaseUrl: '',     // 预留：真实后端地址
    mockLatency: 260    // mock 模拟网络延迟(ms)
  }
  ```
- 请求封装 `miniapp/src/services/request.js` 提供两个函数：
  - `mockRequest(payload, {latency=260, fail=false})`：用 `Promise` + `setTimeout` 模拟网络，深拷贝 `payload` 后 resolve；`fail=true` 时 reject `{code:'MOCK_ERROR', message:'数据加载失败（模拟）'}`。
  - `request(options)`：预留的真实请求函数，当前 `ENV.useMock=true` 时直接 reject `{code:'MOCK_ONLY', message:'当前为 mock 模式'}`；`ENV.useMock=false` 后走 `uni.request`，`url = ENV.apiBaseUrl + options.url`。
- **与历史冻结统一响应结构的差异**：当前 miniapp mock 层**不做** `{code,message,data,traceId,timestamp}` 包裹，`mockRequest` 直接 resolve 业务数据本身；失败态用 `{code:'MOCK_ERROR'}` 而非统一错误码表。**后端真实接口必须按共享底稿统一响应结构返回**（见 `04-统一响应结构与错误码.md`），前端切换到 `request()` 真实实现时需要在该层补一次响应结构解包（从 `{code,message,data,...}` 中取出 `data` 再返回给页面），不能让页面感知这次结构变化。

## 二、学生端接口契约（studentApi，10 方法）

契约来源：`miniapp/src/services/studentApi.js`。所有方法当前均为 `() => mockRequest(M.xxx)` 无参数调用，未来接入分页/筛选参数以（待后端确认）标注。角色对应共享底稿 STUDENT（数据范围 SELF），学生按钮键包括 service.apply、material.submit、internship.checkin、internship.weekly.submit、leave.apply、employment.report、profile.correct。

### 2.1 首页数据

| 项 | 内容 |
|---|---|
| 接口名称 | 学生首页数据 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/home` |
| 参数 | 无（当前）；（待后端确认）是否需要按学期/日期参数 |
| 返回 | 首页聚合数据（M.studentHome，含待办摘要/学业进度/通知等，具体字段待后端确认） |
| 权限 | 登录态 + dataScope=SELF |
| 数据范围 | SELF |
| 空态 | 各分区显示"暂无数据"占位，不返回裸空对象 |
| 异常 | 网络异常 |
| 错误码 | SERVER_ERROR（mock 现状：`{code:'MOCK_ERROR'}`） |

### 2.2 我的档案

| 项 | 内容 |
|---|---|
| 接口名称 | 学生档案（profile.correct 更正入口对应的只读展示） |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/profile` |
| 参数 | 无 |
| 返回 | 学生基础档案（M.studentProfile，字段建议与历史冻结 `02-学生主档与学生360API.md` 4 getStudentProfile 一致） |
| 权限 | student.profile.view + SELF |
| 数据范围 | SELF |
| 空态 | data=null + DATA_NOT_FOUND |
| 异常 | 档案不存在 |
| 错误码 | DATA_NOT_FOUND |
| 敏感字段 | 身份证号/手机号/家庭住址按脱敏规则展示，完整值查看需二次校验（见 05 文档） |

### 2.3 数字迎新

| 项 | 内容 |
|---|---|
| 接口名称 | 学生迎新信息 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/orientation` |
| 参数 | 无 |
| 返回 | M.studentOrientation（报到清单/预报到状态/报到码等，字段建议对齐历史冻结 `03-数字迎新API.md`） |
| 权限 | SELF |
| 数据范围 | SELF |
| 空态 | 迎新未启用/已结束时返回空态提示（对应共享底稿迎新材料审核流当前 DISABLED 的说明） |
| 异常 | 迎新批次不存在 |
| 错误码 | DATA_NOT_FOUND |

### 2.4 在校服务

| 项 | 内容 |
|---|---|
| 接口名称 | 在校服务分类与条目 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/services` |
| 参数 | 无 |
| 返回 | `{ categories: M.serviceCategories, items: M.serviceItems }` |
| 权限 | SELF |
| 数据范围 | SELF |
| 空态 | `{categories:[],items:[]}` |
| 异常 | 无 |
| 错误码 | 无 |
| 关联写接口 | 见 §四 service-apply 服务申请提交契约（对应按钮键 service.apply / leave.apply） |

### 2.5 学业过程

| 项 | 内容 |
|---|---|
| 接口名称 | 学生学业信息 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/academic` |
| 参数 | 无 |
| 返回 | M.studentAcademic（课程/成绩/预警等，字段待后端确认） |
| 权限 | SELF |
| 数据范围 | SELF |
| 空态 | 空列表 + 提示 |
| 异常 | 无 |
| 错误码 | 无 |

### 2.6 岗位实习

| 项 | 内容 |
|---|---|
| 接口名称 | 学生实习信息 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/internship` |
| 参数 | 无 |
| 返回 | M.studentInternship（对应历史冻结 5.2 我的实习，字段建议一致：status/enterprise/position/schoolTeacher/enterpriseMentor/todayTask/returnedAlert） |
| 权限 | SELF |
| 数据范围 | SELF |
| 空态 | 未分配实习时返回 status=待分配 类占位 |
| 异常 | 无 |
| 错误码 | 无 |
| 关联写接口 | 打卡（internship.checkin）建议对齐历史冻结 5.6 `POST /student-mini/internship/checkins`；周报提交见 §四 weekly-report 契约（对应按钮键 internship.weekly.submit）；请假见历史冻结 5.12 `POST /student-mini/internship/leaves`（对应按钮键 leave.apply） |

### 2.7 毕业设计

| 项 | 内容 |
|---|---|
| 接口名称 | 学生毕设信息 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/graduation` |
| 参数 | 无 |
| 返回 | M.studentGraduation（选题/开题/中期/成果状态，字段待后端确认） |
| 权限 | SELF |
| 数据范围 | SELF |
| 空态 | 尚未选题时返回空态提示 |
| 异常 | 无 |
| 错误码 | 无 |

### 2.8 就业服务

| 项 | 内容 |
|---|---|
| 接口名称 | 学生就业信息 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/employment` |
| 参数 | 无 |
| 返回 | M.studentEmployment（就业状态/材料/去向等，字段待后端确认） |
| 权限 | SELF |
| 数据范围 | SELF |
| 空态 | 空态提示 |
| 异常 | 无 |
| 错误码 | 无 |
| 关联写接口 | employment.report 去向上报（待后端确认建议路径 `POST /api/v1/student-mini/employment/report`） |

### 2.9 我的申请

| 项 | 内容 |
|---|---|
| 接口名称 | 我的申请列表 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/applications` |
| 参数 | 无（待后端确认）是否需要按 tab/状态筛选 |
| 返回 | `{ tabs: M.applicationTabs, list: M.applications }` |
| 权限 | SELF |
| 数据范围 | SELF |
| 空态 | `{tabs:[...固定tab...],list:[]}` |
| 异常 | 无 |
| 错误码 | 无 |

### 2.10 消息

| 项 | 内容 |
|---|---|
| 接口名称 | 学生消息 |
| 适用端 | miniapp 学生端 |
| 方法 | GET |
| 建议路径 | `/api/v1/student-mini/messages`（建议直接复用历史冻结 4.13 消息列表通用接口） |
| 参数 | 无（待后端确认）分页/已读状态筛选 |
| 返回 | `{ tabs: M.studentMessageTabs, groups: M.studentMessages }` |
| 权限 | student-mini.message.view |
| 数据范围 | SELF |
| 空态 | `{tabs:[...],groups:[]}` |
| 异常 | 无 |
| 错误码 | 无 |

---

## 三、教师端接口契约（teacherApi，10 方法）

契约来源：`miniapp/src/services/teacherApi.js`。教师端支持 6 类身份切换（`teacherIdentities` = COUNSELOR辅导员/MENTOR毕设指导教师/INTERN_MENTOR实习指导教师/EMPLOYMENT就业老师/ACADEMIC教务老师/COLLEGE_ADMIN学院管理员），身份切换页面 role-switch 对应共享底稿"身份切换"能力，具体切换接口建议复用历史冻结 1.8（`POST /api/v1/authz/contexts/{contextId}/activate`，教师移动端专属路径 `/api/v1/teacher-mobile/contexts/{id}/activate`）。

### 3.1 工作台（按角色）

| 项 | 内容 |
|---|---|
| 接口名称 | 教师工作台（多身份） |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/workbench?roleKey={counselor\|mentor\|intern_mentor\|employment\|academic\|college_admin}` |
| 参数 | `roleKey`：当前 mock 默认回退 counselor（`M.workbenchByRole[roleKey] || M.workbenchByRole.counselor`），（待后端确认）后端是否应改为服务端按 activeContextId 自动判定而非前端传参 |
| 返回 | 对应角色工作台聚合数据（quickActions/待办摘要/风险提示等，字段待后端确认） |
| 权限 | 登录态 + 当前激活身份对应权限点集合 |
| 数据范围 | 按角色：COUNSELOR=CLASS、MENTOR=MENTEES(本人指导学生12人示例)、INTERN_MENTOR=INTERNS(本人实习学生18人示例)、EMPLOYMENT/ACADEMIC/COLLEGE_ADMIN=COLLEGE |
| 空态 | 各分区空态提示 |
| 异常 | roleKey 不属于当前用户已绑定身份 |
| 错误码 | NO_PERMISSION |

### 3.2 待办列表

| 项 | 内容 |
|---|---|
| 接口名称 | 教师待办列表 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/todos`（建议直接复用历史冻结 4.1 待办列表通用接口） |
| 参数 | （待后端确认）筛选参数，当前 mock 无参数 |
| 返回 | `{ filters: M.todoFilters, list: M.teacherTodos }` |
| 权限 | teacher-mobile.todo.view |
| 数据范围 | 按 activeContextId 对应角色范围 |
| 空态 | `{filters:[...],list:[]}` |
| 异常 | 无 |
| 错误码 | 无 |

### 3.3 审批列表

| 项 | 内容 |
|---|---|
| 接口名称 | 教师审批列表 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/approvals`（建议直接复用历史冻结 4.7 审批列表通用接口） |
| 参数 | 无（当前）；（待后端确认）bizType/status/keyword/page |
| 返回 | M.approvals（列表结构待后端确认，建议对齐历史冻结 `items[]{taskId,instanceId,bizType,bizTitle,studentName,applicantName,currentNode,status,dueTime}`） |
| 权限 | workflow.task.view 对应角色权限（approval.handle 按钮键） |
| 数据范围 | 按角色（COUNSELOR/ACADEMIC/COLLEGE_ADMIN 均含 approval.handle 权限动作） |
| 空态 | 空列表 |
| 异常 | 无 |
| 错误码 | 无 |

### 3.4 风险学生

| 项 | 内容 |
|---|---|
| 接口名称 | 风险学生列表 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/risk-students` |
| 参数 | 无（当前 mock 用 `M.students.filter(s => s.risk==='HIGH' \|\| s.risk==='MEDIUM')` 前端过滤，后端应改为服务端过滤并支持分页） |
| 返回 | 风险学生列表（HIGH/MEDIUM） |
| 权限 | risk.handle 按钮键对应角色（COUNSELOR/COLLEGE_ADMIN） |
| 数据范围 | 按角色（COUNSELOR=CLASS、COLLEGE_ADMIN=COLLEGE） |
| 空态 | `{list:[]}` |
| 异常 | 无 |
| 错误码 | 无 |

### 3.5 学生列表

| 项 | 内容 |
|---|---|
| 接口名称 | 教师可见学生列表 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/students` |
| 参数 | 无（当前）；（待后端确认）分页/关键字 |
| 返回 | M.students 全量（后端应按 dataScope 过滤，不应返回全量） |
| 权限 | student.profile.view + student360.view（按钮键） |
| 数据范围 | 按角色：COUNSELOR=CLASS、MENTOR=MENTEES、INTERN_MENTOR=INTERNS、EMPLOYMENT/ACADEMIC/COLLEGE_ADMIN=COLLEGE |
| 空态 | `{list:[],total:0}` |
| 异常 | 无 |
| 错误码 | 无 |

### 3.6 学生 360

| 项 | 内容 |
|---|---|
| 接口名称 | 学生 360 详情 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/students/{id}/360`（建议直接对齐历史冻结 `02-学生主档与学生360API.md` 3 getStudentDetail） |
| 参数 | 路径参数 `id`；当前 mock `M.student360[id] || null` |
| 返回 | 学生 360 聚合详情 |
| 权限 | student360.view 按钮键（COUNSELOR/MENTOR/EMPLOYMENT 均含此按钮键） |
| 数据范围 | 该学生须归属当前角色数据范围内，越权返回 NO_DATA_SCOPE；**企业导师对毕设成果/家庭/心理/处分字段硬隔离**（对应历史冻结总册 §八），教师移动端非企业导师身份不受此限制但仍按脱敏规则展示敏感字段 |
| 空态 | data=null |
| 异常 | 学生不存在或不在数据范围内 |
| 错误码 | DATA_NOT_FOUND、NO_DATA_SCOPE |
| 审计 | 查看详情写 SENSITIVE_VIEW 审计 |

### 3.7 周报列表（实习指导教师）

| 项 | 内容 |
|---|---|
| 接口名称 | 实习周报列表 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/internship/weekly-reports`（建议对齐历史冻结 5.9 周报列表） |
| 参数 | 无（当前）；（待后端确认）studentId/status/page |
| 返回 | `{ reports: M.weeklyReports, abnormal: M.abnormalCheckins }` |
| 权限 | intern.weekly.review 按钮键（INTERN_MENTOR 专属） |
| 数据范围 | INTERNS（本人指导实习学生） |
| 空态 | `{reports:[],abnormal:[]}` |
| 异常 | 无 |
| 错误码 | 无 |
| 关联写接口 | 周报批阅建议对齐历史冻结 5.11 `POST /teacher-mobile/internship/reports/{id}/review`，body `{action:'APPROVE'|'RETURN', comment, rejectReason?, version, requestId}`，RETURN 时 rejectReason≥5字 |

### 3.8 毕设学生（指导教师）

| 项 | 内容 |
|---|---|
| 接口名称 | 毕设指导学生列表 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/graduation/students` |
| 参数 | 无（当前）；（待后端确认）分页 |
| 返回 | `{ list: M.gdStudents, detail: M.gdReviewDetail }` |
| 权限 | gd.review / gd.return / gd.guidelog 按钮键（MENTOR 专属） |
| 数据范围 | MENTEES（本人指导学生） |
| 空态 | `{list:[],detail:null}` |
| 异常 | 无 |
| 错误码 | 无 |
| 关联写接口 | 开题批阅（对应 PC 端 `reviewProposal`，建议 miniapp 侧 `POST /api/v1/teacher-mobile/graduation/proposals/{id}/review`，REJECT 时 comment≥5字）；指导记录（gd.guidelog 按钮键，待后端确认路径） |

### 3.9 就业跟进（就业老师）

| 项 | 内容 |
|---|---|
| 接口名称 | 就业跟进数据 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/employment` |
| 参数 | 无（当前）；（待后端确认）分页/筛选 |
| 返回 | `{ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool }` |
| 权限 | employment.follow / employment.verify / job.recommend 按钮键（EMPLOYMENT 专属） |
| 数据范围 | COLLEGE |
| 空态 | `{stats:{},tabs:[],list:[],jobs:[]}` |
| 异常 | 无 |
| 错误码 | 无 |

### 3.10 消息

| 项 | 内容 |
|---|---|
| 接口名称 | 教师消息 |
| 适用端 | miniapp 教师端 |
| 方法 | GET |
| 建议路径 | `/api/v1/teacher-mobile/messages`（建议直接复用历史冻结 4.13 消息列表通用接口） |
| 参数 | 无（待后端确认）分页/已读筛选 |
| 返回 | `{ tabs: M.teacherMessageTabs, groups: M.teacherMessages }` |
| 权限 | teacher-mobile.message.view |
| 数据范围 | 按角色 |
| 空态 | `{tabs:[...],groups:[]}` |
| 异常 | 无 |
| 错误码 | 无 |

---

## 四、表单类写接口契约（当前页面直连本地 store，未走 studentApi）

> 重要说明：`service-apply`（服务申请）与 `weekly-report`（实习周报提交）两个页面当前**未经过 `studentApi`**，而是直接调用本地 Pinia store `useSubmissionsStore().addApplication()` / `addWeeklyReport()` 写入内存，无网络请求。以下为后端接入时的**建议契约**，字段来自页面表单实际采集项（`miniapp/src/pages/student/service-apply/index.vue`、`weekly-report/index.vue`）。

### 4.1 服务申请提交（service-apply）

| 项 | 内容 |
|---|---|
| 接口名称 | 服务申请提交 |
| 适用端 | miniapp 学生端 |
| 方法 | POST |
| 建议路径 | `/api/v1/student-mini/services/applications` |
| 请求参数 | `{ svcName: string（服务名称，由入口页传入）, dept: string（承办部门）, needApprove: boolean（是否需审批）, applyType: string（申请类型，来自 typeOptions，如"事假/病假/公假/其他"或"国家励志奖学金/国家助学金/校级奖学金/临时困难补助"等，按 svcName 动态取值集）, startDate: string(YYYY-MM-DD), endDate: string(YYYY-MM-DD), reason: string（申请事由，页面前端已校验必填，最长 200 字）, fileId?: string（附件，可选，经文件中心两步上传后获得，见 07 文档）, requestId: string（幂等键） }` |
| 返回字段 | `{ applicationId, status: 'PENDING_REVIEW'|'AUTO_APPROVED', createdAt }`（`needApprove=false` 时可直接终态） |
| 权限要求 | SELF + service.apply 按钮键（部分申请类型对应 leave.apply） |
| 数据范围要求 | SELF |
| 空状态 | 不适用（写操作） |
| 异常状态 | reason 为空（页面已拦截，服务端仍须二次校验）；重复提交（同 requestId） |
| 错误码 | VALIDATION_ERROR、IDEMPOTENCY_CONFLICT（对应共享底稿 APPROVAL_VERSION_CONFLICT 类语义，具体码待后端确认） |
| 备注 | `needApprove=true` 时应触发历史冻结 04 审批流通用能力，生成 `t_workflow_task` + 教师端待办；提交后学生"我的申请"（2.9 getApplications）应能查到新记录 |

### 4.2 实习周报提交（weekly-report）

| 项 | 内容 |
|---|---|
| 接口名称 | 实习周报提交 |
| 适用端 | miniapp 学生端 |
| 方法 | POST |
| 建议路径 | `/api/v1/student-mini/internship/reports`（与历史冻结 5.10 周报提交 `POST /student-pc/internship/reports` 为同一业务能力在不同端的入口，建议后端合并同一张表 `t_intern_report`，仅路径前缀区分端） |
| 请求参数 | `{ week: string（周次标识，由入口页传入，如"第4周"）, company: string（实习企业，只读展示字段，由后端按当前实习分配带出，不应由前端可编辑提交）, post: string（实习岗位，同上）, tasks: string（本周工作内容，必填，最长 500 字）, gain: string（本周收获，必填，最长 500 字）, problem?: string（存在问题/下周计划，可选，最长 500 字）, hours?: number（本周工时）, attachmentFileIds?: string[], clientDraftId: string（草稿去重键，对应"存草稿"按钮）, requestId: string（幂等键） }` |
| 返回字段 | `{ reportId, status: 'SUBMITTED', submittedAt }` |
| 权限要求 | SELF + internship.weekly.submit 按钮键 |
| 数据范围要求 | SELF，且须为该学生当前实习分配下的周报 |
| 空状态 | 不适用（写操作） |
| 异常状态 | tasks 或 gain 为空（页面已拦截"请填写本周工作内容与收获"，服务端须二次校验）；逾期未交（页面提示"逾期未交会计入实习考核"，具体逾期判定逻辑待后端确认） |
| 错误码 | VALIDATION_ERROR |
| 备注 | "存草稿"按钮当前仅前端 toast 提示（"已存草稿（演示）"），未真正持久化；后端实现时建议增加 `PUT /api/v1/student-mini/internship/reports/draft`（body 同上，`clientDraftId` 幂等），支持弱网草稿保存，对齐历史冻结总册一期优先级 P4"弱网草稿"规划 |
| 关联审批 | 提交后应生成教师端周报批阅待办（对应 3.7 教师端周报列表 + 历史冻结 5.11 周报批阅），RETURN 时学生端应能在"我的申请"或专门的"退回提醒"处看到 rejectReason |

---

## 五、miniapp 全局约定小结

- 所有以上接口的统一响应结构、错误码、分页结构，切换到真实后端后必须遵循共享底稿统一口径（详见 `04-统一响应结构与错误码.md`），当前 mock 层的 `{code:'MOCK_ERROR'}` 仅为演示态失败标记，不是最终错误码规范。
- 角色与数据范围来自 `config/roles.config.js` 的 `roleConfigs`，切换真实后端后 `dataScope`/`dataScopeText` 应改为服务端下发（当前为前端硬编码占位文案，如"软件工程 2401 班""信息工程学院"，均为演示数据，非真实组织结构）。
- 品牌配置来自 `config/brand.config.js` 的 `tenantBrandConfig`（platformName「高校学生全生命周期管理平台」，schoolName「示范高校」占位，主色 #2563EB），真实接入后应对齐历史冻结 1.5 当前租户品牌接口 `GET /api/v1/authz/tenant/brand`。
- 教师端多身份切换当前由前端 `teacherIdentities` 数组驱动页面选择，真实接入后应对齐历史冻结 1.6/1.8（我的身份列表 + 切换身份），不应由前端自行维护身份集合。
