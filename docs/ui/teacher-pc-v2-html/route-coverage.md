# 路由覆盖

> 本文件是设计交付清单，不取代生产路由、菜单、权限或后端事实源。机器追溯见 `prototype-manifest.json` 与 `manifest-parts/*.json`。

## 当前统计

- Manifest 条目：**297**
- 独立 HTML：**290**
- 共享 HTML 路由条目：**9**
- 共享设计文件：**43**
- 首轮工作区：**60**
- 一级中心完整冻结：**0**
- 仓库截图：**0**
- 历史本地截图记录：**309**
- 当前累计浏览器回归：**546 / 870 PASS，182 / 290 页**
- 当前 PR 文件边界：**全部变更文件均位于 `docs/ui/teacher-pc-v2-html/`**

## 工作区分布

| 中心 | 当前覆盖 | Manifest | 当前状态 |
|---|---:|---|---|
| 教务中心 | 27 工作区 | `00`–`220` | 多页面族已回归，最终候选 HEAD 全量重跑未完成 |
| 学工中心 | 15 工作区 | `300`、`330` | 15 页契约已核对；13 页一致，2 页发现生产权限冲突；11 页浏览器回归待执行 |
| 岗位实习中心 | 10 关键工作台覆盖 12 二级 | `310` | 101 叶子 / 99 URL 来源审计仍有效；最终 HEAD 待重跑 |
| 毕业设计中心 | 8 工作区 | `320` | 生产现行 8 / 50 / 48 / 2 已重建；审计脚本夹具 PASS；真实分支与浏览器待执行 |

## 教务中心

生产导航继续按 29 个二级模块直接到达，禁止恢复第四级聚合分组。

冻结缺口页：

| 工作区 | 生产入口 | HTML | 关键边界 |
|---|---|---|---|
| 专业分流 | `/admin/academic-affairs/major-split` | `academic-affairs/major-split/major-split-workbench.html` | 试分不落库；待调剂和容量超限阻断确认；最终确认才写学籍专业 |
| 排课管理 | `/admin/academic-affairs/scheduling` | `academic-affairs/scheduling/scheduling-workbench.html` | 规则只影响自动排课；手工与导入结果不被覆盖；已发布 / 归档只读 |
| 课堂考勤 | `/admin/academic-affairs/attendance-stats` | `academic-affairs/attendance/attendance-stats.html` | PC 只统计移动端已提交场次，不提供逐生补点名 |

近期页面族回归：

- 毕业资格审核：15 页，45 / 45 PASS；
- 教务归档：4 页，12 / 12 PASS；
- 教务统计：15 页，45 / 45 PASS，routeName / 权限元数据 15 / 15 收口。

以上结果仍需纳入最终候选 HEAD 的 870 次统一回归。

## 学工中心

学工中心共 15 个独立 HTML：

- 11 个关键工作台：学工总览、学生360、请假销假、宿舍异常、风险处置、困难认定、奖助发放、违纪处分、心理危机、统计驾驶舱、学生档案包；
- 4 个冻结缺口工作台：数字迎新、班级与辅导员、谈心家校、活动二课与社团。

15 页生产 routeName、进入权限、动作权限、数据范围和敏感字段边界已完成静态核对。发现两个生产事实冲突：

1. 数字迎新：菜单权限 `studentAffairs.orientation.view`，真实 `/admin/orientation` 路由守卫 `orientation.student.view`；
2. 班级管理：菜单权限 `studentAffairs.class.view`，真实 `/admin/campus-service/classes` 路由守卫 `campus.record.view`。

原型和 `330-student-affairs-extension.json` 已分别登记菜单权限与路由权限，不把它们静默视为别名。4 个冻结缺口页历史三档回归 12 / 12 PASS；11 个关键页仍待 33 次回归。

## 岗位实习中心

生产岗位实习组实际为：

- 12 个二级模块；
- 101 个三级叶子；
- 99 个唯一 URL；
- 2 个列表 / 详情共享 URL。

两组显式共享 URL：

1. `/admin/internship/batches?panel=list`：批次列表 / 批次详情；
2. `/admin/internship/students?panel=roster`：实习名单 / 学生实习详情。

`310-internship-key.json` 精确登记全部 99 URL，并按 12 个二级模块提供生产权限候选、字段、状态、API 参数和唯一原型 owner。

来源 SHA `7031fc39...` 的机器审计已实际通过：

- 12 / 12 二级模块；
- 101 / 101 三级叶子；
- 99 / 99 唯一 URL；
- 2 / 2 显式别名；
- 99 / 99 唯一 owner；
- 漏 URL、过时 URL、重复 owner 和权限缺失：0。

