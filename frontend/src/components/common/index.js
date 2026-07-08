/**
 * PC 端通用组件聚合导出
 * 用法：import { AppStatusTag, AppGlobalState } from '@/components/common'
 * 后续 UI-P2 / UI-P3 及各业务模块页面统一从此处引用，禁止散乱相对路径引用。
 */
export { default as AppPageHeader } from './AppPageHeader.vue'
export { default as AppStatusTag } from './AppStatusTag.vue'
export { default as AppRiskTag } from './AppRiskTag.vue'
export { default as AppMetricCard } from './AppMetricCard.vue'
export { default as AppTodoCard } from './AppTodoCard.vue'
export { default as AppStudentCard } from './AppStudentCard.vue'
export { default as AppSensitiveText } from './AppSensitiveText.vue'
export { default as AppGlobalState } from './AppGlobalState.vue'
export { default as AppConfirmDialog } from './AppConfirmDialog.vue'
export { default as AppExportConfirm } from './AppExportConfirm.vue'
export { default as AppInlineAlert } from './AppInlineAlert.vue'
export { default as AppStepBar } from './AppStepBar.vue'
export { default as AppTimeline } from './AppTimeline.vue'
export { default as AppFilePreview } from './AppFilePreview.vue'
export { default as AppToast } from './AppToast.vue'
export { default as AppUserChip } from './AppUserChip.vue'

// —— 第一阶段交付级公共组件（安全/审计/文件/批量/审批）——
// 见 docs/公共组件/02-第一阶段交付级公共组件使用指南.md
export { default as AppPermissionButton } from './AppPermissionButton.vue'
export { default as AppAuditTrail } from './AppAuditTrail.vue'
export { default as AppFileList } from './AppFileList.vue'
export { default as AppBatchActionBar } from './AppBatchActionBar.vue'
export { default as AppApprovalPanel } from './AppApprovalPanel.vue'
// 导出按钮统一从公共入口引用（实现位于 ./excel/，真实导出走后端并写审计）
export { default as AppExportButton } from './excel/AppExportButton.vue'

// —— 第二阶段可用版公共组件（工作台/展示/表单辅助）——
export { default as AppWorkflowTimeline } from './AppWorkflowTimeline.vue'
export { default as AppTodoPanel } from './AppTodoPanel.vue'
export { default as AppNotificationPanel } from './AppNotificationPanel.vue'
export { default as AppCopyableText } from './AppCopyableText.vue'
export { default as AppHelpTooltip } from './AppHelpTooltip.vue'
export { default as AppFieldHint } from './AppFieldHint.vue'

// 公共日期底座（见 ./date/）
export {
  AppDatePicker,
  AppDateTimePicker,
  AppDateRangePicker,
  AppDeadlinePicker,
  AppDateDisplay
} from './date'
