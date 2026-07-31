# 学工运行审计工具隔离夹具结果

## 目的

验证 `tools/check-student-affairs-runtime-audit.mjs` 自身能够解析学工运行增强层、检查 11 个页面接入顺序、核准 14 个生产入口并生成机器报告。

## 夹具结构

隔离目录按真实相对关系构造：

```text
student-affairs-runtime-fixture/
├── tools/check-student-affairs-runtime-audit.mjs
├── manifest-parts/300-student-affairs-key.json
├── student-affairs/runtime-enhancements.js
└── student-affairs/*.html × 11
```

11 个 HTML 均以真实接入顺序加载：

```html
<script src="runtime-enhancements.js"></script>
<script src="../shared/v2-student-affairs-workbench.js"></script>
```

运行增强层使用当前 14 个生产入口、图标路径修正、按钮类型、标题关联、首控件焦点、Tab 陷阱、Escape 顶层关闭、遮罩关闭和焦点归还逻辑。

## 已执行

### 1. 工具语法

```bash
node --check tools/check-student-affairs-runtime-audit.mjs
```

结果：**PASS**。

### 2. 隔离同构审计

```bash
node tools/check-student-affairs-runtime-audit.mjs \
  --report=/tmp/student-affairs-runtime-fixture/report.json
```

结果：

```text
manifestRows: 11
uniqueHtmlFiles: 11
wiredHtmlFiles: 11
expectedRoutes: 14
errors: 0
```

结论：**FIXTURE PASS**。

## 结论边界

该结果证明：

- 审计工具 JavaScript 语法有效；
- 能正确聚合 300 Manifest；
- 能识别 11 个 HTML 的增强层引用和加载顺序；
- 能核准 14 个固定生产入口；
- 能检查图标、按钮、对话框标题和焦点闭环标记；
- 能输出 JSON 报告并在错误时退出非零状态。

该结果不证明：

- 当前完整 GitHub PR HEAD 已运行审计；
- 真实 11 个 HTML 在 Chrome 中已通过；
- SVG 资源请求、侧栏跳转、Tab、Escape 和焦点归还已完成浏览器验证；
- 学工 33 / 33 或全库 870 / 870 已通过。

最终冻结仍需在完整真实分支快照中执行同一工具，并运行 `--family=student-affairs-key` 的 33 次 Chrome / Chromium 回归。
