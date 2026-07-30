# 路由覆盖

> 本文件是设计交付清单，不取代 `router/index.js`、模块 routes、`navPlan.js` 或权限事实源。

## 当前统计

- manifest 条目：**52**
- 独立 HTML：**46**
- 共享 HTML 路由条目：**8**
- 仓库截图：**0**
- 本地累计渲染截图：**64**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理
- 一级中心完成：**0**

## 覆盖明细

### 我的工作台

| 路由 / 切面 | routeName | 源组件 | HTML | 状态 |
|---|---|---|---|---|
| `/workbench` | `admin-workbench` | `WorkbenchView.vue` | `workbench/my-workbench/index.html` | COMPLETE |

### 教务看板

| 路由 / 切面 | routeName | 源组件 | HTML | 状态 |
|---|---|---|---|---|
| `/admin/academic-affairs` | `aa-dashboard` | `AaDashboardView.vue` | `academic-affairs/dashboard/index.html` | COMPLETE |

### 成绩管理

| 路由 / 切面 | routeName | 源组件 | HTML | 状态 |
|---|---|---|---|---|
| `/admin/academic-affairs/grade-overview` | `aa-grade-overview` | `AaGradeOverviewView.vue` | `academic-affairs/grades/grade-overview.html` | COMPLETE |
| `/admin/academic-affairs/grade-entry` | `aa-grade-entry` | `AaGradeEntryView.vue` | `academic-affairs/grades/grade-entry.html` | COMPLETE |
| `/admin/academic-affairs/grade-fail` | `aa-grade-fail` | `AaGradeFailListView.vue` | `academic-affairs/grades/grade-fail.html` | COMPLETE |
| `/admin/academic-affairs/transcript` | `aa-transcript` | `AaTranscriptView.vue` | `academic-affairs/grades/transcript.html` | COMPLETE |
| `/admin/academic-affairs/grade-exception` | `aa-grade-exception` | `AaGradeExceptionView.vue` | `academic-affairs/grades/grade-exception.html` | COMPLETE |
| `/admin/academic-affairs/grade-recognition` | `aa-grade-recognition` | `AaGradeRecognitionView.vue` | `academic-affairs/grades/grade-recognition.html` | COMPLETE |
| `/admin/academic-affairs/stats?tab=grade` | `aa-stats` | `AaStatsOverviewView.vue` | `academic-affairs/grades/grade-stats.html` | COMPLETE |

### 成绩审核发布更正

| 路由 / 切面 | routeName | 源组件 | HTML | 状态 |
|---|---|---|---|---|
| `/admin/academic-affairs/grade-college-review` | `aa-grade-college-review` | `AaGradeCollegeReviewView.vue` | `academic-affairs/grades/grade-college-review.html` | COMPLETE |
| `/admin/academic-affairs/grade-publish` | `aa-grade-publish` | `AaGradePublishView.vue` | `academic-affairs/grades/grade-publish.html` | COMPLETE |
| `/admin/academic-affairs/grade-change` | `aa-grade-change` | `AaGradeChangeView.vue` | `academic-affairs/grades/grade-change.html` | COMPLETE |
| `/admin/academic-affairs/grade-recheck` | `aa-grade-recheck` | `AaGradeRecheckView.vue` | `academic-affairs/grades/grade-recheck.html` | COMPLETE |
| `/admin/academic-affairs/grade-audit` | `aa-grade-audit` | `AaGradeAuditView.vue` | `academic-affairs/grades/grade-audit.html` | COMPLETE |

### 学籍管理

| 路由 / 切面 | routeName | 源组件 | HTML | 状态 |
|---|---|---|---|---|
| `/admin/academic-affairs/roster` | `aa-roster` | `AaRosterListView.vue` | `academic-affairs/roster/roster-list.html` | COMPLETE |
| `/admin/academic-affairs/roster/status` | `aa-roster-status` | `AaRosterStatusView.vue` | `academic-affairs/roster/roster-status.html` | COMPLETE |
| `/admin/academic-affairs/roster/changes` | `aa-roster-changes` | `AaRosterChangeRecordsView.vue` | `academic-affairs/roster/roster-changes.html` | COMPLETE |
| `/admin/academic-affairs/roster/import-export` | `aa-roster-import-export` | `AaRosterImportExportView.vue` | `academic-affairs/roster/roster-import-export.html` | COMPLETE |
| `/admin/academic-affairs/roster/resumed-students` | `aa-roster-resumed` | `AaRosterChangeResultListView.vue` | `academic-affairs/roster/roster-change-results.html` | COMPLETE |
| `/admin/academic-affairs/roster/transferred-major-students` | `aa-roster-transferred-major` | `AaRosterChangeResultListView.vue` | `academic-affairs/roster/roster-change-results.html` | COMPLETE |
| `/admin/academic-affairs/roster/corrections` | `aa-roster-corrections` | `AaRosterCorrectionListView.vue` | `academic-affairs/roster/roster-corrections.html` | COMPLETE |
| `/admin/academic-affairs/roster/:studentId` | `aa-roster-detail` | `AaRosterDetailView.vue` | `academic-affairs/roster/roster-detail.html` | COMPLETE |
| `/admin/academic-affairs/stats?scope=roster&tab=statusChange` | `aa-stats` | `AaStatsOverviewView.vue` | `academic-affairs/roster/roster-stats.html` | COMPLETE |
| `/admin/academic-affairs/archive?entry=studentStatus` | `aa-archive` | `AaArchiveConsoleView.vue` | `academic-affairs/roster/roster-archive.html` | COMPLETE |

### 注册管理

