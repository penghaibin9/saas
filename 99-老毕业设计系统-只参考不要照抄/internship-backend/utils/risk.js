/**
 * 实习风险研判共享逻辑。
 * 由风险预警页(riskController)与迎检大屏(analyticsController.cockpit)共用，
 * 统一阈值口径，避免两处重复维护。
 */

// 阈值（天）
const TH = {
  CHECKIN_HIGH: 7,    // 超过 7 天未打卡：高风险
  CHECKIN_MID: 3,     // 超过 3 天未打卡：中风险
  WEEKLY_MID: 10,     // 周报 10 天未更新
  MONTHLY_MID: 40,    // 月报 40 天未更新
};

function daysSince(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  const today = new Date();
  return Math.floor((today.setHours(0, 0, 0, 0) - d.setHours(0, 0, 0, 0)) / 86400000);
}

// 由一行学生数据生成 0~N 条预警
function buildWarnings(row) {
  const warnings = [];
  const base = {
    student_id: row.student_id, student_name: row.student_name, student_eeid: row.student_eeid,
    teacher_id: row.teacher_id, teacher_name: row.teacher_name, enterprise_name: row.enterprise_name,
  };

  // 1) 打卡缺勤
  const ckDays = daysSince(row.last_checkin);
  if (ckDays === null) {
    warnings.push({ ...base, type: 'checkin', level: 'high', message: '从未打卡，请尽快确认实习状态' });
  } else if (ckDays >= TH.CHECKIN_HIGH) {
    warnings.push({ ...base, type: 'checkin', level: 'high', message: `已连续 ${ckDays} 天未打卡` });
  } else if (ckDays >= TH.CHECKIN_MID) {
    warnings.push({ ...base, type: 'checkin', level: 'medium', message: `已 ${ckDays} 天未打卡` });
  }

  // 2) 打卡范围异常（最近一次不在范围内）
  if (row.last_in_range === 0) {
    warnings.push({ ...base, type: 'checkin_range', level: 'medium', message: '最近一次打卡不在实习单位有效范围内' });
  }

  // 3) 周报逾期
  const wkDays = daysSince(row.last_weekly);
  if (wkDays === null) {
    warnings.push({ ...base, type: 'weekly', level: 'low', message: '尚未提交任何周报' });
  } else if (wkDays >= TH.WEEKLY_MID) {
    warnings.push({ ...base, type: 'weekly', level: 'medium', message: `周报已 ${wkDays} 天未更新` });
  }

  // 4) 月报逾期
  const moDays = daysSince(row.last_monthly);
  if (moDays !== null && moDays >= TH.MONTHLY_MID) {
    warnings.push({ ...base, type: 'monthly', level: 'medium', message: `月报已 ${moDays} 天未更新` });
  }

  return warnings;
}

// 汇总一批预警为统计指标
function summarize(list, scanned) {
  const order = { high: 0, medium: 1, low: 2 };
  const sorted = [...list].sort((a, b) => order[a.level] - order[b.level]);
  return {
    summary: {
      total: list.length,
      high: list.filter((w) => w.level === 'high').length,
      medium: list.filter((w) => w.level === 'medium').length,
      low: list.filter((w) => w.level === 'low').length,
      students: new Set(list.map((w) => w.student_id)).size,
      scanned,
    },
    list: sorted,
  };
}

module.exports = { TH, daysSince, buildWarnings, summarize };
