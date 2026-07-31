# 岗位实习 101 叶子 / 99 URL 机器审计报告

## 审计事实源

- 生产导航来源：`frontend/src/config/navPlan.js`
- 生产导航读取 SHA：`7031fc39b2e93f0e976d4e9d2155a8f4ecad2162`
- 原型契约：`manifest-parts/310-internship-key.json`
- 审计方式：从 GitHub 当前 SHA 分别读取生产导航和原型契约，在隔离容器中解析、去重并对比 URL、权限和唯一 owner。

## 结果

| 项目 | 实际值 | 期望 | 结果 |
|---|---:|---:|---|
| 生产二级模块 | 12 | 12 | PASS |
| 生产三级叶子 | 101 | 101 | PASS |
| 生产唯一 URL | 99 | 99 | PASS |
| 显式共享 URL | 2 | 2 | PASS |
| Manifest owner 模块 | 12 | 12 | PASS |
| Manifest 已认领 URL | 99 | 99 | PASS |
| 已覆盖 URL | 99 | 99 | PASS |
| 重复 owner | 0 | 0 | PASS |
| 漏 URL | 0 | 0 | PASS |
| 过时 URL | 0 | 0 | PASS |
| 生产权限未进入 owner 契约 | 0 | 0 | PASS |

## 两个显式共享 URL

1. `/admin/internship/batches?panel=list`
   - 批次列表
   - 批次详情
2. `/admin/internship/students?panel=roster`
   - 实习名单
   - 学生实习详情

两组均为列表宿主页面进入详情，不是重复页面或漏路由。

## 模块分布

| 模块 | 三级叶子 | 唯一 URL |
|---|---:|---:|
| 实习工作台 | 5 | 5 |
| 批次与规则 | 8 | 7 |
| 实习学生 | 6 | 5 |
| 企业与岗位 | 10 | 10 |
| 匹配与分配 | 9 | 9 |
| 申请与协议 | 9 | 9 |
| 打卡与请假 | 9 | 9 |
| 周报与任务 | 8 | 8 |
| 指导与巡访 | 8 | 8 |
| 风险处置 | 11 | 11 |
| 评价与成绩 | 9 | 9 |
| 就业转化与归档统计 | 9 | 9 |

## 结论边界

本报告证明 `7031fc39...` 所读取的生产岗位实习导航与当前 `310-internship-key.json` 的 99 URL owner 契约一致。

本报告不替代：

- 最终冻结 HEAD 的再次执行；
- 290 个 HTML 的文件与相对资源检查；
- 870 次浏览器回归；
- 页面字段实际渲染、状态交互和 API 请求参数的浏览器/生产联调。

因此 PR #27 继续保持 Draft，原型状态继续保持 `IN_PROGRESS_NOT_FROZEN`。
