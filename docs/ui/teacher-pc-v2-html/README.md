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

- manifest 路由/业务切面：**82**
- 独立 HTML：**76**
- 共享 HTML 路由条目：**8**
- 已完成首轮工作区：**8**
  1. 成绩管理
  2. 成绩审核发布更正
  3. 学籍管理
  4. 注册管理
  5. 学籍异动办理
  6. 学院专业班级
  7. 学年学期
  8. 校历节次
- 一级中心完整覆盖：**0**
- 仓库截图：**0**
- 本地累计渲染截图：**118**

“首轮完成”只表示当前工作区的可达路由、重要 query/状态切面与关键办理态已进入 manifest 并完成检查，不代表教务中心或教师 PC 全量完成。

## 主要入口

### 注册、学籍与异动

- `academic-affairs/registration/`
- `academic-affairs/roster/`
- `academic-affairs/status-changes/`

### 学院专业班级

- `academic-affairs/orgs/`

真实 `AaOrgConsole.vue` 共覆盖学院、专业、行政班、年级、教学班、专业方向、班级学生、班级调整、组织树、统计、变更审计 11 个 Tab。

### 学年学期与校历节次

- `academic-affairs/terms-calendar/term-list.html`
- `academic-affairs/terms-calendar/term-new.html`
- `academic-affairs/terms-calendar/term-current.html`
- `academic-affairs/terms-calendar/term-status.html`
- `academic-affairs/terms-calendar/term-teaching-weeks.html`
- `academic-affairs/terms-calendar/term-teaching-weeks-locked.html`
- `academic-affairs/terms-calendar/calendar-events.html`
- `academic-affairs/terms-calendar/calendar-events-locked.html`
- `academic-affairs/terms-calendar/calendar-holiday.html`
- `academic-affairs/terms-calendar/calendar-makeup.html`
- `academic-affairs/terms-calendar/calendar-week.html`
- `academic-affairs/terms-calendar/calendar-publish.html`
- `academic-affairs/terms-calendar/calendar-archive.html`
- `academic-affairs/terms-calendar/time-slots.html`
- `academic-affairs/terms-calendar/time-bands.html`

## 共享设计系统

- `shared/v2-tokens.css`
- `shared/v2-shell.css`
- `shared/v2-components.css`
- `shared/v2-workflows.css`
- `shared/v2-prototype.js`
- `shared/v2-registration-prototypes.js`
- `shared/v2-status-change-prototypes.js`
- `shared/v2-org-prototypes.js`
- `shared/v2-time-base.js`
- `shared/icons.svg`

所有 HTML 均只引用本地共享资源，不依赖外部 CDN。

## Manifest 聚合

`prototype-manifest.json` 是总索引，逐路由登记 82 个业务切面，并按顺序聚合：

- `manifest-parts/00-existing-baseline.json`
- `manifest-parts/10-registration.json`
- `manifest-parts/20-status-changes.json`
- `manifest-parts/30-roster-detail-override.json`
- `manifest-parts/40-org-console.json`
- `manifest-parts/50-terms-calendar.json`

后加载的相同路由记录覆盖前一分片，仅用于让大规模原型库可持续维护，不改变生产路由、权限或菜单事实源。

## 追溯与续工

- `prototype-manifest.json`：路由索引、数量和 manifest 分片聚合规则
- `route-coverage.md`：已完成、部分完成、未开始和差异
- `PROGRESS.md`：验证结果、数量和下一批精确起点
- `design-system.md`：母版、视觉、状态和交互规范

数据中的“— / 学生A / 课程A / 占位”是明确中性 placeholder，不代表生产数量或真实个人信息。
