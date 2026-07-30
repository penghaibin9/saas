# 教师/学校管理 PC 端 V2 高保真 HTML 原型库

本目录是教师/学校管理 PC 端的设计交付物，不是生产菜单、路由或运行时代码。

## 基线与边界

- 生产基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 原型分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 生产代码修改：**否**
- 所有变更仅位于 `docs/ui/teacher-pc-v2-html/`
- manifest 仅用于设计追溯，不是第二份生产事实源

## 当前规模

- manifest 路由/业务切面：**143**
- 独立 HTML：**137**
- 共享 HTML 路由条目：**8**
- 共享设计文件：**14**
- 已完成首轮工作区：**12**
- 一级中心完整覆盖：**0**
- 仓库截图：**0**
- 本地累计渲染截图：**231**

## 最近完成

- 课程库：列表、新建、详情、编辑及 9 个真实控制台 Tab。
- 培养方案：治理、开课差异、编制器 4 个切面及 12 个真实控制台 Tab。
- 教学任务：批次、生成、教学班/名单版本、分配、合班拆班、两级确认、教师本人确认、调整、统计。
- 课表管理：批次、归档、维护、冲突、三视图、五类对象课表、周课表、学期课表、发布、调整记录、XLSX 导出及 A4 打印。

## 离线共享实现

- `shared/v2-course-base-packed.js`
- `shared/v2-program-base-packed.js`
- `shared/v2-teaching-task-base-packed.js`
- `shared/v2-schedule-base-packed.js`

以上均为原型离线渲染资源，不依赖外部 CDN，不进入生产 Vue 运行时。

## 追溯入口

- `prototype-manifest.json`
- `manifest-parts/*.json`
- `route-coverage.md`
- `PROGRESS.md`
- `design-system.md`

页面中的“学生A / 课程A / — / 占位”均为中性 placeholder，不代表生产数据。
