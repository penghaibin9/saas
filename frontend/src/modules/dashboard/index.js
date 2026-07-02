export { useDashboardStore, useHomeDashboardStore } from './store/dashboard.store.js'
export {
  fetchDashboardRaw,
  resolveRiskApiMock,
  remindStudentApiMock,
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
  buildLifecycleStages,
  metricAccent,
  groupTasks
} from './adapter/dashboard.adapter.js'
