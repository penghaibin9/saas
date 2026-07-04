/**
 * PC 业务通用组件（岗位实习 / 毕业设计 / 后续就业、迎新等模块共用）。
 * 原则：组件不写死任何业务名词；状态/风险标签复用 components/common 既有实现。
 * 用法：import { ModulePageShell, DataTable, StatusTag } from '@/components/business'
 */
export { default as ModulePageShell } from './ModulePageShell.vue'
export { default as ModuleHero } from './ModuleHero.vue'
export { default as ModuleToolbar } from './ModuleToolbar.vue'
export { default as AdvancedFilter } from './AdvancedFilter.vue'
export { default as DataTable } from './DataTable.vue'
export { default as EmptyState } from './EmptyState.vue'
export { default as LoadingState } from './LoadingState.vue'
export { default as ErrorState } from './ErrorState.vue'
/** 状态标签 / 风险标签：直接复用全局通用实现，避免重复造轮子 */
export { default as StatusTag } from '@/components/common/AppStatusTag.vue'
export { default as RiskTag } from '@/components/common/AppRiskTag.vue'
