# security 前端安全基线（00-SEC）

## 用途

按**等保 2.0 三级建设思路**为全系统提供前端安全底座：认证上下文、会话策略、路由/菜单/按钮/数据范围守卫、上传下载导出闸口、敏感脱敏、审计事件、安全请求封装、错误页与水印。后续学生主档、岗位实习、毕业设计、迎新、就业等模块**统一复用本目录，禁止各自实现**。

## 重要声明

- 当前为**前端 mock / 预留实现**，authContext、CSRF、审计上报均为 mock；**不代表系统已通过等保三级**，最终以定级备案与第三方测评为准（见 docs/security/00-等保三级安全基线总册.md）。
- 权限判断**复用 workflow permissionContext**（`@/modules/workflow/context/permission.context`），本目录只做安全侧封装，无第二套权限逻辑。

## 后续真实后端接入点

| 能力 | 当前 | 接入点 |
| --- | --- | --- |
| authContext | mock 登录态 | 替换 `auth/auth.context.js` 的 MOCK_AUTH 来源为认证服务，签名不变 |
| CSRF | mock token | `helpers/csrf.helper.js` 改读后端下发的 cookie/meta |
| 审计上报 | 内存队列 | `sendAuditEventToBackend` 改为 POST /api/v1/security/audit-events |
| secureRequest | 无调用方 | 业务 provider 接真实 API 时统一走 `secureRequest`（带 requestId/CSRF/401 分流） |
| 路由守卫 | 函数预留 | P8 在 router.beforeEach 中调用 `checkRouteAccess` + `resolveRouteFailure` |
| 签名 URL | 形态校验 | 文件中心签发真实短期签名 |

## 页面接入示例

```js
import { canExport } from '@/security/guards/export.guard'
import { createAuditEvent } from '@/security/helpers/audit-event.helper'
import { maskPhone } from '@/security/helpers/sensitive-mask.helper'
import { sendAuditEventToBackend, EXPORT_POLICY } from '@/security'

// 1) 导出按钮可见性
const showExport = canExport(EXPORT_POLICY.TYPES.LIST)

// 2) 展示脱敏手机号
const shown = maskPhone(student.phone) // 135****6867

// 3) 敏感查看留痕
const evt = createAuditEvent('SENSITIVE_VIEW', '查看学生联系方式', { studentId: 'stu-001' })
await sendAuditEventToBackend(evt)
```

```vue
<!-- 4) 页面水印 -->
<template>
  <div class="page-with-watermark" style="position: relative">
    <SecurityWatermark purpose="实习名单核对" />
    <!-- 页面内容 -->
  </div>
</template>
<script>
import { SecurityWatermark } from '@/security'
export default { components: { SecurityWatermark } }
</script>
```

```js
// 5) 上传前校验
import { validateUploadFile } from '@/security/guards/upload.guard'
const { valid, reason } = validateUploadFile(file)
if (!valid) toast.warning(reason)
```

## 错误页路由

`/security/401`、`/security/403`、`/security/419`、`/security/500` —— 均可直接访问，不暴露堆栈，带返回首页与重新登录占位按钮。
