# 教务统计：开发还原契约

> 本目录是教师 PC V2 高保真 HTML 原型。统计聚合、指标口径、数据范围、脱敏、下钻和导出文件仍以生产后端为唯一事实源。

## 真实入口结构

生产菜单共有 16 个入口：

- `AaStatsOverviewView.vue` 承载 14 个统计 Tab：教务总览、学籍、注册、课程、教学任务、课表、选课、考务、成绩、学业预警、毕业资格、教师工作量、教学资源、导出报表。
- 调停课统计继续使用独立页面 `/admin/academic-affairs/schedule-change/stats`，不重复造统计页。
- 工作量申报审核使用独立 `AaWorkloadReviewView.vue`。

原型为 14 个统计 Tab 与工作量审核各保留独立可打开 HTML，但视觉和交互共用 `v2-stats-workbench.css/js`。调停课统计直接复用既有 `schedule-change-stats.html`。

## 入口与原型

| 入口 | HTML | 权限 |
|---|---|---|
| 教务总览 | `stats-overview.html` | `academicAffairs.stats.view` |
| 学籍统计 | `stats-status-change.html` | `academicAffairs.stats.view` |
| 注册统计 | `stats-registration.html` | `academicAffairs.stats.view` |
| 课程统计 | `stats-course.html` | `academicAffairs.stats.view` |
| 教学任务统计 | `stats-teaching-task.html` | `academicAffairs.stats.view` |
| 课表统计 | `stats-schedule.html` | `academicAffairs.stats.view` |
| 调停课统计 | `../schedule-change/schedule-change-stats.html` | `academicAffairs.scheduleChange.view` |
| 选课统计 | `stats-selection.html` | `academicAffairs.stats.view` |
| 考务统计 | `stats-exam.html` | `academicAffairs.stats.view` |
| 成绩统计 | `stats-grade.html` | `academicAffairs.stats.view` |
| 学业预警统计 | `stats-warning.html` | `academicAffairs.stats.view` |
| 毕业资格统计 | `stats-graduation.html` | `academicAffairs.stats.view` |
| 教师工作量统计 | `stats-workload.html` | `academicAffairs.stats.view` |
| 教学资源统计 | `stats-resource.html` | `academicAffairs.stats.view` |
| 工作量申报审核 | `workload-review.html` | `academicAffairs.stats.view` |
| 导出报表 | `stats-export.html` | `academicAffairs.stats.export` |

## 统计纪律

1. 百分比必须同时显示分子与分母，不能只展示一个好看的比率。
2. 指标必须登记业务口径、筛选范围、更新时间和下钻来源。
3. 总览卡与下钻明细必须使用相同 `termId / collegeId / majorId` 及业务筛选条件。
4. 学院角色未配置数据范围时 fail-closed，不得回退为全校统计。
5. 真实零值、无数据、模块未启用、无范围和接口失败必须分别显示。
6. 摘要和明细分别加载时，页面不得用旧摘要覆盖新筛选条件。
7. 大规模明细使用服务端分页，不把全部学生或成绩一次加载到浏览器。
8. 学号等字段继续按生产后端的脱敏与角色权限返回，原型不自行判断明文权限。
9. 调停课独立页面是教师本人课位 / 业务台账视角；总览中的调停课指标是学校 / 学院聚合，两者不能互相替代。
10. 教学资源是学校级共享资产，生产统计不接受学期和学院过滤；原型不得制造不存在的筛选条件。

## 关键业务口径

### 学籍统计

只统计已生效 `EFFECTIVE` 异动。申请中、撤回、驳回和已取消记录不能计入已生效人数。

### 注册统计

完成率同时显示 `registered / expected`，下钻为未注册学生名单和原因。

### 教学任务与课表

教师确认、学院确认和管理确认是不同节点；统计页不能代替确认。课表覆盖率只认正式发布批次，草稿预排不计入发布覆盖。

### 选课与考务

选课填充率使用真实容量为分母，低人数阈值可追溯。缺考与违纪只统计已登记事实，不从统计图表直接推断纪律结论。

### 成绩与预警

挂科率使用有效成绩去重口径，补考 / 重修通过后不能继续重复计挂科。预警是干预信号，不等于处分或毕业结论。

### 毕业资格

财务等尚未接入事实以 `UNKNOWN` 展示，不得被前端擅自改为 `FAIL`。

### 教师工作量

工作量统计由教学任务计划学时和已通过的教师申报工时组成，只供教务参考。当前系统没有课程、班型、职称等学校正式系数，也不承担人事薪酬核算。

### 工作量申报审核

状态为 `SUBMITTED / APPROVED / REJECTED`。驳回理由至少 5 字；审核通过后只进入教务参考统计，不自动生成工资、绩效或结算。

### 导出报表

- 当前生产实现为同步生成 XLSX。
- 导出用途至少 5 字。
- 文件由后端按权限和数据范围生成并带审计 / 水印。
- 当前没有异步导出历史和失败重试列表，原型不得展示假任务队列。

## 公共组件映射

生产还原优先使用：

- `ModulePageShell`
- `AppTermEntityPicker` / `AppCollegePicker` / `AppMajorPicker`
- `AppGraduationBatchPicker`
- `AppMetricCard`
- `AppG2Chart`
- `DataTable`
- `LoadingState` / `EmptyState` / `ErrorState`
- `AppInlineAlert`
- `AppSelect` / `AppTextarea`
- `AppButton`

原型共享 JS 只用于离线展示，不进入生产 Vue 运行时。

## 开发 AI 读取顺序

1. 阅读 15 个 HTML 的 route、source、permission、states 和 boundary。
2. 阅读 `manifest-parts/210-stats.json`。
3. 阅读共享统计 CSS / JS 获取布局、状态和交互。
4. 回到生产 `AaStatsOverviewView.vue`、`AaWorkloadReviewView.vue`、调停课统计页和 API。
5. 阅读后端 `academic_affairs_stats_service.py` 及相关 detail / export 实现。
6. 对照真实返回字段、scope.blocked、脱敏、分页、用途校验和 XLSX 下载逐项还原。

## 当前验证口径

- 15 个新 HTML、共享 CSS/JS、开发契约和 manifest 已落盘。
- 16 个菜单入口、权限和页面复用关系已按生产 `navPlan.js` 静态核对。
- 当前连接环境未执行本批真实浏览器渲染，不能宣称控制台、溢出、焦点或三档分辨率通过。
