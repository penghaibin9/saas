# student 模块（01 学生主档与身份中心）

## 职责

全系统**统一学生数据底座**：学生主档、身份认证、学籍状态、联系人/监护人、账号绑定、风险标签、数据范围、审计与导入导出预留。后续 02 迎新、03 在校服务、04 学业过程、05 毕设、06 实习、07 就业、10 驾驶舱、09A/09B 端一律引用本模块，**禁止各自再造学生数据**。

## 重要声明

- **不接真实后端**：当前全部经 `provider → api.mock → mock 内存数据`；本模块不代表已完成后端安全（等保口径见 docs/security 总册）。
- 真实 API 接入：仅将 `provider/student.provider.js` 的 impl 切换为 `api/student.api.real.example.js`（已统一走 security `secureRequest`），页面零改动。

## 引用方式（后续模块）

```js
import { studentProvider, maskStudentForDisplay, STUDENT_STATUS } from '@/modules/student'
const res = await studentProvider.getStudentDetail(studentId) // 统一响应 {code,message,data,...}
```

## 敏感数据脱敏

全部复用 `@/security`：身份证前6+****+后4、手机前3+****+后4、姓名姓+*、住址保留区县+****。
列表/详情经 `maskStudentForDisplay` / `maskGuardianForDisplay` 展示；mock 中的原文仅存于内存，禁止 console 输出、禁止 localStorage 存储。

## 权限点（module.resource.action）

student.profile.view/create/update/delete、student.identity.view/verify、student.contact.view/update、
student.guardian.view/update、student.status.update、student.import、student.export、student.audit.view。
判断唯一入口 `hasStudentPermission()`（复用 workflow permissionContext；mock 阶段 SCHOOL_ADMIN 放行 student.*，P8 权限中心下发后删除放行分支）。

## 数据范围

SCHOOL / COLLEGE / CLASS / SELF / ASSIGNED（workflow getDataScope 提供），页面经 `StudentDataScopeHint` 常驻展示；行级过滤走 security data-scope guard，真实控制在后端复核。

## 导入导出（01-P1 仅预留）

导入：仅 mock 校验结果展示，不解析真实文件；导出：经 security export guard 三档校验 + 强制审计事件，不产真实文件。真实实现排期 **01-P2**。

## 审计

查看详情（SENSITIVE_VIEW）、核验通过/退回（APPROVAL）、状态变更（APPROVAL，含 before/after+原因）、监护人变更、导入校验（UPLOAD）、导出（EXPORT）均生成审计事件（security audit helper，detail 强制脱敏）；当前入内存队列，后端阶段统一上报。

## 与 security / workflow 的关系

- security：脱敏、水印（详情页/导出页）、导出/上传/下载闸口、审计事件、错误页。
- workflow：permissionContext（权限与数据范围单一来源）、`validateRejectReason`（身份核验退回≥5字直接复用，无第二套实现）。
- **身份认证未来可接入 workflow process instance**：当前核验/退回为模块内独立操作；接入正式审批流时，由 workflow 流程实例承载（businessModule=STUDENT，businessType=profile_change/identity_verify），本模块只需把 verify/reject 改为提交流程动作。

## 与 09A 的边界

本模块=学生**数据底座**（列表/详情/身份/状态/监护人/provider/组件）。09A 多角色工作台后续**直接复用 `studentProvider` 与本模块组件**（StudentProfileCard/StudentStatusTag/StudentRiskFlag 等）搭建辅导员/教师视角首页，**不重复开发学生数据底座**；本模块 StudentStatusView 只做状态数据管理，不承担 09A 的多角色首页/跨模块待办/工作台大盘。
