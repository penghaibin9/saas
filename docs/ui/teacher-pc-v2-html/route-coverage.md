# 路由覆盖

> 本文件只记录设计交付覆盖，不取代 `router/index.js`、模块 routes 或 `NAV_PLAN`。

## 统计口径

- 有独立 `component` 且教师/学校管理用户可到达的业务路由
- redirect-only 不计
- 同组件不同业务切面可单独登记
- query/panel/tab 完全同构时允许共用 HTML，但必须逐条映射
- 当前阶段未宣布任何一级中心完成

## 已覆盖（14）

| 路由 / 业务切面 | routeName | 源组件 | HTML |
|---|---|---|---|
| `/workbench` | `admin-workbench` | `WorkbenchView.vue` | `workbench/my-workbench/index.html` |
| `/admin/academic-affairs` | `aa-dashboard` | `AaDashboardView.vue` | `academic-affairs/dashboard/index.html` |
| `/admin/academic-affairs/grade-overview` | `aa-grade-overview` | `AaGradeOverviewView.vue` | `academic-affairs/grades/grade-overview.html` |
| `/admin/academic-affairs/grade-entry` | `aa-grade-entry` | `AaGradeEntryView.vue` | `academic-affairs/grades/grade-entry.html` |
| `/admin/academic-affairs/grade-fail` | `aa-grade-fail` | `AaGradeFailListView.vue` | `academic-affairs/grades/grade-fail.html` |
| `/admin/academic-affairs/transcript` | `aa-transcript` | `AaTranscriptView.vue` | `academic-affairs/grades/transcript.html` |
| `/admin/academic-affairs/grade-exception` | `aa-grade-exception` | `AaGradeExceptionView.vue` | `academic-affairs/grades/grade-exception.html` |
| `/admin/academic-affairs/grade-college-review` | `aa-grade-college-review` | `AaGradeCollegeReviewView.vue` | `academic-affairs/grades/grade-college-review.html` |
| `/admin/academic-affairs/grade-publish` | `aa-grade-publish` | `AaGradePublishView.vue` | `academic-affairs/grades/grade-publish.html` |
| `/admin/academic-affairs/grade-change` | `aa-grade-change` | `AaGradeChangeView.vue` | `academic-affairs/grades/grade-change.html` |
| `/admin/academic-affairs/grade-recheck` | `aa-grade-recheck` | `AaGradeRecheckView.vue` | `academic-affairs/grades/grade-recheck.html` |
| `/admin/academic-affairs/grade-audit` | `aa-grade-audit` | `AaGradeAuditView.vue` | `academic-affairs/grades/grade-audit.html` |
| `/admin/academic-affairs/grade-recognition` | `aa-grade-recognition` | `AaGradeRecognitionView.vue` | `academic-affairs/grades/grade-recognition.html` |
| `/admin/academic-affairs/stats?tab=grade` | `aa-stats` | `AaStatsOverviewView.vue` | `academic-affairs/grades/grade-stats.html` |

## 已覆盖 query / 状态切面

### 成绩分析

- 总体
- 按课程
- 按班级

### 成绩录入

- `filter=pending`
- `todoType=AA_GRADE_ENTRY`
- `taskId=:gradeTaskId`
- `taskId=:gradeTaskId&mode=dynamic`
- `taskId=:gradeTaskId&action=import`

### 学生成绩单

- 未选择学生
- `studentId=:studentId&name=:studentName`
- `action=export`

### 教务发布

- 待终审
- 已发布（可归档）
- 发布高危确认
- 退回原因

### 成绩认定

- 待审核
- 已通过
- 已驳回
- 代录申请
- 通过确认
- 驳回原因

### 成绩统计

- `/admin/academic-affairs/stats?tab=grade`
- 数据范围阻断
- 挂科学生明细下钻

## 本批次工作区结论

- `成绩管理`：首轮覆盖完成
- `成绩审核发布更正`：首轮覆盖完成
- `我的工作台`：仅工作台首页已生成，工作台中心未完成
- `教务看板`：仅中心首页已生成，教务中心未完成

## 未覆盖

仍未覆盖的主要范围：

- 工作台的待办、审批、消息、领导驾驶舱和帮助中心页面
- 教务中心除看板和成绩工作区外的学期、学籍、注册、课程、培养方案、任务、排课、考务、预警、质量、资源、毕业审核、统计归档等路由
- 学工中心、岗位实习中心、毕业设计中心、系统管理
- 全局审批、消息、帮助、数据中心、登录、安全和打印页
- 仓库内截图文件提交

详细续工起点见 `PROGRESS.md`。不得把本批次描述为全量完成。

## 直接代码依据

- `frontend/src/router/index.js`
- `frontend/src/config/navPlan.js`
- `frontend/src/modules/academicAffairs/academic-affairs.routes.js`
- `frontend/src/modules/workbench/views/WorkbenchView.vue`
- `frontend/src/modules/academicAffairs/views/AaDashboardView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeOverviewView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeFailListView.vue`
- `frontend/src/modules/academicAffairs/views/AaTranscriptView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeExceptionView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeCollegeReviewView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradePublishView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeChangeView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeRecheckView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeAuditView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeRecognitionView.vue`
- `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue`
