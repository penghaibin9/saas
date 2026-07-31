# 学工 11 个关键工作台运行增强审计记录

## 最终机器结果

执行源 HEAD：`8344fbf496d14d0cd4e40a119e1de8a1dac72b45`

```text
manifestRows: 11
uniqueHtmlFiles: 11
wiredHtmlFiles: 11
expectedRoutes: 14
errors: 0
status: PASS
```

## 审计目标

验证 11 个学工关键 HTML 是否一致加载运行增强层，并确保增强层持续修复：

- SVG 图标相对路径；
- 14 个真实生产侧栏入口；
- 无类型按钮；
- 对话框标题关联；
- 首个可操作控件焦点；
- Tab / Shift+Tab 焦点陷阱；
- Escape 顶层关闭；
- 遮罩关闭；
- 关闭后的焦点归还。

## 事实源

- 页面清单：`manifest-parts/300-student-affairs-key.json`
- 运行增强层：`student-affairs/runtime-enhancements.js`
- 审计工具：`tools/check-student-affairs-runtime-audit.mjs`

## 加载顺序

11 / 11 HTML 均满足：

```html
<script src="runtime-enhancements.js"></script>
<script src="../shared/v2-student-affairs-workbench.js"></script>
```

增强层必须先加载，以便在主脚本渲染后统一修正运行 DOM。

## 生产入口

审计固定核对 14 个入口：学工总览、学生主档、班级、迎新、请假、宿舍异常、风险、困难认定、奖助、处分、谈心家校、心理、活动和统计。

宿舍入口保持真实 `/admin/student-affairs/dorm/exception`，未制造不存在的 `/admin/student-affairs/dorm`。

## 结果边界

机器审计和学工 45 / 45 浏览器回归均已通过，但连续键盘、多层弹层、视觉焦点和敏感业务字段仍需人工验收。