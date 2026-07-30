# 教师/学校管理 PC 端 V2 高保真 HTML 原型库

本目录是教师/学校管理 PC 端设计交付物，不是生产菜单、路由或运行时代码。

## 边界

- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 生产代码修改：**否**
- 所有变更仅位于本目录
- manifest 只用于设计追溯，不是第二份生产事实源

## 当前规模

- manifest 路由/业务切面：**152**
- 独立 HTML：**146**
- 共享 HTML 路由条目：**8**
- 共享设计文件：**15**
- 已完成首轮工作区：**13**
- 一级中心完整覆盖：**0**
- 仓库截图：**0**
- 本地累计渲染截图：**250**

## 已完成工作区

成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次、课程库、培养方案、教学任务、课表管理、调停课。

## 最近新增

调停课覆盖台账、调课申请、停课申请、冲突预检、两级审批、统计、终态归档、已生效通知单及未生效禁打状态。

## 离线共享渲染包

- `v2-course-base-packed.js`
- `v2-program-base-packed.js`
- `v2-teaching-task-base-packed.js`
- `v2-schedule-base-packed.js`
- `v2-schedule-change-base-packed.js`

这些文件仅服务 HTML 原型，不依赖 CDN，不进入生产 Vue 运行时。

## 追溯入口

- `prototype-manifest.json`
- `manifest-parts/*.json`
- `route-coverage.md`
- `PROGRESS.md`
- `design-system.md`

页面中的人名、课程、班级和数量均为中性 placeholder，不代表生产数据。
