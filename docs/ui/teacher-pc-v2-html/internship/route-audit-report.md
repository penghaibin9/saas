# 岗位实习 101 叶子 / 99 URL 机器审计报告

## 最终机器结果

执行源 HEAD：`8344fbf496d14d0cd4e40a119e1de8a1dac72b45`

```text
secondLevelModules: 12 / 12
leafRoutes: 101 / 101
uniqueUrls: 99 / 99
sharedUrls: 2 / 2
uniqueOwners: 99 / 99
errors: 0
status: PASS
```

## 审计事实源

- 生产导航：`frontend/src/config/navPlan.js`
- 原型契约：`manifest-parts/310-internship-key.json`
- 审计工具：`tools/check-internship-route-audit.mjs`

## 审计范围

- 12 个生产二级模块；
- 101 个三级叶子；
- 99 个唯一 URL；
- 2 个显式共享 URL；
- URL 到 HTML owner 的唯一性；
- 权限候选和共享 owner 约束；
- 漏项、过时项和重复 owner。

## 原型组织方式

原型库使用 10 个关键工作台承载 12 个生产二级模块。该设计只合并原型展示壳，不改变生产菜单、路由、权限或业务状态机。

## 结果边界

机器审计证明生产导航投影与 Manifest 契约一致。岗位实习页面已经包含在全库 870 / 870 浏览器回归中，但打印、复杂宽表、连续键盘和敏感信息人工验收仍未完成。