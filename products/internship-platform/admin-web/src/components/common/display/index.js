/**
 * 数据展示增强组件（第三阶段·第四组）
 * 与既有 DataTable / AdvancedFilter / AppTimeline 协作，只补缺失能力，不重写它们。
 */
export { default as AppPagination } from './AppPagination.vue'
export { default as AppSearchBox } from './AppSearchBox.vue'
export { default as AppQuickFilterChips } from './AppQuickFilterChips.vue'
export { default as AppProgressBar } from './AppProgressBar.vue'
export { default as AppDescriptionList } from './AppDescriptionList.vue'
export { default as AppOperationResult } from './AppOperationResult.vue'
export { default as AppColumnConfig } from './AppColumnConfig.vue'
export { default as AppChartCard } from './AppChartCard.vue'
export { default as AppG2Chart } from './AppG2Chart.vue'
export { default as AppStackedBarChart } from './AppStackedBarChart.vue'
export { default as AppFunnelChart } from './AppFunnelChart.vue'
export { default as AppRankingChart } from './AppRankingChart.vue'
export { default as AppDrilldownChartCard } from './AppDrilldownChartCard.vue'
export {
  buildBarChartSpec,
  buildStackedBarChartSpec,
  buildTrendChartSpec,
  buildFunnelChartSpec,
  buildDonutChartSpec
} from './chartPresets'
