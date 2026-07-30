# 路由覆盖

> 本文件只记录设计交付覆盖，不取代 `router/index.js`、模块 routes 或 `NAV_PLAN`。

## 统计口径

- 有独立 `component` 且教师/学校管理用户可到达的业务路由
- redirect-only 不计
- 同组件不同业务切面可单独登记
- query/panel/tab 完全同构时允许共用 HTML，但必须逐条映射
- 当前阶段未宣布任何一级中心完成

## 当前覆盖

- manifest 路由/切面条目：**24**
- 独立 HTML：**23**
- 两个真实路由共用一个 HTML：复学学生、转专业学生
- 已完成首轮覆盖工作区：**成绩管理、成绩审核发布更正、学籍管理**
- 已启动但未完成：我的工作台、教务看板

## 已覆盖路由

| 路由 / 业务切面 | routeName | HTML |
|---|---|---|
| `/workbench` | `admin-workbench` | `workbench/my-workbench/index.html` |
| `/admin/academic-affairs` | `aa-dashboard` | `academic-affairs/dashboard/index.html` |
| `/admin/academic-affairs/grade-overview` | `aa-grade-overview` | `academic-affairs/grades/grade-overview.html` |
| `/admin/academic-affairs/grade-entry` | `aa-grade-entry` | `academic-affairs/grades/grade-entry.html` |
| `/admin/academic-affairs/grade-fail` | `aa-grade-fail` | `academic-affairs/grades/grade-fail.html` |
| `/admin/academic-affairs/transcript` | `aa-transcript` | `academic-affairs/grades/transcript.html` |
| `/admin/academic-affairs/grade-exception` | `aa-grade-exception` | `academic-affairs/grades/grade-exception.html` |
| `/admin/academic-affairs/grade-college-review` | `aa-grade-college-review` | `academic-affairs/grades/grade-college-review.html` |
| `/admin/academic-affairs/grade-publish` | `aa-grade-publish` | `academic-affairs/grades/grade-publish.html` |
| `/admin/academic-affairs/grade-change` | `aa-grade-change` | `academic-affairs/grades/grade-change.html` |
| `/admin/academic-affairs/grade-recheck` | `aa-grade-recheck` | `academic-affairs/grades/grade-recheck.html` |
| `/admin/academic-affairs/grade-audit` | `aa-grade-audit` | `academic-affairs/grades/grade-audit.html` |
| `/admin/academic-affairs/grade-recognition` | `aa-grade-recognition` | `academic-affairs/grades/grade-recognition.html` |
| `/admin/academic-affairs/stats?tab=grade` | `aa-stats` | `academic-affairs/grades/grade-stats.html` |
| `/admin/academic-affairs/roster` | `aa-roster` | `academic-affairs/roster/roster-list.html` |
| `/admin/academic-affairs/roster/status` | `aa-roster-status` | `academic-affairs/roster/roster-status.html` |
| `/admin/academic-affairs/roster/changes` | `aa-roster-changes` | `academic-affairs/roster/roster-changes.html` |
| `/admin/academic-affairs/roster/import-export` | `aa-roster-import-export` | `academic-affairs/roster/roster-import-export.html` |
| `/admin/academic-affairs/roster/resumed-students` | `aa-roster-resumed` | `academic-affairs/roster/roster-change-results.html` |
| `/admin/academic-affairs/roster/transferred-major-students` | `aa-roster-transferred-major` | `academic-affairs/roster/roster-change-results.html` |
| `/admin/academic-affairs/roster/corrections` | `aa-roster-corrections` | `academic-affairs/roster/roster-corrections.html` |
| `/admin/academic-affairs/roster/:studentId` | `aa-roster-detail` | `academic-affairs/roster/roster-detail.html` |
| `/admin/academic-affairs/stats?scope=roster&tab=statusChange` | `aa-stats` | `academic-affairs/roster/roster-stats.html` |
| `/admin/academic-affairs/archive?entry=studentStatus` | `aa-archive` | `academic-affairs/roster/roster-archive.html` |

## 共用 HTML 说明

`AaRosterChangeResultListView.vue` 被两个路由复用：

- `meta.changeType=RESUME` → 复学学生
- `meta.changeType=TRANSFER_MAJOR` → 转专业学生

字段、筛选、操作和结构完全相同，仅标题、说明、申请入口和 `changeType` 不同，因此两个路由逐条登记，但共用一个 HTML。

## 已覆盖 query / 状态切面

- 成绩分析：总体、按课程、按班级
- 成绩录入：待录入深链、待办深链、固定三段、动态成绩项、Excel 导入
- 学生成绩单：未选择学生、指定学生、导出
- 教务发布：待终审、已发布、发布确认、退回、归档
- 成绩认定：待审核、已通过、已驳回、代录、附件、通过、驳回
- 学籍名册：关键字与状态分类；休学、退学、保留学籍视图共用名册 HTML
- 学籍信息更正：发起、更正前后对比、敏感字段、通过、驳回
- 学籍档案：脱敏、敏感查看、状态时间线、无权访问
- 学籍归档：草稿、检查中、完整可归档、有缺失、已归档、取消、强制归档、特批解冻

## 代码事实差异记录

当前真实代码存在一个需要后续生产施工单独核实的状态口径差异：

- `navPlan.js` 的“保留学籍”分类入口使用 `status=PRESERVED`
- `AaRosterListView.vue` 的状态字典和分类标题使用 `RETAINED`

本原型库没有修改任何生产代码，只在 manifest 和 HTML 注释中记录该差异；后续必须由业务状态机与后端枚举共同裁定，不能在 UI 原型里擅自修正。

## 未覆盖

- 工作台：待办、审批、消息、领导驾驶舱、帮助中心
- 教务中心：学期校历、组织、注册、专业分流、学籍异动办理、课程、培养方案、教学计划、任务、排课、课表、调停课、考勤、选课、考务、补考重修、预警、毕业审核、教材、资源、评价、质量、完整统计归档等
- 学工中心、岗位实习中心、毕业设计中心、系统管理
- 全局审批、消息、帮助、数据中心、登录、安全和打印页
- 新增学籍原型的截图文件
- 仓库内全部截图二进制提交

详细续工起点见 `PROGRESS.md`。不得把本批次描述为全量完成。
