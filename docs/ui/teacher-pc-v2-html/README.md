# 教师/学校管理 PC 端 V2 高保真 HTML 原型库

本目录是教师/学校管理 PC 端设计交付物，不是生产菜单、路由或运行时代码。

## 边界

- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 状态：**IN PROGRESS / NOT FROZEN**
- 生产代码修改：**否**
- 所有修改仅允许位于本目录
- Manifest 只用于设计追溯，不取代生产路由、权限、API 或后端状态机
- 原型数据均为中性 placeholder

## 当前真实规模

- Manifest 路由 / 业务切面：**297**
- 独立 HTML：**290**
- 共享 HTML 路由条目：**9**
- 共享设计文件：**43**
- 首轮工作区：**60**
- 完整冻结一级中心：**0**
- 仓库截图：**0**
- 已记录历史本地渲染截图：**309**
- 累计浏览器回归：**546 / 870 PASS，182 / 290 页**

工作区分布：

- 教务中心：**27**
- 学工中心：**15**
- 岗位实习中心关键工作台：**10**，覆盖 12 个生产二级模块
- 毕业设计中心：**8**

总 Manifest 当前聚合：

- 教务：`00`–`220`
- 学工：`300`、`330`
- 岗位实习：`310`
- 毕业设计：`320`

此前出现过的 175 / 169 / 17 / 15、290 / 283 / 41 / 53、849 次回归均为历史口径，不得继续引用。

## 导航规范

Teacher PC V2 信息架构固定为：

**顶部一级中心 → 左侧真实二级模块 → 内容区三级功能**

禁止恢复第四级业务聚合菜单。权限、角色、数据范围、状态机和 API 继续由生产代码与后端裁决。

## 四个重点中心

### 教务中心 · 27 工作区

除既有成绩、学籍、注册、培养方案、课程、教学任务、课表、调停课、选课、考务、补考重修、预警、毕业资格、教材、资源、评价、质量、归档和统计外，已补齐：

- 专业分流：`academic-affairs/major-split/major-split-workbench.html`
- 排课管理：`academic-affairs/scheduling/scheduling-workbench.html`
- 课堂考勤：`academic-affairs/attendance/attendance-stats.html`

事实边界：专业分流试分不落库；排课规则不覆盖手工结果；课堂考勤 PC 只统计移动端已提交场次，不提供逐生补点名。

近期已回归：毕业资格 45 / 45、教务归档 12 / 12、教务统计 45 / 45。最终候选 HEAD 仍需统一重跑。

### 学工中心 · 15 工作区

11 个关键页：学工总览、学生360、请假销假、宿舍异常、风险处置、困难认定、奖助发放、违纪处分、心理危机、统计驾驶舱、学生档案包。

4 个冻结缺口页：数字迎新、班级与辅导员、谈心家校、活动二课与社团。

15 页 routeName、权限、数据范围和敏感字段边界已核对；13 页一致，2 页存在生产菜单与真实路由守卫权限冲突：

- 数字迎新：`studentAffairs.orientation.view` / `orientation.student.view`；
- 班级管理：`studentAffairs.class.view` / `campus.record.view`。

原型不把不同权限码静默视为别名。4 个冻结缺口页历史回归 12 / 12；11 个关键页仍待 33 次回归。

### 岗位实习中心 · 10 个关键工作台

10 个 HTML 覆盖 12 个生产二级模块。生产导航实际为：

- **101 个三级叶子**
- **99 个唯一 URL**
- **2 个显式共享 URL**：批次列表 / 详情、实习名单 / 学生详情

`310-internship-key.json` 已登记精确生产 URL，并为 12 个模块登记字段、状态和 API 参数契约。来源 SHA 的机器审计实际通过；比较确认生产 `navPlan.js` 与 310 Manifest 输入此后未变化。最终冻结 HEAD 仍必须重新执行 `tools/check-internship-route-audit.mjs`。

### 毕业设计中心 · 8 工作区

当前严格对应生产 `GRADUATION_WORKSPACES`：

1. 我的工作台 `gd-workbench`
2. 批次与实施 `gd-batch-impl`
3. 题目与选题 `gd-topic-select`
4. 过程指导 `gd-process`
5. 开题与成果 `gd-proposal-final`
6. 答辩与成绩 `gd-defense`
7. 风险与归档 `gd-risk-archive`
8. 模板与设置 `gd-templates`

生产量级为 **50 个三级叶子、48 个唯一 URL、2 个显式共享 URL**。旧的“总览、选题、开题、过程、成果、答辩、成绩、归档统计”拆法已撤销，8 个 HTML、320 Manifest 和共享 JavaScript 已重建。重映射后浏览器回归仍为 0 / 24。

## 一致性与浏览器工具

- `tools/check-prototype-consistency.mjs`：Manifest、文件、孤儿 HTML、重复路由、共享资源和相对引用检查。
- `tools/check-internship-route-audit.mjs`：岗位实习 101 叶子 / 99 URL / 权限 / 字段 / 状态 / API 参数检查。
- `tools/run-browser-regression.mjs`：Chrome / Chromium 三档分辨率全量回归。
- `tools/README.md`：可重复执行命令。

工具落盘不等于最终候选 HEAD 已经执行通过。当前连接器可读写 GitHub，但执行容器无法解析 GitHub 域名，不能直接取得完整分支快照。

## 当前冻结阻断

当前 **290 个 HTML** 尚未在同一最终候选 HEAD 下完成全量浏览器回归：

```text
290 × 3 = 870 次渲染
```

当前累计：

```text
546 / 870 PASS
182 / 290 页
```

尚未完成：

- 最终候选 HEAD 的 Manifest / 文件 / 相对资源一致性真实执行；
- 学工 11 页 33 次回归；
- 毕业设计现行 8 页 24 次回归；
- 岗位实习最终 HEAD 101 叶子 / 99 URL 重跑；
- 剩余 108 页、324 次浏览器回归；
- 默认、加载、空、错误、403、只读、长数据和高风险状态复核；
- 打印页、键盘、焦点、Escape、焦点归还和业务红线最终验收；
- 学工两个生产权限冲突的生产裁决。

因此：

- `prototype-manifest.json.status` 保持 `IN_PROGRESS_NOT_FROZEN`；
- PR #27 保持 Draft；
- 不记录冻结 HEAD；
- 不生成或启用四条生产施工总控提示词；
- 不同时开启四个生产修改窗口。
