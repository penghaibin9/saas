# 教师/学校管理 PC 端 V2 高保真 HTML 原型库

本目录是 `penghaibin9/saas` 教师/学校管理 PC 端的设计交付物，不是生产菜单、路由或运行时代码。

## 基线与边界

- 生产基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 原型分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 生产代码修改：**否**
- 所有文件仅位于 `docs/ui/teacher-pc-v2-html/`
- 原型按钮不执行真实写操作
- manifest 分片仅用于设计追溯，不是第二份生产菜单事实源

## 当前规模

- manifest 路由/业务切面：**124**
- 独立 HTML：**118**
- 共享 HTML 路由条目：**8**
- 共享设计文件：**13**
- 已完成首轮工作区：**11**
- 一级中心完整覆盖：**0**
- 仓库截图：**0**
- 本地累计渲染截图：**196**

## 最近完成

### 课程库

课程列表、新建、详情、编辑及 `category / nature / credit / outline / assessment / owner / material / disable / archive` 九个真实控制台 Tab。

### 培养方案

治理首页、开课差异、编制器四个关键步骤及 `authoring / versions / planChange / courseModules / practicePlan / creditRequirements / practiceSegments / graduationRequirements / review / publish / changeStatus / archive` 十二个真实 Tab。

### 教学任务

教学任务工作台、生成批次、教学班与名单版本、教学班详情、批次详情、任课教师分配、合班拆班、两级批次确认、教师本人确认、任务调整和统计。

## 离线共享实现

- `shared/v2-course-base-packed.js`
- `shared/v2-program-base-packed.js`
- `shared/v2-teaching-task-base-packed.js`

这些文件是原型离线渲染包，使用浏览器原生 gzip 解压能力，不依赖 CDN，不进入生产 Vue 运行时。

## 追溯入口

- `prototype-manifest.json`：聚合规则、最新批次索引和覆盖汇总
- `manifest-parts/*.json`：完整 route → component → permission/API → HTML → states 记录
- `route-coverage.md`：工作区覆盖和未覆盖项
- `PROGRESS.md`：验证结果及下一批精确起点
- `design-system.md`：视觉、母版和业务真实性规范

数据中的“学生A / 课程A / — / 占位”均为中性 placeholder，不代表生产数据。
