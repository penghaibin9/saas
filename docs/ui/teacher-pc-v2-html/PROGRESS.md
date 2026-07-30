# PROGRESS

## 当前状态

- 状态：**IN PROGRESS**
- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 共享设计系统：`teacher-pc-v2 / 0.6.0`
- 生产代码修改：**否**
- 允许目录外修改：**0**

## 本轮完成

### 课程库

- 课程列表、新建、详情、编辑
- `category / nature / credit / outline / assessment / owner / material / disable / archive` 九个真实 Tab
- 分类/性质/考核方式调整抽屉
- 学分学时全字段抽屉
- 课程负责人绑定
- 大纲/材料上传登记及作废确认
- 两级审核、退回理由、启停和培养方案引用保护
- 历史课程按 `DISABLED + SUPERSEDED` 只读派生，不虚构 `ARCHIVED`

### 培养方案

- 培养方案治理与内联新建
- 开课差异：漏开、重复、多开、缺教师、学分/学时不一致、未解析、未匹配班级
- 编制器：基本信息、课程结构、国家标准依据、审核发布四个关键切面
- 控制台 12 个真实 Tab：`authoring / versions / planChange / courseModules / practicePlan / creditRequirements / practiceSegments / graduationRequirements / review / publish / changeStatus / archive`
- 新建版本、带原因计划变更、课程/实践/学分/毕业要求 CRUD、两级审核、年级/班级绑定、冻结/恢复/停用、变更记录
- 方案归档为已停用和被新版本取代的只读派生结果，不新增状态值

## 累计数量

- manifest 条目：**113**
- 独立 HTML：**107**
- 共享路由条目：**8**
- shared 文件：**12**
- 仓库截图：**0**
- 本地累计渲染截图：**173**
- 已完成首轮工作区：**10**
- 完成一级中心：**0**

## 本批验证

- 新增页面：**31**
- 1440 × 1000：31 页全部渲染
- 1280 × 900：12 个关键页额外渲染
- 1920 × 1080：12 个关键页额外渲染
- 本批总渲染：**55 次**
- 页面级横向溢出：**0**
- 控制台明显错误：**0**
- 相对资源缺失：**0**
- 根布局已增加 `min-width:0` 密集工作区约束，9/12 Tab 不会撑宽页面
- 截图只保存在执行环境，**未提交 GitHub 仓库**

## 已完成首轮工作区

1. 成绩管理
2. 成绩审核发布更正
3. 学籍管理
4. 注册管理
5. 学籍异动办理
6. 学院专业班级
7. 学年学期
8. 校历节次
9. 课程库
10. 培养方案

“首轮完成”不代表教务中心或教师 PC 全量完成。

## 已确认差异 / 疑问

1. `navPlan.js` 使用 `PRESERVED`，`AaRosterListView.vue` 使用 `RETAINED`；只记录，不修改。
2. `PRESERVE` 是保留学籍，`RETAIN` 是留级，不能合并。
3. `/status-changes/retain` 是 redirect-only，不生成原型。
4. 异动记录 `term_code` 无可靠回填，不虚构学期筛选。
5. 学期和校历归档统一进入教务归档，不造第二套写入口。
6. 课程历史视图没有 `ARCHIVED` 状态；只使用 `DISABLED` 与版本关系。
7. 课程控制台维度写操作真实后端为完整记录整体 PUT，原型不得暗示局部 PATCH。
8. 方案归档是 `DISABLED ∪ SUPERSEDED` 只读派生；生命周期变更在方案变更 Tab 执行。
9. `/programs/opening-plan` 被动态 `:id` 路由接收后由编辑器组件内部切换到开课差异页面，原型按真实可达切面登记。

## 下一批精确起点

按业务依赖继续 **教学任务**：

1. `/admin/academic-affairs/teaching-tasks` 教学任务批次
2. `/teaching-tasks/:batchId` 教学任务明细
3. `/teaching-tasks/assign` 任课教师分配
4. `/teaching-tasks/merge-split` 合班拆班
5. `/teaching-tasks/confirm` 教学任务确认
6. `/teaching-tasks/teacher-confirm` 教师任务确认
7. `/teaching-tasks/adjust` 教学任务调整
8. `/teaching-tasks/stats` 教学任务统计
9. 生成、分配、确认、退回、调整、只读、异常和批量办理状态

教学任务完成后继续课表管理。

## Git 状态

- 保持 Draft PR #27
- 不合并 main
- 不创建新 PR
- 每批只修改 `docs/ui/teacher-pc-v2-html/`
