# 毕业资格审核：开发还原契约

> 本目录是教师 PC V2 高保真 HTML 原型。生产权限、跨域证据、规则、数据范围、接口和状态以后端为准。

## 已核准生产事实

- 预审与审核批次路由：`aa-graduation`，组件 `AaGraduationBatchView.vue`
- 十项审核控制台路由：`aa-graduation-audit-console`，组件 `AaGraduationAuditConsoleView.vue`
- 证书路由：`aa-certificates`，组件 `AaCertificateView.vue`
- API：`academic-affairs.api.js` 中毕业资格相关适配器
- 入口 URL 与权限：生产 `navPlan.js`
- 费用来源当前未接入完整财务系统，保持 `UNKNOWN` 软提醒，不阻断学业结论。

## 15 个真实入口

| 入口 | 路由名 | 权限 | HTML |
|---|---|---|---|
| 毕业资格预审 | `aa-graduation` | `academicAffairs.graduation.view` | `graduation-precheck.html` |
| 审核批次 | `aa-graduation` | `academicAffairs.graduation.view` | `graduation-batches.html` |
| 毕业学生名单 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-roster.html` |
| 学分达成审核 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-credit.html` |
| 课程达成审核 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-course.html` |
| 实践环节审核 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-practice.html` |
| 毕设状态联动 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-thesis.html` |
| 实习状态联动 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-internship.html` |
| 费用结清 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-fee.html` |
| 处分状态联动 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-discipline.html` |
| 毕业资格终审 | `aa-graduation-audit-console` | `academicAffairs.graduation.final` | `graduation-final.html` |
| 不通过原因 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-reasons.html` |
| 审核结果 | `aa-graduation-audit-console` | `academicAffairs.graduation.view` | `graduation-results.html` |
| 毕业证书管理 | `aa-certificates` | `academicAffairs.graduationCert.view` | `graduation-certificates.html` |
| 审核归档 | `aa-graduation-audit-console` | `academicAffairs.graduation.manage` | `graduation-archive.html` |

## 关键边界

1. 预审不是终审，进入名单也不是审核通过。
2. 总学分达标不能掩盖必修、核心或实践模块缺口。
3. 毕设、实习和处分事实由来源模块维护，毕业审核只读取并判断影响。
4. `UNKNOWN` 既不是通过也不是不通过，应进入补核或暂缓。
5. 终审由 `academicAffairs.graduation.final` 授权人员确认，前端建议不能自动通过。
6. 归档由 `academicAffairs.graduation.manage` 裁决，原件不可覆盖。
7. 发布后的结果更正形成新版本和完整审计。
8. 证书管理读取已发布毕业结果，不替代毕业资格审核。

## 费用页真实口径

- 数据状态：`UNKNOWN`
- 展示：黄色软提醒
- 学业结论：不阻断
- 过渡接入：财务处 Excel 回填
- 长期接入：财务系统适配器
- 禁止用教材费、奖助、贷款或迎新缴费冒充学校财务结清结果

## 生产还原要求

- 读取每个 HTML 的 route、routeName、permission、roles、states 和 boundary。
- 读取 `manifest-parts/150-graduation.json`。
- 读取 `AaGraduationBatchView.vue`、`AaGraduationAuditConsoleView.vue`、`AaCertificateView.vue` 及真实 API。
- 保留批次、规则、名单、数据截止、来源状态、审核结论、版本和审计字段。
- 所有终审、学籍终态、归档和证书动作重新读取后端状态与版本，不在前端伪造成功。

历史 `routeName: to verify` 和预审权限待核对标记已废止。
