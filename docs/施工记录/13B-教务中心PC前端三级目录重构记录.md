# 13B 教务中心 PC 前端三级目录重构记录

> 日期：2026-07-10
> 性质：菜单/页面树审计、三级目录重构、旧路由兼容核对；不做教务业务开发。
> 分支：`codex/academic-affairs-ui-refactor`
> worktree：`C:\Users\10850\Desktop\academic-affairs-ui-refactor`

## 1. 本轮结论

教务中心 PC 导航已从“按实体和动作拆分的 27 个二级模块、295 个三级叶子”收敛为“按真实教学运行主线组织的 12 个二级业务域、118 个页面库存”。其中 87 个为独立菜单页，31 个为详情、tab、指标下钻或时间线，不进入菜单。

状态严格按代码事实重判：

- `implemented`：0 个页面。
- `partial`：8 个现有路由页面。
- `planned`：110 个页面。

现有页面全部保留且仍可访问，但其 API 层存在真实接口失败后回退内存 mock 的行为，不能按生产级标准标 `implemented`。本轮未创建空页面、假按钮、假接口或新业务路由。

## 2. 开工安全与范围

开工前已执行：

```text
git status --short
git branch --show-current
git log --oneline -8
```

主工作区存在后端、岗位实习、毕业设计、迎新、小程序等大量无关 WIP，按任务要求创建独立 worktree 后施工。原工作区改动未移动、未覆盖、未暂存。

本轮允许范围内实际涉及：

- `frontend/src/config/navPlan.js`
- `frontend/src/config/adminMenu.js`
- `frontend/src/views/admin/academic/AdminAcademicLayout.vue`
- `docs/modules/13B-教务中心页面树与路由设计.md`
- `docs/施工记录/13B-教务中心PC前端三级目录重构记录.md`

明确未修改：`backend/**`、`miniapp/**`、`internship/**`、`student-affairs/**`、`graduation/**`、`orientation/**`、`employment/**`、数据库、migration、mock 数据文件。

## 3. 菜单真实渲染链路

| 层级 | 真实来源 | 消费位置 | 结论 |
|---|---|---|---|
| 一级图标轨 | `config/adminMenu.js` | `BasePortalLayout.vue#getVisibleAdminMenu` | 本轮把教务入口名称改为“教务工作台” |
| 二级/三级侧栏 | `config/navPlan.js` | `BasePortalLayout.vue#getVisibleNavPlan` | 本轮 27→12，详情/指标 hidden |
| 路由 | `modules/academic/academic.routes.js` | `router/index.js` | 保留 8 条现有路由，不删除 |
| router meta | 各路由 meta | 路由守卫/标题契约 | 不直接生成菜单 |
| Pinia | 无 | — | 不生成教务菜单 |
| 后端菜单接口 | 无 | — | 菜单不来自后端或数据库 |
| 菜单缓存 | 无 | — | localStorage 仅主题；sessionStorage 仅令牌 |

`AdminAcademicLayout.vue` 原有 6 项静态 `MENUS` 与真实 `navPlan` 重复，虽然在 ctx 加载后不参与侧栏渲染，仍会造成短暂旧菜单和维护歧义；本轮已移除，教务二/三级菜单只保留 `navPlan.js` 单一事实源。

## 4. 新 12 个二级业务域

1. 教务工作台
2. 教学计划
3. 课程与排课
4. 选课与教学班
5. 教师教学任务
6. 考务管理
7. 成绩管理
8. 学籍管理
9. 学业预警
10. 教材与教学资源
11. 教学质量
12. 教务统计与归档

设计原因：概览统一进入工作台；统计和归档统一收口；计划、课程、排课、选课、考务、成绩、学籍各自保持职责清晰；教师个人任务与教务管理视图分离；详情、审批记录、指标和归档材料不再全部挂菜单。

## 5. 去重处理汇总

### 5.1 合并菜单

- 学年学期 + 校历节次 + 培养方案 + 教学计划 → 教学计划。
- 课程库 + 排课管理 + 课表管理 + 调停课 → 课程与排课。
- 选课管理 + 教学班 → 选课与教学班。
- 教学任务中的教师执行视图 → 教师教学任务。
- 考务管理 + 补考重修缓考免修 → 考务管理。
- 成绩管理 + 成绩审核发布更正 → 成绩管理。
- 学籍管理 + 注册管理 + 学籍异动 + 毕业资格审核 → 学籍管理。
- 教材管理 + 教学资源 → 教材与教学资源。
- 教学评价 + 教学质量 → 教学质量。
- 教务归档 + 教务统计 → 教务统计与归档。

### 5.2 移为详情/tab/指标

