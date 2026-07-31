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

## 工作区分布

| 中心 | 当前覆盖 | Manifest | 状态 |
|---|---:|---|---|
| 教务中心 | 27 工作区 | `00`–`220` | 结构缺口已补，浏览器与状态回归未完成 |
| 学工中心 | 15 工作区 | `300`、`330` | 主要生产工作区已进入追踪，浏览器与状态回归未完成 |
| 岗位实习中心 | 10 关键工作台覆盖 12 二级 | `310` | 99 URL 精确契约已重建，机器审计未执行 |
| 毕业设计中心 | 8 工作区 | `320` | 结构完成，浏览器与状态回归未完成 |

## 教务中心

生产导航继续按 29 个二级模块直接到达，禁止恢复第四级聚合分组。

本轮新增：

| 工作区 | 生产入口 | HTML | 关键边界 |
|---|---|---|---|
| 专业分流 | `/admin/academic-affairs/major-split` | `academic-affairs/major-split/major-split-workbench.html` | 试分不落库；待调剂和容量超限阻断确认；最终确认才写学籍专业 |
| 排课管理 | `/admin/academic-affairs/scheduling` | `academic-affairs/scheduling/scheduling-workbench.html` | 规则只影响自动排课；手工与导入结果不被覆盖；已发布/归档只读 |
| 课堂考勤 | `/admin/academic-affairs/attendance-stats` | `academic-affairs/attendance/attendance-stats.html` | PC 只统计移动端已提交场次，不提供逐生补点名 |

教务共 27 个首轮工作区，但“工作区结构完成”不等于所有生产叶子和状态已通过浏览器验收。

## 学工中心

原有 11 个关键页：学工总览、学生360、请假销假、宿舍异常、风险处置、困难认定、奖助发放、违纪处分、心理危机、统计驾驶舱、学生档案包。

本轮新增：

| 工作区 | 生产入口 | HTML | 关键边界 |
|---|---|---|---|
| 数字迎新 | `/admin/orientation` | `student-affairs/orientation-workbench.html` | 不复制学生主档；阻断项保留来源、责任、证据与补正历史 |
| 班级与辅导员 | `/admin/campus-service/classes` 等 | `student-affairs/class-counselor-workbench.html` | 未配置责任范围 fail-closed，不回退全校 |
| 谈心家校 | `/admin/student-affairs/talk` 等 | `student-affairs/talks-family-workbench.html` | 原文、联系人、附件和导出需独立权限、用途与审计 |
| 活动二课与社团 | `/admin/student-affairs/activity` 等 | `student-affairs/activities-workbench.html` | 报名、签到、结果、时长、积分、申诉和任职分开留痕 |

## 岗位实习中心

生产岗位实习组不是简单“99 个菜单项”：

- 12 个二级模块；
- 101 个三级叶子；
- 99 个唯一 URL；
- 2 个列表/详情共享 URL。

两组显式共享 URL：

1. `/admin/internship/batches?panel=list`：批次列表 / 批次详情；
2. `/admin/internship/students?panel=roster`：实习名单 / 学生实习详情。

`310-internship-key.json` 现已精确登记全部 99 URL，并按 12 个二级模块提供：

- 生产权限候选；
- 字段契约；
- 状态契约；
- API 参数契约；
- 唯一原型 owner。

最终冻结必须运行：

```bash
node tools/check-internship-route-audit.mjs \
  --report=/tmp/teacher-pc-v2-freeze/internship-route-audit.json
```

未实际执行前，不得宣称 99 URL 审计通过。

## 毕业设计中心

8 个工作区继续按生产 `GRADUATION_WORKSPACES` 一一对应：总览、选题、开题、过程、成果、答辩、成绩、归档统计。

## 程序化冻结检查

新增：

- `tools/check-prototype-consistency.mjs`
- `tools/check-internship-route-audit.mjs`
- `tools/run-browser-regression.mjs`
- `tools/README.md`

当前总量是 **290 个唯一 HTML**，三档基础回归为：

```text
290 × 3 = 870 次渲染
```

冻结通过条件至少包括：

- Manifest、HTML、CSS、JS 和相对资源存在性通过；
- 无未解释重复 route、孤儿 HTML、失效引用或目录越界；
- 岗位实习 101 叶子 / 99 URL / 2 别名审计 0 error；
- 870 / 870 浏览器渲染通过；
- 控制台、运行时、Promise、资源和样式错误为 0；
- 非预期根页面横向溢出为 0；
- 默认、加载、空、错误、403、只读、长数据状态通过；
- 弹层焦点进入、Tab 陷阱、Escape 和焦点归还通过；
- 打印和四中心业务红线通过。

## 当前判定

工具和契约已经落盘，但当前完整 HEAD 的真实执行报告尚未产生。因此：

- PR #27 保持 Draft；
- `prototype-manifest.json.status` 保持 `IN_PROGRESS_NOT_FROZEN`；
- 冻结 HEAD 不记录；
- 四条生产施工总控提示词不生成、不启用；
- 不同时开启四个生产修改窗口。
