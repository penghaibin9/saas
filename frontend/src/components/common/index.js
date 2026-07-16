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
export { default as AppQuickPhrases } from './AppQuickPhrases.vue'
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

// —— 第三阶段·第一组 页面骨架（见 ./layout/）——
export {
  AppPageShell,
  AppModuleHero,
  AppToolbar,
  AppSectionHeader,
  AppSectionCard,
  AppActionBar,
  AppStickyFooter,
  AppResponsiveGrid,
  AppDrawerLayout
} from './layout'

// —— 第三阶段·第二组 通用表单（见 ./form/）——
export {
  AppForm,
  AppFormItem,
  AppFormSection,
  AppTextInput,
  AppNumberInput,
  AppTextarea,
  AppTemplateChips,
  AppSelect,
  AppMultiSelect,
  AppRadioGroup,
  AppCheckboxGroup,
  AppSubmitBar,
  AppRichTextEditor
} from './form'

// —— 第三阶段·第三组 高校业务选择器（见 ./picker/，全部 partial）——
export {
  AppRemoteSelect,
  AppOrgCascader,
  AppAcademicYearPicker,
  AppTermPicker,
  AppStudentPicker,
  AppTeacherPicker,
  AppMentorPicker,
  AppClassPicker,
  AppMajorPicker,
  AppCollegePicker,
  AppCoursePicker,
  AppRolePicker,
  AppTenantPicker,
  AppCompanyPicker,
  AppPositionPicker,
  AppBatchPicker
} from './picker'

// —— 第三阶段·第四组 数据展示增强（见 ./display/）——
export {
  AppPagination,
  AppSearchBox,
  AppQuickFilterChips,
  AppProgressBar,
  AppDescriptionList,
  AppOperationResult,
  AppColumnConfig,
  AppChartCard,
  AppG2Chart,
  AppStackedBarChart,
  AppFunnelChart,
  AppRankingChart,
  AppDrilldownChartCard,
  buildBarChartSpec,
  buildStackedBarChartSpec,
  buildTrendChartSpec,
  buildFunnelChartSpec,
  buildDonutChartSpec
} from './display'

// —— 第三阶段·第五组 体验增强（见 ./experience/，AppQRCode 为 partial）——
export {
  AppWatermark,
  AppPrintButton,
  AppAvatarGroup,
  AppStepGuide,
  AppKeyboardShortcut,
  AppQRCode
} from './experience'

// 公共日期底座（见 ./date/）
export {
  AppDatePicker,
  AppDateTimePicker,
  AppDateRangePicker,
  AppDeadlinePicker,
  AppDateDisplay
} from './date'