- 课程详情与大纲、培养方案详情、教学任务详情、考试安排详情、成绩更正详情、学生详情、预警详情、教材/资源详情、质量整改详情 → 详情页。
- 校历/节次、合班记录、分域归档 → 对应主页面 tab。
- 排课冲突、考试提醒、成绩进度、异动待办、预警来源、教师工作量、考务统计 → 指标或下钻。
- 审核记录、处置时间线、发布回退记录、导出下载审计 → 时间线/抽屉。

### 5.3 归档材料

培养方案版本、课表发布批次、选课名单、考务批次、成绩发布批次、学籍异动单、预警处置记录、质量整改证据统一由“业务归档中心”按业务域组织，不再每个二级模块重复挂一个“归档”菜单。

### 5.4 external-link

学院/专业/班级组织主数据不在教务中心重复维护；后续由系统组织中心提供只读引用、Picker 或关联跳转。未确认真实目标路由前保持 planned，不伪造 external-link path。

## 6. 现有 partial 路由兼容

| 路由 | 新归属 | 菜单形态 | 状态 |
|---|---|---|---|
| `/admin/academic` | 教务工作台/教务总览 | 菜单 | partial |
| `/admin/academic/students` | 学籍管理/学生学籍 | 菜单 | partial |
| `/admin/academic/students/:id` | 学籍管理/学生学业详情 | 详情 | partial |
| `/admin/academic/grades` | 成绩管理/成绩查询 | 菜单 | partial |
| `/admin/academic/credits` | 成绩管理/GPA 与学分修读 | 菜单 | partial |
| `/admin/academic/makeup-retake` | 考务管理/补考与重修 | 菜单 | partial |
| `/admin/academic/warnings` | 学业预警/预警学生 | 菜单 | partial |
| `/admin/academic/warnings/:id` | 学业预警/预警跟进详情 | 详情 | partial |

未删除旧路由，未扩大 meta 权限，未把旧路径 redirect 到 planned 空页。顶部功能搜索已拆分为工作台、学籍、成绩、GPA/学分、补考重修、预警六个真实承接入口。

## 7. 权限审计结论

本轮没有新增 permissionCode、没有放宽角色白名单、没有合并多个角色权限。菜单重组只改变信息架构，不改变后端数据范围。

仍需后续真实业务开发补齐的 B 类安全欠账：

1. `module.academicAffairs.enabled` 的菜单、路由和接口三层闸门尚未完整落地。
2. 教务旧页当前角色/范围来自 mock 上下文，不能作为真实授权证明。
3. 成绩提交、审核、发布的职责分离尚未形成完整后端闭环。
4. 学籍异动单一入口、状态机和审计尚未形成完整后端闭环。
5. 导出仍可回退 mock，不能作为正式 xlsx 导出验收依据。

因此所有现有页保持 partial，planned 页无 path、不可点击；权限没有扩大。

## 8. 性能处理

- 二级模块：27 → 12。
- 可渲染菜单叶子：295 → 87。
- 31 个详情/指标节点标 `hidden`，不进侧栏和搜索。
- 保留现有扁平索引、可见树缓存、搜索缓存、20 条结果上限和唯一 leafKey 高亮策略。
- 未新增路由切换时的菜单全量重建、后端请求或 localStorage 菜单缓存。

## 9. 验证记录

完成后执行：

```text
cd frontend
npm run build
npm run lint
```

验证结果：

- `npm run build`：通过（Vite production build，747 modules transformed）。
- `npm run lint`：通过，0 error；保留 2 个任务前已有 warning：`src/utils/dateUtils.js` 未使用变量、`TopicLibListView.vue` 未使用常量，均属禁改/无关范围。
- navPlan 自动统计：12 个二级、118 个页面、87 个菜单页、31 个非菜单页、8 partial、110 planned。
- Node 导航断言：通过；覆盖数量、状态、hidden、普通角色可见模块、成绩/学籍/预警高亮、搜索跳转、一级入口名称。
- `git diff --check`：通过。
- 禁改目录核对：通过，仅包含本记录 §2 列出的 5 个文件。

## 10. 是否进入教务业务开发前契约核对

页面树、旧页映射、业务流程落位和权限边界已经形成，可进入下一阶段“教务业务开发前契约核对”；但不能直接把任何 planned 页面改为 implemented。建议施工顺序：

1. 教务工作台真实上下文与聚合接口；
2. 学年学期/培养方案/开课计划/教学任务；
3. 手工排课、冲突检测和课表发布；
4. 成绩录入→提交→审核→发布职责分离；
5. 学籍注册与异动状态机；
6. 考务、选课、教材、质量、统计归档依序补齐。

每个页面只有在真实前端、真实后端、MySQL、权限、数据范围、状态机、审计、测试和 build 全部满足后，才可从 planned/partial 改为 implemented。
