# 教师/学校管理 PC 端 V2 高保真 HTML 原型库

本目录是 `penghaibin9/saas` 教师/学校管理 PC 端的**设计交付物**，不是生产菜单、生产路由或运行时代码。

## 基线

- 生产基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 原型分支：`codex/teacher-pc-v2-html-library`
- 范围：`/workbench` 与教师/学校管理人员可到达的 `/admin/**`
- 排除：学生 PC、小程序、`/admin/platform/**`、纯开发预览和 redirect-only 页面

## 约束

- 所有新增文件只在 `docs/ui/teacher-pc-v2-html/`
- 不修改生产路由、权限、API、状态机、数据库、菜单配置、生产 tokens 或测试
- `prototype-manifest.json` 是设计交付映射，不是第二份生产菜单事实源
- 原型按钮不执行真实写操作
- “— / 学生A / 课程A”属于明确标注的中性 placeholder，不代表生产数据

## 当前批次

已经建立共享 V2 tokens、统一壳、组件、交互脚本和 SVG 图标体系，并生成：

- manifest 路由/切面条目：**24**
- 独立 HTML：**23**
- 共用 HTML：复学学生与转专业学生两个真实路由共用 `roster-change-results.html`

### 已完成首轮覆盖的真实工作区

1. 成绩管理
2. 成绩审核发布更正
3. 学籍管理

### 已启动但未完成

- 我的工作台
- 教务看板

### 当前 HTML

#### 工作台与中心首页

- 教师/管理工作台
- 教务工作台

#### 成绩管理

- 成绩分析
- 成绩录入（固定三段 + 动态成绩项 + 导入切面）
- 挂科清单
- 学生成绩单
- 成绩异常
- 成绩认定 · 课程替代
- 成绩统计（`/stats?tab=grade`）

#### 成绩审核发布更正

- 学院审核
- 教务发布
- 成绩更正
- 成绩复查复审
- 成绩操作审计

#### 学籍管理

- 学籍名册及状态分类视图
- 学籍状态总览
- 学籍异动记录
- 学籍导入导出
- 复学学生 / 转专业学生结果视图
- 学籍信息更正
- 学籍档案详情
- 学籍统计
- 学籍归档

当前没有宣称整个工作台中心或教务中心完成，更没有宣称全库完成。

## 快速查看

- `workbench/my-workbench/index.html`
- `academic-affairs/dashboard/index.html`
- `academic-affairs/grades/grade-overview.html`
- `academic-affairs/grades/grade-entry.html`
- `academic-affairs/grades/grade-publish.html`
- `academic-affairs/roster/roster-list.html`
- `academic-affairs/roster/roster-detail.html`
- `academic-affairs/roster/roster-import-export.html`

## 交付索引

- `prototype-manifest.json`：路由 → Vue 组件 → API/字段 → HTML
- `route-coverage.md`：当前覆盖、共用映射和代码事实差异
- `PROGRESS.md`：可无损续工状态
- `design-system.md`：视觉和母版规范
- `shared/`：所有原型复用的离线 CSS、JS 和 SVG 图标

## 截图状态

首批 14 个 HTML 已在本地渲染环境生成并检查 24 张截图：14 个页面的 1440 截图，以及工作台、教务看板、成绩分析、成绩录入、挂科清单的 1280/1920 截图。新增学籍工作区尚未生成截图。

当前 GitHub 连接器不能直接从本地二进制路径批量写入仓库，因此截图文件尚未提交。HTML 已完成首批实际渲染和横向溢出检查；截图缺口继续在 `PROGRESS.md` 中保持未完成，不以本地截图冒充仓库交付。
