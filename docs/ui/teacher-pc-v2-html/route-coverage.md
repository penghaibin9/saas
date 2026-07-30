# 路由覆盖

> 本文件是设计交付清单，不取代生产 router、模块 routes、`navPlan.js` 或权限事实源。完整逐条追溯见 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**124**
- 独立 HTML：**118**
- 共享 HTML 路由条目：**8**
- 仓库截图：**0**
- 本地累计渲染截图：**196**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次、课程库、培养方案、教学任务
- 一级中心完成：**0**

## 课程库（COMPLETE）

课程列表、新建、详情、编辑及九个真实控制台 Tab 全部进入 `manifest-parts/60-courses.json`。

## 培养方案（COMPLETE）

治理首页、开课差异、编制器四个业务步骤和十二个控制台 Tab 全部进入 `manifest-parts/70-programs.json`。

## 教学任务（COMPLETE）

| 路由 / 切面 | 组件 | HTML | 状态 |
|---|---|---|---|
| `/teaching-tasks` | `AaTaskBatchListView.vue` | `teaching-tasks/task-workbench.html` | COMPLETE |
| `?open=generate` | 同上 | `teaching-tasks/task-generate.html` | COMPLETE |
| `?view=classes` | `AaTeachingClassListView.vue` | `teaching-tasks/teaching-classes.html` | COMPLETE |
| `?view=classes&teachingClassId=:id` | `AaTeachingClassDetailView.vue` | `teaching-tasks/teaching-class-detail.html` | COMPLETE |
| `/teaching-tasks/:batchId` | `AaTaskDetailView.vue` | `teaching-tasks/task-detail.html` | COMPLETE |
| `/teaching-tasks/assign` | `AaTeacherAssignConsoleView.vue` | `teaching-tasks/teacher-assign.html` | COMPLETE |
| `/teaching-tasks/merge-split` | `AaTaskMergeSplitView.vue` | `teaching-tasks/merge-split.html` | COMPLETE |
| `/teaching-tasks/confirm` | `AaTaskConfirmView.vue` | `teaching-tasks/batch-confirm.html` | COMPLETE |
| `/teaching-tasks/teacher-confirm` | `AaTeacherTaskConfirmView.vue` | `teaching-tasks/teacher-confirm.html` | COMPLETE |
| `/teaching-tasks/adjust` | `AaTaskAdjustView.vue` | `teaching-tasks/task-adjust.html` | COMPLETE |
| `/teaching-tasks/stats` | `AaTaskStatsView.vue` | `teaching-tasks/task-stats.html` | COMPLETE |

完整权限、API、字段和状态登记在 `manifest-parts/80-teaching-tasks.json`。

## 重要事实

- 教师本人确认不可由管理端代替。
- 合班仅限教师确认前、同批次且同课程的两条及以上任务。
- 教学班名单版本是下游考勤、考务和成绩的正式成员事实。
- 名单变化生成新版本，旧版本保留；下游已消费时必须阻断直接改名册。
- 教学任务更换教师后退回已分配状态，要求新教师重新确认。

## 尚未覆盖

- 教务中心：专业分流、课表、调停课、选课、考务、补考重修、预警、毕业审核、教材、教学资源、评价、质量、统计归档其余切面。
- 工作台其余页面及全局审批、消息、帮助、数据中心。
- 学工中心、岗位实习中心、毕业设计中心、系统管理。
- 登录、安全、其余打印/导出预览。

未覆盖项不得描述为完成。
