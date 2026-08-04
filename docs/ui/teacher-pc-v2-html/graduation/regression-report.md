# 毕业设计原型回归记录

## 当前结论

- 生产现行工作区：**8 / 8**
- 独立 HTML：**8 / 8**
- 三档浏览器回归：**24 / 24 PASS**
- 执行源 HEAD：`8344fbf496d14d0cd4e40a119e1de8a1dac72b45`
- 状态：**结构纠偏和机器回归通过，仍未冻结**

## 现行 8 工作区

1. 我的工作台 `gd-workbench`
2. 批次与实施 `gd-batch-impl`
3. 题目与选题 `gd-topic-select`
4. 过程指导 `gd-process`
5. 开题与成果 `gd-proposal-final`
6. 答辩与成绩 `gd-defense`
7. 风险与归档 `gd-risk-archive`
8. 模板与设置 `gd-templates`

旧生命周期拆法“总览、选题、开题、过程、成果、答辩、成绩、归档统计”已撤销，不再冒充生产 `GRADUATION_WORKSPACES`。

## 生产投影

- 工作区：**8**
- 三级叶子：**50**
- 唯一 URL：**48**
- 共享 URL：**2**
  - `defense-scoring`
  - `stats-report`

## 机器审计

`tools/check-graduation-workspace-audit.mjs` 在完整执行源 HEAD 上通过：

```text
workspaceCount: 8
leafCount: 50
uniqueUrlCount: 48
sharedUrlCount: 2
htmlOwnerCount: 8
errors: 0
```

审计覆盖 workspace key、名称、主入口、coveredRoutes、权限候选、共享 URL、HTML 存在性和唯一 owner。

## 浏览器回归

三档桌面视口：

- `1280 × 900`
- `1440 × 1000`
- `1920 × 1080`

结果：**24 / 24 PASS**。

## 尚未完成

自动回归不替代：

- 成果材料超长文件名与大批量列表；
- 答辩评分连续键盘操作；
- 风险与归档敏感数据人工验收；
- 打印页、复杂宽表和 Windows Chrome / Edge 复核。

PR 继续保持 `IN_PROGRESS_NOT_FROZEN` 和 Draft。