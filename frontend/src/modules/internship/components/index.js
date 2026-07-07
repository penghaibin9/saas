/**
 * 岗位实习中心 — 模块局部组件（与数字迎新/就业模块同范式复刻，不修改全局 components/business，
 * 避免并行任务冲突）。
 * 全局已有的 ModulePageShell / ModuleHero / ModuleToolbar / AdvancedFilter / DataTable /
 * StatusTag / RiskTag / Empty·Loading·ErrorState 直接从 '@/components/business' 复用。
 */
export { default as TableActionColumn } from './TableActionColumn.vue'
export { default as EditDrawer } from './EditDrawer.vue'
export { default as AuditTrailPanel } from './AuditTrailPanel.vue'
export { default as NoPermissionState } from './NoPermissionState.vue'
