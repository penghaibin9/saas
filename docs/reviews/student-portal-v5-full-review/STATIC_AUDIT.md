# Student Portal V5 · PR #29 静态复审证据

> 本文只记录代码与 GitHub 证据，不把 lint、build 或公共 CSS 命中等同于真实页面验收完成。

## 1. 现场保护

- `main` 基线：`6d0e0cdaf27d36c7eadcd78a0a3bd062a0b7567b`
- 复审分支：`agent/student-portal-v5-full-review`
- Draft PR：#30 `Student Portal V5 full review and remediation`
- 当前没有修改、回滚或再次合并 `main`。
- 当前执行环境不能联网 clone 仓库，因此不能伪造本地 `git status / branch --show-current / log -1` 输出；远程分支由 GitHub 从当前 `main` 创建。

## 2. PR #29 实际修改的 5 个文件

| 文件 | 实际职责 | 实际重构范围 | 影响方式 |
|---|---|---|---|
| `student-portal/src/App.vue` | 全局主题状态、CSS 变量、V5 两份样式入口、毕设健康提示圆角 | 主题系统和全局样式加载 | 直接影响全部学生门户页面 |
| `student-portal/src/layouts/PortalLayout.vue` | 门户一级导航、顶栏、主题切换器、首页/业务页紧凑骨架 | 公共门户壳层 | 直接影响所有受保护路由 |
| `student-portal/src/views/home/HomeView.vue` | 首页英雄区、成长航线、待办、消息、指标、快捷入口 | 首页被逐块重写 | 仅首页属于真正的页面级重构 |
| `student-portal/src/styles/v5-overrides.css` | 卡片、表单、表格、暗色模式、`:has(> .sp-tabs)` 双栏、分组标题、响应式 | 公共表现层覆盖 | 所有业务页被间接套用；不是逐页设计 |
| `student-portal/src/styles/v5-polish.css` | 分组标题、焦点态、暗色补丁、宽屏与窄屏细节 | 公共表现层微调 | 所有匹配选择器的页面被间接影响 |

## 3. 已真正重构与未真正重构的边界

### 已真正重构

1. `/home`：`HomeView.vue` 模板和局部样式被实质重写。
2. 全部登录后页面的一级侧栏和顶栏：`PortalLayout.vue` 被实质重写。
3. 六套主题切换入口：`App.vue + PortalLayout.vue`。
4. 顶部搜索入口：`PortalLayout.vue` 新增跳转行为。

### 只被公共 CSS 影响，未逐页重构

以下生产页面模板、业务字段、真实按钮和业务状态并未在 PR #29 中逐页重写：

- `/profile` → `ProfileView.vue`
- `/academic` → `AcademicView.vue`（19 个真实 tab）
- `/campus-service` → `AffairsFourEndView.vue`
- `/materials` → `MaterialSupplementView.vue`
- `/internship` → `InternshipView.vue`
- `/internship/compliance` → `InternshipComplianceView.vue`
- `/employment` → `EmploymentView.vue`
- `/orientation` → `OrientationView.vue`
- `/messages` → `MessagesView.vue`
- `/service-hall` → `ServiceHallView.vue`
- `/graduation` → `GraduationWorkbenchView.vue` 及 `App.vue` 后置扩展面板
- `/module-disabled/:module`、`/not-enabled` 等状态页

这些页面主要通过 `v5-overrides.css` 的通用选择器、`:has(> .sp-tabs)` 网格和暗色变量被改变，不能据此称为“V5 全部门户页面已逐页还原”。

## 4. 与“V5 全部门户页面已还原”的真实差距

1. 页面级模板只实质重写了首页；业务页没有按每个真实 tab 逐页还原 HTML 原型。
2. `v5-overrides.css` 把任何顶层含 `.sp-tabs` 的页面强制改为 208px 侧栏 + 内容区，缺乏逐页例外清单。
3. 业务页存在大量自定义 class、内联白底、局部固定宽度和独立交互，公共暗色规则无法自动覆盖。
4. 原型里描述的组件层级并未全部抽成生产组件，AI 原型合同也没有进入运行时代码。
5. 上次合并前没有对全部路由、全部真实 tab、六套主题和多分辨率进行真实浏览器验收。

## 5. 已确认的回归风险与问题

### P1/P2 候选：顶部搜索无实际筛选效果

`PortalLayout.vue` 将关键词路由到 `/service-hall?kw=...`，但 `ServiceHallView.vue` 的本地 `kw` 未从 route query 初始化或监听。表现为用户按回车后进入办事大厅，但搜索框为空、目录未过滤。

### P2：成长航线把“未聚合”误判为“未开始”

`HomeView.vue` 的成长航线包含 `campusService` 和 `graduation`；首页聚合数据没有相应域记录时，代码直接显示“未开始”。缺少聚合记录只能说明状态未知，不能证明学生没有该业务。

### P1/P2：深邃黑主题覆盖不完整

全局暗色规则只覆盖少量通用 class；业务页面仍有大量自定义白底容器和内联白色背景。与此同时 `--t1` 至 `--t4` 被改成浅色，存在浅色文字落在白底上的不可读风险。必须真实逐页截图确认，不能只检查首页。

### 复审基础设施阻塞：沙箱种子与数据库约束不一致

真实 MySQL 迁移已把 `t_internship_record.batch_id` 设为 NOT NULL；现有 `sandbox_service.seed_sandbox()` 尾部仍新增一条没有 `batch_id` 的旧实习记录，导致全新数据库无法完成沙箱建数。该问题不是本次前端修改造成，但会阻断真实页面复审。

本任务不改后端。复审工作流只在一次性 CI 数据库中使用透明兼容步骤：临时允许旧种子写入，将该记录归入明确命名的“V5 复审兼容批次”，确认无 NULL 后恢复 NOT NULL。此限制必须保留在最终报告。

## 6. 公共改动的重点复验范围

- `:has(> .sp-tabs)` 对教务、实习、学工、就业、迎新、办事大厅等页面的布局影响。
- 208px 侧栏与 76px 一级图标栏在 1920、1440、1366、1024 宽度的实际占比。
- 长 tab、长表格、双列表单、sticky 卡片、内联 `overflow:hidden` 的裁切问题。
- 六套主题在自定义业务容器、表格、表单、状态标签、毕设扩展面板上的对比度。
- 顶栏搜索、直接访问、F5 刷新、消息跳转、实习合规入口和模块开关页面。

## 7. 当前阶段结论

尚不能给出“可以保留并直接合并”的结论。必须等待真实 Chromium 复审证据和截图，再按 P0–P3 分级。PR #30 保持 Draft。
