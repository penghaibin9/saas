export { useDashboardStore, useHomeDashboardStore } from './store/dashboard.store.js'
export {
  fetchDashboardRaw,
  getDashboardStatistics,
  getDashboardTrends,
  getDashboardTodos,
  getDashboardAlerts,
  getDashboardQuickEntries,
  fetchRisks,
  fetchLogs,
  remindRisk,
  followUpRisk,
  resolveRisk,
  completeTask,
  remindStudentApiMock,
  resolveRiskApiMock,
  completeTaskApiMock
} from './provider/dashboard.provider.js'
export {
  normalizeDashboardData,
  adaptDashboard,
  buildDashboardMetrics,
  buildTaskCompletionMetric,
  buildRiskAlerts,
  buildTaskGroups,
  buildFocusStudents,
  buildHighRiskStudents,
  buildLifecycleStages,
  groupTasks
} from './adapter/dashboard.adapter.js'
export { metricAccent } from '@/components/dashboard/presentation.js'
