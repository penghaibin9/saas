/**
 * @deprecated 已废弃。请使用 @/modules/dashboard/adapter/dashboard.adapter.js。
 * 本文件仅保留兼容导出，供历史代码过渡。
 * TODO(migrate): 全项目无引用后删除本文件。
 */
export {
  filterHighRiskStudents,
  filterFocusStudents,
  buildFocusStudents,
  buildRiskAlerts
} from '@/modules/dashboard/adapter/dashboard.adapter.js'

/** @deprecated 请从 store/adapter 获取关联关系 */
export const RISK_STUDENT_MAP = {
  'risk-checkin': 'stu-001',
  'risk-report': 'stu-001',
  'risk-gd': 'stu-004',
  'risk-teacher': null,
  'risk-foundation': null
}
