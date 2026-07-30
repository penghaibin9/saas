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

- manifest 路由/业务切面：**113**
- 独立 HTML：**107**
- 共享 HTML 路由条目：**8**
- 共享设计文件：**12**
- 已完成首轮工作区：**10**
- 一级中心完整覆盖：**0**
- 仓库截图：**0**
- 本地累计渲染截图：**173**

## 本轮新增

### 课程库（13页）

课程列表、新建、详情、编辑，以及控制台 9 个真实 Tab：课程分类、课程性质、学分学时、课程大纲、考核方式、课程负责人、课程材料、课程停用、历史课程。

### 培养方案（18页）

培养方案治理、开课差异、编制器 4 个关键步骤，以及控制台 12 个真实 Tab：方案制定、版本、计划变更、课程模块、实践教学计划、学分要求、实践环节、毕业要求、审核、发布、变更、归档。

## 离线共享实现

- `shared/v2-course-base-packed.js`
- `shared/v2-program-base-packed.js`

二者是离线原型渲染包，使用浏览器原生 `DecompressionStream('gzip')` 解包本地脚本，不依赖 CDN 或网络请求。生产 Vue 不使用这些文件。

## 追溯入口

- `prototype-manifest.json`：聚合规则、当前批次索引和覆盖汇总
- `manifest-parts/*.json`：完整 route → component → permission/API → HTML → states 记录
- `route-coverage.md`：工作区覆盖与未覆盖项
- `PROGRESS.md`：验证结果和下一批精确起点
- `design-system.md`：视觉、母版和业务真实性规范

数据中的“学生A / 课程A / — / 占位”均为中性 placeholder，不代表真实生产数据。
