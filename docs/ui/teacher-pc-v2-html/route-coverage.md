# 路由覆盖

> 本文件只记录设计交付覆盖，不取代 `router/index.js`、模块 routes 或 `NAV_PLAN`。

## 统计口径

- 有独立 `component` 且教师/学校管理用户可到达的业务路由
- redirect-only 不计
- 同组件不同业务切面可单独登记
- query/panel/tab 完全同构时允许共用 HTML，但必须逐条映射
- 当前阶段未宣布任何中心完成

## 已覆盖

| 路由 | routeName | 源组件 | HTML | 状态 |
|---|---|---|---|---|
| `/workbench` | `admin-workbench` | `WorkbenchView.vue` | `workbench/my-workbench/index.html` | 已生成 |
| `/admin/academic-affairs` | `aa-dashboard` | `AaDashboardView.vue` | `academic-affairs/dashboard/index.html` | 已生成 |
| `/admin/academic-affairs/grade-overview` | `aa-grade-overview` | `AaGradeOverviewView.vue` | `academic-affairs/grades/grade-overview.html` | 已生成 |
| `/admin/academic-affairs/grade-entry` | `aa-grade-entry` | `AaGradeEntryView.vue` | `academic-affairs/grades/grade-entry.html` | 已生成 |
| `/admin/academic-affairs/grade-fail` | `aa-grade-fail` | `AaGradeFailListView.vue` | `academic-affairs/grades/grade-fail.html` | 已生成 |

## 已覆盖 query 切面

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

## 未覆盖

当前仍有大量真实路由未覆盖，详见 `PROGRESS.md`。不得把本批次描述为全量完成。

## 直接代码依据

- `frontend/src/router/index.js`
- `frontend/src/modules/academicAffairs/academic-affairs.routes.js`
- `frontend/src/modules/workbench/views/WorkbenchView.vue`
- `frontend/src/modules/academicAffairs/views/AaDashboardView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeOverviewView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue`
- `frontend/src/modules/academicAffairs/views/AaGradeFailListView.vue`
