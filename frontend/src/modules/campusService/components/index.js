/**
 * 在校服务中心 — 模块局部组件。
 *
 * 老「在校服务」页面已整体退役（见 campusService.routes.js），只被那些页面使用的
 * 导入/导出/列设置/表单抽屉/住宿详情组件随之删除。这里保留的两项仍被学生主档的
 * 更正审核、身份核验、学生列表等在用页面引用：
 * - SplitWorkspace：左右双栏工作区
 * - readListState / writeListState：列表筛选状态与 URL 同步
 */
export { default as SplitWorkspace } from './SplitWorkspace.vue'
export { readListState, writeListState } from './routeState'
