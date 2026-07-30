# 路由覆盖

> 本文件是设计交付清单，不取代生产路由、菜单或权限事实源。完整追溯见 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**175**
- 独立 HTML：**169**
- 共享 HTML 路由条目：**8**
- 共享设计文件：**17**
- 仓库截图：**0**
- 本地累计渲染截图：**309**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次、课程库、培养方案、教学任务、课表管理、调停课、选课管理、考务管理
- 一级中心完成：**0**

## 教务中心导航纠偏（COMPLETE）

- 左侧菜单按 `frontend/src/config/navPlan.js` 冻结顺序直接展示 **29 个真实二级模块**。
- 已取消“学期与校历、组织与学籍”等 8 个原型聚合分组；分组不再作为菜单、折叠层级、页面、路由、点击入口或面包屑节点。
- 导航层级为：**顶部一级中心 → 左侧真实二级模块 → 内容区三级功能**。
- 共享原型壳支持二级菜单搜索、独立纵向滚动、展开/收起、当前模块高亮和严格三级面包屑。
- 原型尚未覆盖的真实二级模块保留名称与生产路由提示，但不伪装为已经存在独立高保真 HTML。
- 权限继续以 `navPlan → adminMenu → BasePortalLayout` 的生产投影为准，本 PR 没有修改权限点、角色或数据范围。

## 考务管理（COMPLETE）

| 路由 / 业务切面 | 源组件 | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/exam?view=batches` | `AaExamConsoleView.vue` | `exam/exam-batches.html` | COMPLETE |
| 同路由考试课程确认 | 同上 | `exam/exam-courses.html` | COMPLETE |
| 同路由自动排考 | 同上 | `exam/exam-auto-arrange.html` | COMPLETE |
| 同路由冲突处理 | 同上 | `exam/exam-conflicts.html` | COMPLETE |
| 同路由考场与座位 | 同上 | `exam/exam-rooms-seats.html` | COMPLETE |
| 同路由监考与巡考 | 同上 | `exam/exam-invigilators.html` | COMPLETE |
| 同路由发布前核验 | 同上 | `exam/exam-publish-precheck.html` | COMPLETE |
| 同路由异常记录 | 同上 | `exam/exam-incidents.html` | COMPLETE |
| 同路由考务统计 | 同上 | `exam/exam-stats.html` | COMPLETE |
| `/admin/academic-affairs/exam?tab=archive` | 同上 | `exam/exam-archive.html` | COMPLETE |
| `/admin/academic-affairs/exam/print/seating?roomId=:roomId` | `AaExamSeatingPrintView.vue` | `exam/exam-seating-print.html` | COMPLETE |

完整权限、API、角色、母版和状态登记在 `manifest-parts/120-exam.json`。

### 考务事实边界

- 真实生命周期按生产页面核对为：`DRAFT → COURSE_CONFIRMED → ARRANGED / PUBLISHED → FINISHED → ARCHIVED`，页面说明保持“草稿→圈课→学院确认→编排→发布→结束→归档”。
- 自动排考明确区分仅预检和正式执行，并保留人工编排保护、漏排原因和监考缺口。
- 冲突按教师、教室、考生时间和监考缺口分别定位，不能用一个笼统失败提示替代。
- 发布是高风险流转，必须重新读取后端状态并完成课程、时间、考场、座位、监考和冲突核验。
- 考场异常仅记录缺考、违纪和其他事实，不越权替代处分、申诉或成绩处理。
- 归档为只读封存；打印使用独立 A4 页面，无 `roomId`、无权限或座位未铺排时不得输出空白正式单据。

### 考务实际验证

- 10 个考务工作区 × 3 种分辨率：**30 次真实浏览器渲染**。
- 独立打印页 × 3 种分辨率：**3 次真实浏览器渲染**，另验证 A4 打印媒体。
- 分辨率：`1280×900`、`1440×1000`、`1920×1080`。
- 结果：控制台错误 **0**、根页面横向溢出 **0**。
- 已检查：29 项名称与顺序、当前模块高亮、菜单搜索、展开/收起、三级页签跳转、三级面包屑、加载/空/错误/403/长数据、确认弹层和 Escape 关闭。
- 截图和打印 PDF 只存在于本地执行环境，未提交 PR。

## 选课管理（COMPLETE）

| 路由 / 切面 | 源组件 | HTML | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/selection` | `AaSelectionConsoleView.vue` | `selection/selection-batches.html` | COMPLETE |
| 同路由 `DRAFT` | 同上 | `selection/selection-draft-config.html` | COMPLETE |
| 同路由轮次/抽签 | 同上 | `selection/selection-rounds.html` | COMPLETE |
| 同路由 `OPEN` | 同上 | `selection/selection-open-monitor.html` | COMPLETE |
| 同路由 `CLOSED` | 同上 | `selection/selection-closed-review.html` | COMPLETE |
| 同路由异常/冲突 | 同上 | `selection/selection-conflicts.html` | COMPLETE |
| 同路由 `LOCKED` | 同上 | `selection/selection-locked-roster.html` | COMPLETE |
| `/admin/academic-affairs/my-selection` | `AaSelectionStudentView.vue` | `selection/my-selection-open.html` | COMPLETE |
| 同路由满额态 | 同上 | `selection/my-selection-full.html` | COMPLETE |
| 同路由补选指引 | 同上 | `selection/my-selection-reselect.html` | COMPLETE |
| `/admin/academic-affairs/selection/archive` | `AaSelectionArchiveView.vue` | `selection/selection-archive.html` | COMPLETE |
| 同路由归档详情 | 同上 | `selection/selection-archive-detail.html` | COMPLETE |

完整权限、API、字段与状态登记在 `manifest-parts/110-selection.json`。

## 尚未覆盖

- 教务中心：专业分流、排课管理、课堂考勤、补考重修缓考免修、学业预警、毕业资格审核、教材管理、教学资源、教学评价、教学质量、教务归档、教务统计等真实二级模块或其复杂切面。
- 工作台其余页面及全局审批、消息、帮助、数据中心。
- 学工中心、岗位实习中心、毕业设计中心、系统管理。
- 登录、安全、其余打印/导出预览。

## 尚未完成的验证

- 本轮没有在浏览器中重新渲染此前已存在的 **158 个 HTML**。共享导航和壳层改动已通过新增考务工作区回归，但旧页面仍需执行一次169页全量浏览器回归。
- 当前执行环境无法直接克隆完整分支快照；全目录资源检查目前由 GitHub 文件读取、manifest 追踪和新增页面真实渲染共同承担。

未覆盖或未验证项不得描述为完成。
