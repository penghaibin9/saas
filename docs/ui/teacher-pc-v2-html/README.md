# 教师/学校管理 PC 端 V2 高保真 HTML 原型库

本目录是教师/学校管理 PC 端设计交付物，不是生产菜单、路由或运行时代码。

## 边界

- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 生产代码修改：**否**
- 所有变更仅位于本目录
- manifest 只用于设计追溯，不是第二份生产事实源
- 原型数据均为中性 placeholder，不代表生产数据

## 当前规模

- manifest 路由 / 业务切面：**175**
- 独立 HTML：**169**
- 共享 HTML 路由条目：**8**
- 共享设计文件：**17**
- 已完成首轮工作区：**15**
- 一级中心完整覆盖：**0**
- 仓库截图：**0**
- 本地累计渲染截图：**309**

## 导航规范

Teacher PC V2 的信息架构冻结为：

**顶部一级中心 → 左侧真实二级模块 → 内容区三级功能**

教务中心按生产 `navPlan.js` 直接显示 29 个真实二级模块，取消业务聚合分组。左侧菜单支持独立滚动、搜索、展开/收起和当前模块高亮；面包屑严格为“一级中心 / 二级模块 / 三级功能”。权限、角色和数据范围继续由生产代码投影，本原型库不复制裁决逻辑。

## 已完成工作区

成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次、课程库、培养方案、教学任务、课表管理、调停课、选课管理、考务管理。

## 最近新增

### 考务管理

覆盖考试批次、课程确认、自动排考、教师/教室/考生冲突、考场与座位、监考与巡考、发布前核验、异常记录、统计、归档，以及独立座位表 / 准考证 / 门贴打印页面。

业务形态和状态来自真实 `AaExamConsoleView.vue`、`AaExamSeatingPrintView.vue` 与 `academicAffairsExamApi`；没有增加生产路由、权限点、API 或状态机。

### 设计治理

- `component-reuse-matrix.md`：原型区域与真实 Vue 公共组件的复用、增强和 GAP 判断。
- `page-archetype-matrix.md`：17 类页面母版、独立 HTML 判断和重复页面收敛规则。
- 共享壳已恢复 29 项真实二级导航，并处理 packed 脚本异步加载、菜单搜索和根页面溢出问题。

## 离线共享渲染包

- `v2-course-base-packed.js`
- `v2-program-base-packed.js`
- `v2-teaching-task-base-packed.js`
- `v2-schedule-base-packed.js`
- `v2-schedule-change-base-packed.js`
- `v2-selection-base-packed.js`
- `v2-exam-base-packed.js`

这些文件仅服务 HTML 原型，不依赖 CDN，不进入生产 Vue 运行时。

## 追溯入口

- `prototype-manifest.json`
- `manifest-parts/*.json`
- `route-coverage.md`
- `component-reuse-matrix.md`
- `page-archetype-matrix.md`
- `PROGRESS.md`
- `design-system.md`

## 已知限制

本轮新增考务页面已完成三种分辨率共 33 次真实浏览器渲染；此前存在的 158 个 HTML 尚未在本轮重新全量渲染。截图和打印 PDF 只保存在执行环境，没有作为仓库交付物提交。
