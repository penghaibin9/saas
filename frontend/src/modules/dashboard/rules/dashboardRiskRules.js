/**
 * Dashboard 风险口径规则（单一来源）
 * 连续打卡异常等口径统一在此定义，adapter / mock / aggregate 均引用本文件。
 */

export const CHECKIN_ABNORMAL_STREAK_THRESHOLD = 3

const ABNORMAL_STATUSES = new Set(['ABNORMAL', 'MISSING'])

/**
 * 计算学生截至 today 的连续异常打卡天数
 * @param {Array<{ studentId: string, date: string, status: string }>} checkins
 * @param {string} studentId
 * @param {string} today YYYY-MM-DD
 */
export function calculateCheckinAbnormalStreak(checkins, studentId, today) {
  const recs = checkins
    .filter((c) => c.studentId === studentId && c.date <= today)
    .sort((a, b) => (a.date < b.date ? 1 : -1))
  let streak = 0
  for (const r of recs) {
    if (ABNORMAL_STATUSES.has(r.status)) streak++
    else break
  }
  return streak
}

/**
 * 是否达到连续异常打卡阈值（默认 3 天）
 */
export function isContinuousCheckinAbnormal(
  checkins,
  studentId,
  today,
  threshold = CHECKIN_ABNORMAL_STREAK_THRESHOLD
) {
  return calculateCheckinAbnormalStreak(checkins, studentId, today) >= threshold
}

/**
 * 统计达到连续异常阈值的学生人数
 */
export function countContinuousCheckinAbnormalStudents(
  checkins,
  studentIds,
  today,
  threshold = CHECKIN_ABNORMAL_STREAK_THRESHOLD
) {
  return studentIds.filter((sid) =>
    isContinuousCheckinAbnormal(checkins, sid, today, threshold)
  ).length
}
