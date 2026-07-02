# workflow 模块（11 权限与流程中心）

全系统前端底座：审批任务、流程模板、角色、权限点、数据范围、permissionContext。
后续业务模块（学生主档/岗位实习/毕业设计/迎新/在校服务/学业过程/毕业就业/驾驶舱）统一挂接本中心，禁止自建审批与权限判断。

## 分层

```
api/        contract（18 接口冻结）+ mock 实现（默认）+ real.example（未启用）
provider/   页面唯一数据门面（页面禁止直引 mock/api）
constants/  全部集中枚举（模块/状态/动作/角色/数据范围/节点类型…）
mock/       唯一 mock 数据源（不伪造业务正文，只有 businessModule/Type/Id 等骨架字段）
context/    permissionContext（mock）+ canAccessPage/canClickButton/canViewMenu/hasRole…
guards/     checkRoutePermission/checkMenuPermission/checkButtonPermission/checkDataScope（P8 实装入口，签名冻结）
helpers/    审批（validateRejectReason≥5字 等）/ 权限匹配 / 状态文案
components/ 模块内 UI（StateBlock/Timeline/TaskList/DetailPanel/RolePanel/Tags…），不入全局组件库
```

## 数据流

页面 → provider → api.mock（默认）→ mock 数据（写操作真实变更 + 追加审计）。
接后端：provider 将 impl 切到 api.real.example 同名方法，页面零改动。

## licenseContext 关系（预留）

当前不接真实授权中心。视图状态 NORMAL/READONLY/NO_LICENSE 由 mock 提供并可在
AdminWorkflowLayout 头部切换演示；冻结优先级兼容 03 开关模型：
租户停用 > 到期只读 > 模块未授权 > 试用限制 > 功能开关 > 角色权限 > 按钮权限 > 数据范围。
P6-2 /platform 落地后，替换 `workflow.helpers.resolveLicenseViewState` 与 mock licenseState 的数据来源即可。

## 业务模块接入方式（后续）

1. 在 `constants` 确认 moduleCode 与业务 businessType 命名。
2. 业务提交动作调用 provider 创建流程实例（P7 扩展 createInstance 契约）。
3. 待办/审批统一读 `getApprovalTasks({ moduleCode })`；退回原因校验统一走 `validateRejectReason`。
4. 页面/按钮权限统一走 context 的 canAccessPage/canClickButton；行级数据用 guards.checkDataScope。
