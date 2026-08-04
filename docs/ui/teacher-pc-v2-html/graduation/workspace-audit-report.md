# 毕业设计 8 工作区 / 50 叶子机器审计记录

## 最终机器结果

执行源 HEAD：`8344fbf496d14d0cd4e40a119e1de8a1dac72b45`

```text
workspaceCount: 8
leafCount: 50
uniqueUrlCount: 48
sharedUrlCount: 2
htmlOwnerCount: 8
errors: 0
status: PASS
```

## 审计目标

验证毕业设计 HTML 原型的工作区投影与生产单一事实源一致，避免再次把生命周期概念分组误写成生产导航结构。

## 事实源

- 生产工作区：`frontend/src/modules/graduation/config/graduationWorkspaces.js`
- 原型契约：`manifest-parts/320-graduation.json`
- 审计工具：`tools/check-graduation-workspace-audit.mjs`

## 核对范围

- 8 个 workspace key 与名称；
- 每个工作区主入口；
- 全部 `coveredRoutes`；
- 50 个三级叶子；
- 48 个唯一 URL；
- 2 个共享 URL；
- 权限候选覆盖；
- 8 个 HTML 存在性和唯一 owner；
- 过时路由、漏项和错误共享 owner。

## 现行工作区

1. 我的工作台
2. 批次与实施
3. 题目与选题
4. 过程指导
5. 开题与成果
6. 答辩与成绩
7. 风险与归档
8. 模板与设置

## 结果边界

该审计证明生产导航投影与原型契约一致。它不替代打印、连续键盘、敏感业务和跨浏览器人工验收。