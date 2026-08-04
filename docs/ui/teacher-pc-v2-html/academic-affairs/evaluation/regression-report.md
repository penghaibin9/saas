# 教学评价原型回归记录

## 范围

- 独立 HTML：8
- 共享工作台脚本：1
- 模块样式：1
- 机器 Manifest：1
- 修改范围：仅 `docs/ui/teacher-pc-v2-html/`

## 历史快速浏览器回归

历史等价材料化回归共 16 次渲染，记录结果为 0 失败，覆盖菜单、页签、面包屑、匿名提示、默认/加载/空/错误/403/只读/长数据和根页面溢出。

该历史结果只用于证明早期模块结构可打开，**不等于当前冻结候选 HEAD 的三档全量回归**。

## 本轮生产事实核准

已读取并对齐：

- `academic-affairs.routes.js`：路由名 `aa-evaluation`
- `navPlan.js`：8 个精确 URL 与权限
- `AaEvaluationConsoleView.vue`：8 个真实 Tab key、批次生命周期、任务、统计、归档与申诉交互
- `academicAffairsEvaluationApi`：生产 API 适配器

本轮修复：

- 5 个旧 query key 改为 `studentEval / selfEval / peerEval / supervisorEval / evalStats`；
- 教师自评、同行评价、督导评价权限补齐 `academicAffairs.evaluation.` 前缀；
- 学生评教查看权限改为生产 `academicAffairs.evaluation.view`；
- 8 页 `routeName` 统一为 `aa-evaluation`；
- `180-evaluation.json` 与 8 个 HTML 同步。

## 仍需冻结回归

- 当前完整 HEAD 的文件与相对资源检查；
- 8 页纳入 290 × 3 浏览器全量回归；
- 匿名最小样本、角色隔离、写权限、并发版本和申诉更正事务的生产联调；
- 键盘、焦点、Escape、焦点归还与打印检查。

## 当前结论

教学评价历史 `to verify` 元数据阻断已解除；模块仍随整个原型库保持 `IN_PROGRESS_NOT_FROZEN`，不得用历史 16 次回归替代当前 870 次冻结回归。
