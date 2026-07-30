# 路由覆盖

> 本文件是设计交付清单，不取代生产 router、模块 routes、`navPlan.js` 或权限事实源。完整逐条追溯见 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**113**
- 独立 HTML：**107**
- 共享 HTML 路由条目：**8**
- 仓库截图：**0**
- 本地累计渲染截图：**173**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次、课程库、培养方案
- 一级中心完成：**0**

## 课程库（COMPLETE）

| 路由/切面 | 组件 | HTML | 状态 |
|---|---|---|---|
| `/courses` | `AaCourseListView.vue` | `courses/course-list.html` | COMPLETE |
| `/courses/new` | `AaCourseFormView.vue` | `courses/course-new.html` | COMPLETE |
| `/courses/:id` | `AaCourseDetailView.vue` | `courses/course-detail.html` | COMPLETE |
| `/courses/:id/edit` | `AaCourseFormView.vue` | `courses/course-edit.html` | COMPLETE |
| `console?tab=category` | `AaCourseConsoleView.vue` | `courses/course-category.html` | COMPLETE |
| `console?tab=nature` | 同上 | `courses/course-nature.html` | COMPLETE |
| `console?tab=credit` | 同上 | `courses/course-credit.html` | COMPLETE |
| `console?tab=outline` | 同上 | `courses/course-outline.html` | COMPLETE |
| `console?tab=assessment` | 同上 | `courses/course-assessment.html` | COMPLETE |
| `console?tab=owner` | 同上 | `courses/course-owner.html` | COMPLETE |
| `console?tab=material` | 同上 | `courses/course-material.html` | COMPLETE |
| `console?tab=disable` | 同上 | `courses/course-disable.html` | COMPLETE |
| `console?tab=archive` | 同上 | `courses/course-archive.html` | COMPLETE |

## 培养方案（COMPLETE）

- `/programs` 治理首页
- `/programs/opening-plan` 开课差异
- `/programs/:id` 的 basic/courses/standards/review 四个重要编制切面
- `/programs/console` 十二个真实 Tab 全覆盖

完整 18 条路由/业务切面、权限、API 和状态登记在 `manifest-parts/70-programs.json`。

## 已确认差异

- 课程/方案均使用 `DRAFT / COLLEGE_REVIEW / ACADEMIC_REVIEW / ENABLED|PUBLISHED / RETURNED / FROZEN / DISABLED` 的真实状态集合。
- 课程与方案“归档”页面均为只读派生，不新增 `ARCHIVED` 状态。
- 开课差异是培养方案与教学任务的实时对照，不建立第二套教学计划。

## 尚未覆盖

- 教务中心：专业分流、教学任务、课表、选课、考务、补考重修、预警、毕业审核、教材、教学资源、评价、质量、统计归档其余切面。
- 工作台其余页面及全局审批、消息、帮助、数据中心。
- 学工中心、岗位实习中心、毕业设计中心、系统管理。
- 登录、安全、其余打印/导出预览。

未覆盖项不得描述为完成。
