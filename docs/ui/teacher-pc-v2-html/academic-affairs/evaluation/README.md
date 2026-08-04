# 教学评价：开发还原契约

> 本目录是教师 PC V2 高保真 HTML 原型。生产权限、数据范围、任务生成、问卷、匿名聚合、权重、结果和申诉状态以后端为准。

## 已核准生产事实

- 生产路由：`aa-evaluation`
- 生产组件：`AaEvaluationConsoleView.vue`
- API 适配器：`academicAffairsEvaluationApi`
- 真实 Tab：`batches`、`appeals`、`studentEval`、`selfEval`、`peerEval`、`supervisorEval`、`evalStats`、`archive`
- 批次生命周期：`DRAFT → PUBLISHED → OPEN → CLOSED → RESULT_READY → ARCHIVED`
- 生产入口与权限以 `navPlan.js` 为准。

## 8 个真实入口

| 入口 | URL | 权限 | HTML |
|---|---|---|---|
| 评教批次 | `?tab=batches` | `academicAffairs.evaluation.view` | `evaluation-batches.html` |
| 申诉审核 | `?tab=appeals` | `academicAffairs.evaluation.view` | `evaluation-appeals.html` |
| 学生评教 | `?tab=studentEval` | `academicAffairs.evaluation.view` | `evaluation-student.html` |
| 教师自评 | `?tab=selfEval` | `academicAffairs.evaluation.selfEval.submit` | `evaluation-self.html` |
| 同行评价 | `?tab=peerEval` | `academicAffairs.evaluation.peerEval.submit` | `evaluation-peer.html` |
| 督导评价 | `?tab=supervisorEval` | `academicAffairs.evaluation.supervisorEval.submit` | `evaluation-supervisor.html` |
| 评价统计 | `?tab=evalStats` | `academicAffairs.evaluation.view` | `evaluation-stats.html` |
| 评价归档 | `?tab=archive` | `academicAffairs.evaluation.view` | `evaluation-archive.html` |

## 业务链

```text
创建批次并冻结规则
→ 从教学任务生成多角色评价任务
→ 学生 / 教师 / 同行 / 督导分别评价
→ 身份隔离、异常检测和匿名聚合
→ 按规则版本生成结果
→ 发布结果与反馈
→ 申诉复核和改进跟踪
→ 只读归档
```

## 关键边界

1. 学生填写入口在学生小程序；教师 PC 负责批次、任务、进度、匿名聚合、结果与申诉治理。
2. 任课教师不能查看学生个人答卷、未评学生名单或可反推身份的提交时间。
3. 匿名样本不足时不展示结果，不能解释为零分或低分。
4. 教师自评只覆盖本人教学任务，是独立来源。
5. 同行评价必须校验专业匹配、利益冲突和重复评价。
6. 督导评价区分观察事实与专业判断，严重问题进入教学质量整改。
7. 申诉不能修改原始答卷，只能追加复核结论与结果版本。
8. 评价结果用于教学改进，不生成简单公开教师排名。
9. 归档后的问卷、规则、聚合结果和申诉记录不可覆盖。

## 生产还原要求

- 读取 HTML `<head>` 的 route、routeName、permission、roles、states、privacy 和 boundary。
- 读取 `manifest-parts/180-evaluation.json` 的机器契约。
- 读取 `shared/v2-evaluation-workbench.js/css` 的离线结构与交互。
- 回到 `AaEvaluationConsoleView.vue`、`academicAffairsEvaluationApi` 和后端服务核对字段、数据范围、写权限、并发版本与审计。
- 原型中的中性数据、权重和匿名阈值不得直接写入生产常量。

历史 `student-evaluation / self-evaluation / peer-evaluation / supervisor-evaluation / evaluation-stats` query 及缺少 `evaluation.` 前缀的权限码已废止。
