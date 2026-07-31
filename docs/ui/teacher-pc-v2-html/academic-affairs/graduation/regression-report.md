# 毕业资格审核原型回归记录

## 范围

- 独立 HTML：15
- 共享工作台脚本：1
- 模块样式：1
- 机器 Manifest：1
- 修改范围：仅 `docs/ui/teacher-pc-v2-html/`

## 历史快速浏览器回归

历史等价材料化回归共 23 次渲染，记录结果为 0 失败，覆盖预审、费用、终审、证书、菜单、页签、面包屑、默认/加载/空/错误/403/只读/长数据和根页面溢出。

该历史结果只用于证明早期模块结构可打开，**不等于当前冻结候选 HEAD 的三档全量回归**。

## 本轮生产事实核准

已读取并对齐：

- `academic-affairs.routes.js`：`aa-graduation`、`aa-graduation-audit-console`、`aa-certificates`
- `navPlan.js`：15 个精确入口和查看、终审、归档、证书权限
- `AaGraduationBatchView.vue`：预审与审核批次
- `AaGraduationAuditConsoleView.vue`：十项供数、课程/学分/实践、跨域联动、终审、结果和归档
- `AaCertificateView.vue`：证书生命周期
- `academic-affairs.api.js`：生产 API 适配器

本轮修复：

- 15 页真实 `routeName`；
- 预审权限由待核对改为 `academicAffairs.graduation.view`；
- 终审、归档和证书权限保持生产专用权限；
- `150-graduation.json` 与 15 个 HTML 同步；
- 费用 UNKNOWN / 软提醒 / 不阻断边界继续保留。

## 仍需冻结回归

- 当前完整 HEAD 的文件与相对资源检查；
- 15 页纳入 290 × 3 浏览器全量回归；
- 十项来源证据、终审、学籍终态、归档和证书动作的生产联调；
- 键盘、焦点、Escape、焦点归还与打印检查。

## 当前结论

毕业资格审核历史 `to verify` 和权限待核对阻断已解除；模块仍随整个原型库保持 `IN_PROGRESS_NOT_FROZEN`，不得用历史 23 次回归替代当前 870 次冻结回归。
