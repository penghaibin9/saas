# 学工中心原型回归记录

## 当前结论

- 独立 HTML：**15**
- 三档浏览器回归：**45 / 45 PASS**
- 其中 11 个关键工作台：**33 / 33 PASS**
- 4 个冻结缺口页：**12 / 12 PASS**
- 执行源 HEAD：`8344fbf496d14d0cd4e40a119e1de8a1dac72b45`
- 状态：**机器回归通过，仍未冻结**

## 运行增强层

11 个关键工作台均在学工共享主脚本之前加载：

```html
<script src="runtime-enhancements.js"></script>
<script src="../shared/v2-student-affairs-workbench.js"></script>
```

增强层负责：

- 修正从 `student-affairs/*.html` 解析的 SVG 图标路径；
- 给 14 个学工模块补真实生产 `href` 与追溯字段；
- 给无类型按钮补 `type="button"`；
- 对话框标题关联；
- 打开后聚焦首个可操作控件；
- Tab / Shift+Tab 限制在顶层对话框；
- Escape 只关闭顶层对话框；
- 点击遮罩关闭；
- 关闭后焦点归还原触发按钮。

## 机器审计

`tools/check-student-affairs-runtime-audit.mjs` 在完整执行源 HEAD 上通过：

```text
manifestRows: 11
uniqueHtmlFiles: 11
wiredHtmlFiles: 11
expectedRoutes: 14
errors: 0
```

## 生产契约核对

15 / 15 页已登记 routeName、入口权限、动作权限、数据范围和敏感字段边界：

- 13 页契约一致；
- 2 页存在生产菜单与真实路由守卫权限冲突。

明确阻断：

1. 数字迎新：菜单 `studentAffairs.orientation.view`，路由守卫 `orientation.student.view`；
2. 班级管理：菜单 `studentAffairs.class.view`，主路由守卫 `campus.record.view`。

原型不把不同权限码静默视为别名，也不在本 PR 修改生产权限实现。

## 自动回归边界

45 / 45 已验证页面可渲染、脚本无运行错误、基础状态和基础弹层交互可用。以下仍需人工专项：

- 连续键盘操作与多层弹层焦点；
- 敏感字段逐角色最小可见；
- 打印与复杂宽表；
- Windows Chrome / Edge 视觉复核。

因此 PR 继续保持 `IN_PROGRESS_NOT_FROZEN` 和 Draft。