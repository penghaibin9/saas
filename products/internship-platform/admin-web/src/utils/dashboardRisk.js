/**
 * Standalone internship risk helpers.
 *
 * This file intentionally has no dependency on the full-platform dashboard module.
 * The standalone product only needs the compatibility projections below.
 */
const HIGH_RISK_LEVELS = ['HIGH', 'CRITICAL']
const FOCUS_RISK_LEVELS = ['MEDIUM', 'HIGH', 'CRITICAL']

export function filterHighRiskStudents(students = []) {
  return students.filter((student) => HIGH_RISK_LEVELS.includes(String(student?.riskLevel || '').toUpperCase()))
}

export function filterFocusStudents(students = []) {
  return students.filter((student) => FOCUS_RISK_LEVELS.includes(String(student?.riskLevel || '').toUpperCase()))
}

export function buildRiskAlerts(state = {}) {
  return (state.risks || []).filter((risk) => !['resolved', 'ignored'].includes(String(risk?.status || '').toLowerCase()))
}

export function buildFocusStudents(state = {}) {
  const focusIds = new Set(
    buildRiskAlerts(state)
      .filter((risk) => risk?.studentId && FOCUS_RISK_LEVELS.includes(String(risk?.riskLevel || risk?.level || '').toUpperCase()))
      .map((risk) => String(risk.studentId))
  )
  return (state.students || []).filter((student) => focusIds.has(String(student?.studentId ?? student?.id ?? '')))
}

export const RISK_STUDENT_MAP = {
  'risk-checkin': 'stu-001',
  'risk-report': 'stu-001',
  'risk-gd': 'stu-004',
  'risk-teacher': null,
  'risk-foundation': null
}
