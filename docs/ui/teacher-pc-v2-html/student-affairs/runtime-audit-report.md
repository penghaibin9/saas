# 学工 11 个关键工作台运行增强审计记录

## 审计目标

验证 11 个学工关键 HTML 是否一致加载运行增强层，并确保增强层持续修复图标路径、真实导航、按钮类型和对话框键盘焦点，不因后续并发提交而被漏接或覆盖。

## 事实源

- 页面清单：`manifest-parts/300-student-affairs-key.json`
- 运行增强层：`student-affairs/runtime-enhancements.js`
- 原共享脚本：`shared/v2-student-affairs-workbench.js`
- 审计工具：`tools/check-student-affairs-runtime-audit.mjs`

## 固定检查量

| 项目 | 期望 |
|---|---:|
| 300 Manifest 条目 | 11 |
| 唯一关键 HTML | 11 |
| 正确接入增强层的 HTML | 11 |
| 真实左侧模块入口 | 14 |

## 审计内容

工具检查：

1. `300-student-affairs-key.json` 必须保持 11 个条目和 11 个唯一 HTML；
2. 11 个 HTML 必须存在于原型目录内；
3. 每页必须引用 `runtime-enhancements.js`；
4. 每页增强层必须先于 `../shared/v2-student-affairs-workbench.js` 加载；
5. 增强层 JavaScript 必须通过语法解析；
6. 必须把错误图标路径 `../../shared/icons.svg#` 修正为 `../shared/icons.svg#`；
7. 必须为无 `type` 按钮补 `type="button"`；
8. 必须为左侧模块补真实 `href` 与 `data-production-route`；
9. 14 个模块标签与生产入口必须完全匹配；
10. 对话框必须具备标题关联、打开按钮追踪、焦点进入、首个控件聚焦、Tab 陷阱、Escape 顶层关闭、遮罩关闭和焦点归还；
11. 不得出现过时或额外路由映射。

## 14 个固定生产入口

| 模块 | 入口 |
|---|---|
| 学工工作台 | `/admin/student-affairs/dashboard` |
| 学生主档 | `/admin/student/list` |
| 班级与辅导员 | `/admin/campus-service/classes` |
| 数字迎新 | `/admin/orientation` |
| 请假销假 | `/admin/student-affairs/leave` |
| 宿舍与公寓 | `/admin/student-affairs/dorm/exception` |
| 风险预警与处置 | `/admin/student-affairs/risk` |
| 困难认定 | `/admin/student-affairs/aid` |
| 奖助勤贷补 | `/admin/student-affairs/funding` |
| 违纪处分 | `/admin/student-affairs/discipline` |
| 谈心谈话与家校协同 | `/admin/student-affairs/talk` |
| 心理关注 | `/admin/student-affairs/mental` |
| 活动与第二课堂 | `/admin/student-affairs/activity` |
| 统计与档案 | `/admin/student-affairs/stats` |

宿舍入口明确使用已存在的异常工作台 `/admin/student-affairs/dorm/exception`，不制造不存在的 `/admin/student-affairs/dorm` 路由。

## 当前验证边界

当前已完成：

- 11 个关键 HTML 已逐页接入增强层；
- 增强层位于原共享脚本之前；
- 增强层写入前完成 JavaScript 语法检查；
- 运行审计工具已落盘，检查项和固定入口已冻结。

当前尚未在完整真实 PR 分支快照中执行：

```bash
node tools/check-student-affairs-runtime-audit.mjs \
  --report=/tmp/teacher-pc-v2-freeze/student-affairs-runtime-audit.json
```

也尚未执行真实浏览器：

```bash
node tools/run-page-family-regression.mjs \
  --family=student-affairs-key \
  --report-dir=/tmp/teacher-pc-v2-freeze/student-affairs-key
```

因此当前不能宣称：

- 当前完整 HEAD 的运行审计已经 PASS；
- 图标、链接和焦点行为已在 Chrome 中通过；
- 学工 33 / 33 浏览器回归通过；
- 学工中心已经冻结。

## 最终通过条件

完整真实分支运行审计必须得到：

- Manifest 11 / 11；
- HTML 11 / 11；
- 正确加载顺序 11 / 11；
- 生产入口 14 / 14；
- 脚本语法错误 0；
- 缺失标记 0；
- 过时路由 0；
- 总错误 0。

随后还必须完成 11 页 × 3 档 = 33 次真实 Chrome / Chromium 回归，重点验证 SVG 实际加载、左侧键盘导航、弹层焦点进入、Tab / Shift+Tab、Escape、遮罩关闭与焦点归还。