| 路由 / 切面 | routeName | 源组件 | HTML | 状态 |
|---|---|---|---|---|
| `/admin/academic-affairs/registration` | `aa-registration` | `AaRegistrationBatchListView.vue` | `academic-affairs/registration/registration-batches.html` | COMPLETE |
| `/admin/academic-affairs/registration?type=ENROLL` | `aa-registration` | `AaRegistrationBatchListView.vue` | `academic-affairs/registration/registration-enroll.html` | COMPLETE |
| `/admin/academic-affairs/registration?type=ANNUAL` | `aa-registration` | `AaRegistrationBatchListView.vue` | `academic-affairs/registration/registration-annual.html` | COMPLETE |
| `/admin/academic-affairs/registration?type=SEMESTER` | `aa-registration` | `AaRegistrationBatchListView.vue` | `academic-affairs/registration/registration-semester.html` | COMPLETE |
| `/admin/academic-affairs/registration/:batchId` | `aa-registration-detail` | `AaRegistrationDetailView.vue` | `academic-affairs/registration/registration-detail.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=eligibility` | `aa-registration-workbench` | `AaRegistrationWorkbenchView.vue` | `academic-affairs/registration/registration-eligibility.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=unregistered` | `aa-registration-workbench` | `AaRegistrationWorkbenchView.vue` | `academic-affairs/registration/registration-unregistered.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=deferral` | `aa-registration-workbench` | `AaRegistrationWorkbenchView.vue` | `academic-affairs/registration/registration-deferral.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=exception` | `aa-registration-workbench` | `AaRegistrationWorkbenchView.vue` | `academic-affairs/registration/registration-exception.html` | COMPLETE |
| `/admin/academic-affairs/registration/workbench?tab=archive` | `aa-registration-workbench` | `AaRegistrationWorkbenchView.vue` | `academic-affairs/registration/registration-archive.html` | COMPLETE |
| `/admin/academic-affairs/stats?tab=registration` | `aa-stats` | `AaStatsOverviewView.vue` | `academic-affairs/registration/registration-stats.html` | COMPLETE |

### 学籍异动办理

| 路由 / 切面 | routeName | 源组件 | HTML | 状态 |
|---|---|---|---|---|
| `/admin/academic-affairs/status-changes` | `aa-status-changes` | `AaStatusChangeListView.vue` | `academic-affairs/status-changes/status-change-ledger.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/new` | `aa-status-change-new` | `AaStatusChangeFormView.vue` | `academic-affairs/status-changes/status-change-form.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/new?type=TRANSFER_MAJOR` | `aa-status-change-new` | `AaStatusChangeFormView.vue` | `academic-affairs/status-changes/status-change-form-transfer-major.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/new?type=TRANSFER_CLASS` | `aa-status-change-new` | `AaStatusChangeFormView.vue` | `academic-affairs/status-changes/status-change-form-transfer-class.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/suspend` | `aa-status-change-suspend` | `AaStatusChangeTypedListView.vue` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/resume` | `aa-status-change-resume` | `AaStatusChangeTypedListView.vue` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/withdraw` | `aa-status-change-withdraw` | `AaStatusChangeTypedListView.vue` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/transfer-major` | `aa-status-change-transfer-major` | `AaStatusChangeTypedListView.vue` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/transfer-class` | `aa-status-change-transfer-class` | `AaStatusChangeTypedListView.vue` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/preserve` | `aa-status-change-preserve` | `AaStatusChangeTypedListView.vue` | `academic-affairs/status-changes/status-change-typed-list.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/approval` | `aa-status-change-approval` | `AaStatusChangeApprovalView.vue` | `academic-affairs/status-changes/status-change-approval.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/effective` | `aa-status-change-effective` | `AaStatusChangeEffectiveView.vue` | `academic-affairs/status-changes/status-change-effective.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/stats` | `aa-status-change-stats` | `AaStatusChangeStatsView.vue` | `academic-affairs/status-changes/status-change-stats.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/archive` | `aa-status-change-archive` | `AaStatusChangeArchiveView.vue` | `academic-affairs/status-changes/status-change-archive.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/:id` | `aa-status-change-detail` | `AaStatusChangeDetailView.vue` | `academic-affairs/status-changes/status-change-detail.html` | COMPLETE |
| `/admin/academic-affairs/status-changes/:id (status=EFFECTIVE)` | `aa-status-change-detail` | `AaStatusChangeDetailView.vue` | `academic-affairs/status-changes/status-change-detail-effective.html` | COMPLETE |
| `/admin/academic-affairs/print/status-change/:id` | `aa-print-status-change` | `AaStatusChangePrintView.vue` | `academic-affairs/status-changes/status-change-print.html` | COMPLETE |

## 已确认差异与疑问

1. `navPlan.js` 的学籍名册“保留学籍”历史入口仍出现 `status=PRESERVED`，`AaRosterListView.vue` 分类过滤使用 `RETAINED`；原型继续按真实页面行为呈现并保留差异，不修改生产代码。
2. 学籍异动真实类型同时存在 `PRESERVE`（保留学籍）与 `RETAIN`（留级），二者业务含义、审批节点和主档结果不同；原型禁止合并。
3. `/status-changes/retain` 是 redirect-only，按排除规则不生成独立 HTML，只记录其重定向到 `aa-status-change-preserve`。
4. 异动归档页面明确说明当前 `term_code` 无可靠写入口回填，因此不虚构学期筛选。

## 尚未覆盖

- 教务中心：学期与校历、学院专业班级、专业分流、课程库、培养方案、教学任务、课表、考务、预警、毕业审核、教学资源、调停课、统计归档其余切面。
- 工作台其余页面及全局审批、消息、帮助、数据中心。
- 学工中心、岗位实习中心、毕业设计中心、系统管理。
- 登录、安全、其余打印/导出预览。

未覆盖项不得描述为完成。
