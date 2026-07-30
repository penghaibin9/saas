# 路由覆盖

> 本文件是设计交付清单，不取代 `router/index.js`、模块 routes、`navPlan.js` 或权限事实源。

## 当前统计

- manifest 条目：**82**
- 独立 HTML：**76**
- 共享 HTML 路由条目：**8**
- 仓库截图：**0**
- 本地累计渲染截图：**118**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次
- 一级中心完成：**0**

## 覆盖明细

### 我的工作台

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/workbench` | `admin-workbench` | `workbench/my-workbench/index.html` | COMPLETE |

### 教务看板

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs` | `aa-dashboard` | `academic-affairs/dashboard/index.html` | COMPLETE |

### 成绩管理

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/grade-overview` | `aa-grade-overview` | `academic-affairs/grades/grade-overview.html` | COMPLETE |
| `/admin/academic-affairs/grade-entry` | `aa-grade-entry` | `academic-affairs/grades/grade-entry.html` | COMPLETE |
| `/admin/academic-affairs/grade-fail` | `aa-grade-fail` | `academic-affairs/grades/grade-fail.html` | COMPLETE |
| `/admin/academic-affairs/transcript` | `aa-transcript` | `academic-affairs/grades/transcript.html` | COMPLETE |
| `/admin/academic-affairs/grade-exception` | `aa-grade-exception` | `academic-affairs/grades/grade-exception.html` | COMPLETE |
| `/admin/academic-affairs/grade-recognition` | `aa-grade-recognition` | `academic-affairs/grades/grade-recognition.html` | COMPLETE |
| `/admin/academic-affairs/stats?tab=grade` | `aa-stats` | `academic-affairs/grades/grade-stats.html` | COMPLETE |

### 成绩审核发布更正

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/grade-college-review` | `aa-grade-college-review` | `academic-affairs/grades/grade-college-review.html` | COMPLETE |
| `/admin/academic-affairs/grade-publish` | `aa-grade-publish` | `academic-affairs/grades/grade-publish.html` | COMPLETE |
| `/admin/academic-affairs/grade-change` | `aa-grade-change` | `academic-affairs/grades/grade-change.html` | COMPLETE |
| `/admin/academic-affairs/grade-recheck` | `aa-grade-recheck` | `academic-affairs/grades/grade-recheck.html` | COMPLETE |
| `/admin/academic-affairs/grade-audit` | `aa-grade-audit` | `academic-affairs/grades/grade-audit.html` | COMPLETE |

### 学籍管理

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/roster` | `aa-roster` | `academic-affairs/roster/roster-list.html` | COMPLETE |
| `/admin/academic-affairs/roster/status` | `aa-roster-status` | `academic-affairs/roster/roster-status.html` | COMPLETE |
| `/admin/academic-affairs/roster/changes` | `aa-roster-changes` | `academic-affairs/roster/roster-changes.html` | COMPLETE |
| `/admin/academic-affairs/roster/import-export` | `aa-roster-import-export` | `academic-affairs/roster/roster-import-export.html` | COMPLETE |
| `/admin/academic-affairs/roster/resumed-students` | `aa-roster-resumed` | `academic-affairs/roster/roster-change-results.html` | COMPLETE |
| `/admin/academic-affairs/roster/transferred-major-students` | `aa-roster-transferred-major` | `academic-affairs/roster/roster-change-results.html` | COMPLETE |
| `/admin/academic-affairs/roster/corrections` | `aa-roster-corrections` | `academic-affairs/roster/roster-corrections.html` | COMPLETE |
| `/admin/academic-affairs/roster/:studentId` | `aa-roster-detail` | `academic-affairs/roster/roster-detail.html` | COMPLETE |
| `/admin/academic-affairs/stats?scope=roster&tab=statusChange` | `aa-stats` | `academic-affairs/roster/roster-stats.html` | COMPLETE |
| `/admin/academic-affairs/archive?entry=studentStatus` | `aa-archive` | `academic-affairs/roster/roster-archive.html` | COMPLETE |

### 注册管理

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/registration` | `aa-registration` | `academic-affairs/registration/registration-batches.html` | COMPLETE |
| `/admin/academic-affairs/registration?type=ENROLL` | `aa-registration` | `academic-affairs/registration/registration-enroll.html` | COMPLETE |
| `/admin/academic-affairs/registration?type=ANNUAL` | `aa-registration` | `academic-affairs/registration/registration-annual.html` | COMPLETE |
| `/admin/academic-affairs/registration?type=SEMESTER` | `aa-registration` | `academic-affairs/registration/registration-semester.html` | COMPLETE |
| `/admin/academic-affairs/registration/:batchId` | `aa-registration-detail` | `academic-affairs/registration/registration-detail.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=eligibility` | `aa-registration-workbench` | `academic-affairs/registration/registration-eligibility.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=unregistered` | `aa-registration-workbench` | `academic-affairs/registration/registration-unregistered.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=deferral` | `aa-registration-workbench` | `academic-affairs/registration/registration-deferral.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=exception` | `aa-registration-workbench` | `academic-affairs/registration/registration-exception.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=archive` | `aa-registration-workbench` | `academic-affairs/registration/registration-archive.html` | COMPLETE |
| `/admin/academic-affairs/stats?tab=registration` | `aa-stats` | `academic-affairs/registration/registration-stats.html` | COMPLETE |

