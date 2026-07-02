/**
 * Pinia store 聚合导出
 * 用法：import { useDashboardStore } from '@/modules/dashboard'
 */
export { useStudentDashboardStore } from './studentDashboard'
export { useTeacherWorkbenchStore } from './teacherWorkbench'
export { usePracticeOverviewStore } from './practiceOverview'
export { useDashboardStore, useHomeDashboardStore } from '@/modules/dashboard/store/dashboard.store'
export { useEnterpriseDashboardStore } from './enterpriseDashboard'
export { useGdDashboardStore } from './gdDashboard'
export { useInternshipDashboardStore } from './internshipDashboard'
