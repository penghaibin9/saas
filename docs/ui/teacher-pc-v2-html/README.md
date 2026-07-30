# 教师/学校管理 PC 端 V2 高保真 HTML 原型库

本目录是 `penghaibin9/saas` 教师/学校管理 PC 端的**设计交付物**，不是生产菜单、生产路由或运行时代码。

## 基线与边界

- 生产基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 原型分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 所有变更只允许位于本目录
- 不修改生产路由、权限、API、状态机、数据库、菜单配置、生产 tokens 或测试
- 原型按钮不执行真实写操作
- `prototype-manifest.json` 是设计追溯清单，不是第二份生产菜单事实源

## 当前规模

- manifest 条目：**52**
- 独立 HTML：**46**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理
- 一级中心完整覆盖：**0**
- 仓库截图：**0**
- 本地累计渲染截图：**64**

## 本批入口

### 注册管理

- `academic-affairs/registration/registration-batches.html`
- `academic-affairs/registration/registration-eligibility.html`
- `academic-affairs/registration/registration-deferral.html`
- `academic-affairs/registration/registration-exception.html`
- `academic-affairs/registration/registration-archive.html`

### 学籍异动

- `academic-affairs/status-changes/status-change-ledger.html`
- `academic-affairs/status-changes/status-change-form.html`
- `academic-affairs/status-changes/status-change-form-transfer-major.html`
- `academic-affairs/status-changes/status-change-form-transfer-class.html`
- `academic-affairs/status-changes/status-change-approval.html`
- `academic-affairs/status-changes/status-change-detail.html`
- `academic-affairs/status-changes/status-change-print.html`

### 学籍详情

- `academic-affairs/roster/roster-detail.html`

## 共享设计系统

- `shared/v2-tokens.css`
- `shared/v2-shell.css`
- `shared/v2-components.css`
- `shared/v2-workflows.css`
- `shared/v2-prototype.js`
- `shared/v2-registration-prototypes.js`
- `shared/v2-status-change-prototypes.js`
- `shared/icons.svg`

所有 HTML 均只引用本地共享资源，不依赖外部 CDN。

## Manifest 聚合

`prototype-manifest.json` 是总索引，逐路由登记 52 个业务切面，并按顺序聚合：

- `manifest-parts/00-existing-baseline.json`
- `manifest-parts/10-registration.json`
- `manifest-parts/20-status-changes.json`
- `manifest-parts/30-roster-detail-override.json`

后加载的相同路由记录覆盖前一分片，仅用于让大规模原型库可持续维护，不改变生产路由或菜单事实源。

## 追溯与续工

- `prototype-manifest.json`：路由索引与 manifest 分片聚合规则
- `route-coverage.md`：已完成、部分完成、未开始和差异
- `PROGRESS.md`：验证结果、数量和下一批精确起点
- `design-system.md`：母版、视觉和交互规范

数据中的“— / 学生A / 课程A / 占位”是明确中性 placeholder，不代表生产数量或真实个人信息。