### 学籍异动办理

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/status-changes` | `aa-status-changes` | `academic-affairs/status-changes/status-change-ledger.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/new` | `aa-status-change-new` | `academic-affairs/status-changes/status-change-form.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/new?type=TRANSFER_MAJOR` | `aa-status-change-new` | `academic-affairs/status-changes/status-change-form-transfer-major.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/new?type=TRANSFER_CLASS` | `aa-status-change-new` | `academic-affairs/status-changes/status-change-form-transfer-class.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/suspend` | `aa-status-change-suspend` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/resume` | `aa-status-change-resume` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/withdraw` | `aa-status-change-withdraw` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/transfer-major` | `aa-status-change-transfer-major` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/transfer-class` | `aa-status-change-transfer-class` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/preserve` | `aa-status-change-preserve` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/approval` | `aa-status-change-approval` | `academic-affairs/status-changes/status-change-approval.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/effective` | `aa-status-change-effective` | `academic-affairs/status-changes/status-change-effective.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/stats` | `aa-status-change-stats` | `academic-affairs/status-changes/status-change-stats.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/archive` | `aa-status-change-archive` | `academic-affairs/status-changes/status-change-archive.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/:id` | `aa-status-change-detail` | `academic-affairs/status-changes/status-change-detail.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/:id (status=EFFECTIVE)` | `aa-status-change-detail` | `academic-affairs/status-changes/status-change-detail-effective.html` | COMPLETE |
| `/admin/academic-affairs/print/status-change/:id` | `aa-print-status-change` | `academic-affairs/status-changes/status-change-print.html` | COMPLETE |

### 学院专业班级

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/orgs` | `aa-orgs` | `academic-affairs/orgs/org-college.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=major` | `aa-orgs` | `academic-affairs/orgs/org-major.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=class` | `aa-orgs` | `academic-affairs/orgs/org-class.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=grade` | `aa-orgs` | `academic-affairs/orgs/org-grade.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=teaching` | `aa-orgs` | `academic-affairs/orgs/org-teaching.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=direction` | `aa-orgs` | `academic-affairs/orgs/org-direction.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=students` | `aa-orgs` | `academic-affairs/orgs/org-students.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=adjust` | `aa-orgs` | `academic-affairs/orgs/org-adjust.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=tree` | `aa-orgs` | `academic-affairs/orgs/org-tree.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=stats` | `aa-orgs` | `academic-affairs/orgs/org-stats.html` | COMPLETE |
| `/admin/academic-affairs/orgs?tab=audit` | `aa-orgs` | `academic-affairs/orgs/org-audit.html` | COMPLETE |