2026-07-31 再次比较后确认：自原审计起，生产 `navPlan.js` 与 `310-internship-key.json` 两个审计输入均未变化，因此原 PASS 仍适用于当前契约。该结论不是新的脚本运行，最终候选 HEAD 仍必须重跑。

## 毕业设计中心

### 现行生产结构

当前生产 `GRADUATION_WORKSPACES` 为：

| 工作区 | 主入口 | HTML |
|---|---|---|
| 我的工作台 `gd-workbench` | `/admin/graduation` | `graduation/overview.html` |
| 批次与实施 `gd-batch-impl` | `/admin/graduation/batches?panel=list` | `graduation/batch-implementation.html` |
| 题目与选题 `gd-topic-select` | `/admin/graduation/topic-lib` | `graduation/topic.html` |
| 过程指导 `gd-process` | `/admin/graduation/process?panel=taskbook` | `graduation/process.html` |
| 开题与成果 `gd-proposal-final` | `/admin/graduation/proposals` | `graduation/proposal-final.html` |
| 答辩与成绩 `gd-defense` | `/admin/graduation/defense` | `graduation/defense.html` |
| 风险与归档 `gd-risk-archive` | `/admin/graduation/risk-archive?panel=risk` | `graduation/risk-archive.html` |
| 模板与设置 `gd-templates` | `/admin/graduation/templates` | `graduation/templates.html` |

生产量级：

- 8 个工作区；
- 50 个三级叶子；
- 48 个唯一 URL；
- 2 个显式共享 URL：`defense-scoring`、`stats-report`。

### 本轮纠偏

原型旧版错误地按“总览、选题、开题、过程、成果、答辩、成绩、归档统计”组织。该拆法已全部撤销：

- 新建现行“批次与实施、开题与成果、风险与归档、模板与设置”；
- 重定义“我的工作台、题目与选题、过程指导、答辩与成绩”；
- 删除旧独立“开题、成果、成绩、归档统计”文件；
- 重建 `320-graduation.json` 与共享 JavaScript；
- 独立 HTML 数量仍为 8，全库总数仍为 290。

### 机器审计

新增 `tools/check-graduation-workspace-audit.mjs` 与 `graduation/workspace-audit-report.md`。工具检查：

- 8 个 workspace key、名称和主入口；
- 50 个生产叶子与 48 个唯一 URL；
- 两个共享 URL 及 owner；
- 每个工作区 `coveredRoutes` 与生产权限覆盖；
- 8 个 HTML 的存在性与唯一 owner；
- 字段、状态和业务边界；
- 漏项、过时项和错误共享关系。

当前工具语法检查 PASS，隔离同构夹具得到 8 / 50 / 48 / 2、8 HTML、0 error PASS。完整真实 PR 分支尚未执行，因此当前 8 页仍只完成静态结构与契约重建，浏览器回归仍为 0 / 24。

## 程序化冻结检查

工具：

- `tools/check-prototype-consistency.mjs`
- `tools/check-internship-route-audit.mjs`
- `tools/check-graduation-workspace-audit.mjs`
- `tools/run-browser-regression.mjs`
- `tools/README.md`

当前总量是 **290 个唯一 HTML**，三档基础回归为：

```text
290 × 3 = 870 次渲染
```

最终冻结条件至少包括：

- Manifest、HTML、CSS、JavaScript 和相对资源存在性通过；
- 无未解释重复 route、孤儿 HTML、失效引用或目录越界；
- 最终候选 HEAD 的岗位实习 101 叶子 / 99 URL / 2 别名审计 0 error；
- 最终候选 HEAD 的毕业设计 8 工作区 / 50 叶子 / 48 URL / 2 共享 URL 审计 0 error；
- 870 / 870 浏览器渲染通过；
- 控制台、运行时、Promise、资源和样式错误为 0；
- 非预期根页面横向溢出为 0；
- 默认、加载、空、错误、403、只读和长数据状态通过；
- 弹层焦点进入、Tab 陷阱、Escape 和焦点归还通过；
- 打印和四中心业务红线通过。

## 当前判定

当前累计回归为 546 / 870，但毕业设计刚完成生产工作区结构纠偏，学工仍有 33 次页面回归与两个生产权限阻断，全库最终候选 HEAD 报告也尚未产生。因此：

- PR #27 保持 Draft；
- `prototype-manifest.json.status` 保持 `IN_PROGRESS_NOT_FROZEN`；
- 冻结 HEAD 不记录；
- 四条生产施工总控提示词不生成、不启用；
- 不同时开启四个生产修改窗口。
