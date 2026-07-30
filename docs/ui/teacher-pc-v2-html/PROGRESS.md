# PROGRESS

## 当前状态

- 状态：**IN PROGRESS**
- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 共享设计系统：`teacher-pc-v2 / 0.7.0`
- 生产代码修改：**否**
- 允许目录外修改：**0**

## 本轮完成

### 课程库

- 课程列表、新建、详情、编辑
- 九个真实控制台 Tab：`category / nature / credit / outline / assessment / owner / material / disable / archive`
- 两级审核、退回、课程引用保护、材料上传登记、版本治理和历史课程只读派生

### 培养方案

- 治理首页、开课差异
- 编制器四个关键步骤：基本信息、课程结构、国家标准依据、审核发布
- 十二个真实控制台 Tab：`authoring / versions / planChange / courseModules / practicePlan / creditRequirements / practiceSegments / graduationRequirements / review / publish / changeStatus / archive`
- 版本、变更、课程与实践结构、学分与毕业要求、审核发布、年级绑定、冻结恢复停用和归档派生

### 教学任务

- 教学任务工作台与生成批次
- 教学班与名单版本、教学班详情
- 批次工作台与阻断项
- 任课教师分配
- 合班拆班
- 学院核对与教务终审
- 教师本人确认/提出异议
- 教学任务调整
- 教学任务统计

## 累计数量

- manifest 条目：**124**
- 独立 HTML：**118**
- 共享路由条目：**8**
- shared 文件：**13**
- 仓库截图：**0**
- 本地累计渲染截图：**196**
- 已完成首轮工作区：**11**
- 完成一级中心：**0**

## 教学任务验证

- 新增页面：**11**
- 1440 × 1000：11 页全部渲染
- 1280 × 900：6 个关键页额外渲染
- 1920 × 1080：6 个关键页额外渲染
- 本批总渲染：**23 次**
- 页面级横向溢出：**0**
- 控制台明显错误：**0**
- 相对资源缺失：**0**
- 关键弹窗/确认框：可打开
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
11. 教学任务

“首轮完成”不代表教务中心或教师 PC 全量完成。

## 已确认差异 / 疑问

1. `navPlan.js` 使用 `PRESERVED`，`AaRosterListView.vue` 使用 `RETAINED`；只记录，不修改。
2. `PRESERVE` 是保留学籍，`RETAIN` 是留级，不能合并。
3. `/status-changes/retain` 是 redirect-only，不生成原型。
4. 异动记录 `term_code` 无可靠回填，不虚构学期筛选。
5. 学期和校历归档统一进入教务归档，不造第二套写入口。
6. 课程历史视图没有 `ARCHIVED` 状态，只使用 `DISABLED` 与版本关系。
7. 课程控制台维度写操作为完整记录整体 PUT，原型不暗示局部 PATCH。
8. 方案归档是 `DISABLED ∪ SUPERSEDED` 只读派生。
9. `/programs/opening-plan` 由动态 `:id` 路由接收后在编辑器内部切换到开课差异页。
10. 教师确认必须由绑定稳定工号的教师本人完成，管理端不可代确认。
11. 教学班名单版本是下游考勤、考务和成绩使用的正式成员事实，历史版本不能覆盖。
12. 已生成课表项的任务不能直接调整，须先进入排课模块处理。

## 下一批精确起点

继续 **课表管理**：

1. `/admin/academic-affairs/schedule` 课表批次
2. `/schedule/:batchId/edit` 课表维护
3. `/schedule/:batchId/views` 课表三视图
4. `/schedule/class/:classId?` 班级课表
5. `/schedule/teacher/:teacherKey?` 教师课表
6. `/schedule/room/:classroomId?` 教室课表
7. `/schedule/student/:studentId?` 学生课表
8. `/schedule/teaching-class/:code?` 教学班课表
9. `/schedule/week` 周课表
10. `/schedule/semester` 学期课表
11. `/schedule/publish` 课表发布
12. `/schedule/adjustments` 课表调整记录
13. `/schedule/export` 课表导出
14. 冲突、未排、拖拽/编辑、发布锁定、只读、导出预览和长周历状态

课表完成后继续调停课与选课管理。

## Git 状态

- 保持 Draft PR #27
- 不合并 main
- 不创建新 PR
- 每批只修改 `docs/ui/teacher-pc-v2-html/`