### 学年学期

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/terms` | `aa-terms` | `academic-affairs/terms-calendar/term-list.html` | COMPLETE |
| `/admin/academic-affairs/terms/new` | `aa-term-new` | `academic-affairs/terms-calendar/term-new.html` | COMPLETE |
| `/admin/academic-affairs/terms/years` | `aa-term-years` | `academic-affairs/terms-calendar/term-years.html` | COMPLETE |
| `/admin/academic-affairs/terms/current` | `aa-term-current` | `academic-affairs/terms-calendar/term-current.html` | COMPLETE |
| `/admin/academic-affairs/terms/weeks` | `aa-term-weeks` | `academic-affairs/terms-calendar/term-weeks.html` | COMPLETE |
| `/admin/academic-affairs/terms/teaching-weeks` | `aa-term-teaching-weeks` | `academic-affairs/terms-calendar/term-teaching-weeks.html` | COMPLETE |
| `/admin/academic-affairs/terms/teaching-weeks (status=PUBLISHED)` | `aa-term-teaching-weeks` | `academic-affairs/terms-calendar/term-teaching-weeks-locked.html` | COMPLETE |
| `/admin/academic-affairs/terms/status` | `aa-term-status` | `academic-affairs/terms-calendar/term-status.html` | COMPLETE |
| `/admin/academic-affairs/terms/switch-log` | `aa-term-switch-log` | `academic-affairs/terms-calendar/term-switch-log.html` | COMPLETE |
| `/admin/academic-affairs/terms/archive-status` | `aa-term-archive-status` | `academic-affairs/terms-calendar/term-archive.html` | COMPLETE |

### 校历节次

| 路由 / 业务切面 | routeName | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/calendar` | `aa-calendar` | `academic-affairs/terms-calendar/calendar-events.html` | COMPLETE |
| `/admin/academic-affairs/calendar (status=PUBLISHED)` | `aa-calendar` | `academic-affairs/terms-calendar/calendar-events-locked.html` | COMPLETE |
| `/admin/academic-affairs/calendar?tab=holiday` | `aa-calendar` | `academic-affairs/terms-calendar/calendar-holiday.html` | COMPLETE |
| `/admin/academic-affairs/calendar?tab=makeup` | `aa-calendar` | `academic-affairs/terms-calendar/calendar-makeup.html` | COMPLETE |
| `/admin/academic-affairs/calendar?tab=weekCalendar` | `aa-calendar` | `academic-affairs/terms-calendar/calendar-week.html` | COMPLETE |
| `/admin/academic-affairs/calendar?tab=publish` | `aa-calendar` | `academic-affairs/terms-calendar/calendar-publish.html` | COMPLETE |
| `/admin/academic-affairs/calendar?tab=archive` | `aa-calendar` | `academic-affairs/terms-calendar/calendar-archive.html` | COMPLETE |
| `/admin/academic-affairs/time-slots` | `aa-time-slots` | `academic-affairs/terms-calendar/time-slots.html` | COMPLETE |
| `/admin/academic-affairs/time-slots?tab=bands` | `aa-time-slots` | `academic-affairs/terms-calendar/time-bands.html` | COMPLETE |

## 重要状态切面说明

1. `/admin/academic-affairs/terms/teaching-weeks (status=PUBLISHED)` 与默认教学周配置为同一路由的不同业务状态；非 `DRAFT` 时结构性配置锁定，因此独立 HTML、独立 manifest 记录。
2. `/admin/academic-affairs/calendar (status=PUBLISHED)` 与默认校历管理为同一路由的不同业务状态；发布后事件不可增删改，因此独立 HTML、独立 manifest 记录。
3. `AaCalendarView.vue` 的 `holiday`、`makeup`、`weekCalendar`、`publish`、`archive` 是真实 query Tab，均单独登记。
4. `AaTimeSlotView.vue` 的 `periods` 与 `bands` 字段、表格和 CRUD 结构明显不同，分别生成节次管理和上课时间段原型。

## 已确认差异与疑问

1. `navPlan.js` 的学籍名册“保留学籍”历史入口仍出现 `status=PRESERVED`，`AaRosterListView.vue` 分类过滤使用 `RETAINED`；原型继续按真实页面行为呈现并保留差异，不修改生产代码。
2. 学籍异动真实类型同时存在 `PRESERVE`（保留学籍）与 `RETAIN`（留级），二者业务含义、审批节点和主档结果不同；原型禁止合并。
3. `/status-changes/retain` 是 redirect-only，按排除规则不生成独立 HTML，只记录其重定向到 `aa-status-change-preserve`。
4. 异动归档页面明确说明当前 `term_code` 无可靠写入口回填，因此不虚构学期筛选。
5. 学期列表真实代码仍保留“学期编辑/冻结/归档为后续波次”旧说明，但冻结、解冻与归档总览已由独立真实路由承载；原型以当前可达路由行为为准，不修改生产文案。
6. 校历归档与学期归档页均只读跳转教务归档，不在原型中虚构绕过归档批次和 9 数据域完整性检查的直接归档按钮。

## 尚未覆盖

- 教务中心：专业分流、课程库、培养方案、教学任务、课表、选课、考务、补考重修、预警、毕业审核、教材、教学资源、评价、质量、统计归档其余切面。
- 工作台其余页面及全局审批、消息、帮助、数据中心。
- 学工中心、岗位实习中心、毕业设计中心、系统管理。
- 登录、安全、其余打印/导出预览。

未覆盖项不得描述为完成。
