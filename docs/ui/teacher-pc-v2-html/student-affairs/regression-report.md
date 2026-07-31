# 学工中心原型回归记录

## 当前结论

状态：**15 页生产 routeName / 权限契约已逐页核对；13 页契约一致，2 页发现生产菜单与路由权限码冲突。4 个冻结缺口页历史三档回归 12/12 PASS；11 个关键工作台仍待浏览器回归。**

PR 继续保持 `IN_PROGRESS_NOT_FROZEN`。本报告不把静态核对、历史页面族回归或文件存在冒充为当前最终候选 HEAD 的全量冻结结果。

## 范围

- 学工关键工作台：11 页
- 学工冻结缺口：4 页
- 合计独立 HTML：15 页
- 最低三档回归量：`15 × 3 = 45`
- 修改范围：仅 `docs/ui/teacher-pc-v2-html/`

## 本轮生产事实核对

已读取并交叉核对：

- `frontend/src/config/navPlan.js`
- `frontend/src/modules/studentAffairs/studentAffairs.routes.js`
- `frontend/src/modules/student/student.routes.js`
- `frontend/src/modules/orientation/orientation.routes.js`
- `frontend/src/modules/campusService/campusService.routes.js`
- `manifest-parts/300-student-affairs-key.json`
- `manifest-parts/330-student-affairs-extension.json`

15 个 HTML 均已补齐或修正生产路由元数据：

- 学工总览：`student-affairs-dashboard`
- 学生360：入口 `student-list`、主档详情 `student-detail`、授权聚合详情 `student-affairs-profile-detail`
- 请假销假：`student-affairs-leave`
- 宿舍异常：`student-affairs-dorm-exception`
- 风险预警：`student-affairs-risk`
- 困难认定：`student-affairs-aid`
- 奖助发放：`student-affairs-funding`
- 违纪处分：`student-affairs-discipline`
- 心理关注：`student-affairs-mental`，危机页 `student-affairs-mental-crisis`
- 学工统计：`student-affairs-stats`，驾驶舱 `student-affairs-cockpit`
- 学工归档：`student-affairs-archive`，档案包 `student-affairs-archive-packages`
- 数字迎新：`orientation-dashboard`
- 班级管理：`campus-service-classes`
- 谈心谈话：`student-affairs-talk`
- 学生活动：`student-affairs-activity`

本轮还修复了 `difficulty-workbench.html` 原先完全缺失契约注释的问题，并为风险处置、统计、资助专项、心理明细等区分了“进入页面权限”和“执行高风险动作权限”。

## 生产阻断：菜单与路由权限不一致

### 1. 数字迎新

- `navPlan.js` 菜单权限：`studentAffairs.orientation.view`
- `/admin/orientation` 的真实路由守卫：`orientation.student.view`
- 结论：**不一致，未静默合并。**

原型与 Manifest 已同时登记两个事实源，并标记 `BLOCKED_MENU_ROUTE_PERMISSION_MISMATCH`。在生产侧选定唯一权威权限口径前，不能把数字迎新标记为权限契约冻结完成。

### 2. 班级管理

- `navPlan.js` 主入口权限：`studentAffairs.class.view`
- `/admin/campus-service/classes` 的真实路由守卫：`campus.record.view`
- 辅导员责任台账与考评分别使用 `studentAffairs.class.view`、`studentAffairs.counselorEval.view`
- 结论：**主入口不一致，覆盖的两个学工路由本身正常。**

原型与 Manifest 已标记 `BLOCKED_PRIMARY_MENU_ROUTE_PERMISSION_MISMATCH`。冻结前必须由生产代码后续施工选择统一权限，而不是由原型假定两个权限等价。

## 已完成浏览器回归

4 个冻结缺口页面此前已纳入“冻结缺口工作区”三档回归：

- 数字迎新
- 班级与辅导员
- 谈心谈话与家校协同
- 活动、第二课堂与社团

结果：

```text
4 页 × 3 档 = 12 / 12 PASS
```

这 4 页后续修改只发生在 HTML 注释和 Manifest 契约字段，不改变 DOM、共享 CSS、共享 JavaScript 或运行参数。最终候选 HEAD 仍需重新执行同源回归。

## 尚未执行浏览器回归

11 个关键工作台当前仍为：

```text
0 / 33 当前最终候选 HEAD 浏览器回归
```

包括：学工总览、学生360、请假销假、宿舍异常、风险处置、困难认定、奖助发放、违纪处分、心理危机、统计驾驶舱和学生档案包。

因此当前学工中心整体回归口径为：

```text
12 / 45 历史页面族 PASS
33 / 45 待执行
```

该 12 次已包含在全库累计 546 / 870 中，不能重复累加。

## 已确认业务红线

- 学工非管理角色未配置范围时 fail-closed，不回退全校；
- 学生主档是唯一身份事实源，学生360只聚合授权业务事实；
- 学生360完整字段与最小字段由生产权限分开控制；
- 心理明细、家庭联系人明文、困难材料、谈话原文和附件需要独立权限、用途和审计；
- 请假只允许当前审批节点操作，续假与销假追加历史而不覆盖原申请；
- 宿舍异常先记录客观事实并核验请假，不直接推定违纪；
- 风险心理来源默认只显示摘要，处置、升级、接管、关闭和重开不得跳节点；
- 困难认定的申请、公示、异议和最终认定保留版本；
- 奖助评审通过不等于资金已发放，失败、重试、部分成功和凭证必须留痕；
- 处分的事实、调查、送达、申诉、生效和解除是独立节点；
- 敏感统计执行最小样本保护，同筛选下钻不得扩大数据范围；
- 档案包只收录允许版本，下载要求权限、用途、脱敏、水印和审计；
- 报名、签到、活动结果、志愿时长、二课积分与组织任职保持独立事实。

## 下一步

1. 在完整分支快照中材料化 11 个关键工作台及共享 `v2-student-affairs-workbench.css/js`；
2. 先做 11 页单档冒烟，再执行 `11 × 3 = 33` 次回归；
3. 修复控制台、Promise、重复 ID、溢出、状态切换、弹层和焦点失败；
4. 最终候选 HEAD 重新执行全部 15 页 45 次回归；
5. 将数字迎新与班级管理的生产权限冲突作为明确阻断保留，直至生产施工阶段统一权限口径；
6. 全库 870 / 870、人工敏感业务检查和 G0–G7 全部通过后才允许记录冻结 HEAD。
