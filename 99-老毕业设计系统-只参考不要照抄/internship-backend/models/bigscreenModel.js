const pool = require('../config/db');

// 监管大屏聚合：GIS 实习分布 + 多维风险雷达。容错（单项查询失败返回空/0，不阻断）。
async function safeRows(sql, params = []) {
  try { const [rows] = await pool.query(sql, params); return rows; } catch (_) { return []; }
}
async function safeCount(sql, params = []) {
  try { const [[r]] = await pool.query(sql, params); return Number(r.c) || 0; } catch (_) { return 0; }
}

const bigscreenModel = {
  // GIS 点位：有坐标的实习企业 + 其在册实习人数（用于地图打点）
  async gisPoints({ collegeId } = {}) {
    const where = collegeId ? ' AND s.college_id = ?' : '';
    const params = collegeId ? [collegeId] : [];
    return safeRows(
      `SELECT e.id, e.name, e.latitude AS lat, e.longitude AS lng, COUNT(DISTINCT a.student_id) AS interns
       FROM t_enterprise e
       JOIN t_assignment a ON a.enterprise_id = e.id AND a.is_deleted = 0 AND a.status = 1
       JOIN t_user s ON s.id = a.student_id AND s.is_deleted = 0
       WHERE e.latitude IS NOT NULL AND e.longitude IS NOT NULL${where}
       GROUP BY e.id, e.name, e.latitude, e.longitude
       ORDER BY interns DESC`,
      params
    );
  },

  // 按学院汇总在册实习人数（无坐标时的区域分布兜底）
  async byCollege() {
    return safeRows(
      `SELECT c.id, c.name, COUNT(DISTINCT a.student_id) AS interns
       FROM t_college c
       LEFT JOIN t_user s ON s.college_id = c.id AND s.role = 4 AND s.is_deleted = 0
       LEFT JOIN t_assignment a ON a.student_id = s.id AND a.is_deleted = 0 AND a.status = 1
       WHERE c.is_deleted = 0
       GROUP BY c.id, c.name ORDER BY interns DESC`
    );
  },

  // 多维风险雷达：各风险维度的当前计数
  async riskRadar({ collegeId } = {}) {
    const cw = collegeId ? ' AND s.college_id = ?' : '';
    const cp = collegeId ? [collegeId] : [];

    const checkinRisk = await safeCount(
      `SELECT COUNT(*) c FROM t_checkin ck JOIN t_user s ON s.id = ck.student_id
       WHERE ck.risk_level = 'high' AND DATE(ck.checkin_time) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)${cw}`, cp);
    const complaints = await safeCount(
      `SELECT COUNT(*) c FROM t_complaint cp JOIN t_user s ON s.id = cp.student_id
       WHERE cp.status IN (0,1)${cw}`, cp);
    const uninsured = await safeCount(
      `SELECT COUNT(DISTINCT a.student_id) c FROM t_assignment a JOIN t_user s ON s.id = a.student_id
       LEFT JOIN t_insurance i ON i.student_id = a.student_id AND i.is_deleted = 0
       WHERE a.is_deleted = 0 AND a.status = 1 AND i.id IS NULL${cw}`, cp);
    const noCheckin3d = await safeCount(
      `SELECT COUNT(DISTINCT a.student_id) c FROM t_assignment a JOIN t_user s ON s.id = a.student_id
       WHERE a.is_deleted = 0 AND a.status = 1${cw}
         AND NOT EXISTS (SELECT 1 FROM t_checkin ck WHERE ck.student_id = a.student_id
                         AND ck.checkin_time >= DATE_SUB(NOW(), INTERVAL 3 DAY))`, cp);
    const changes = await safeCount(
      `SELECT COUNT(*) c FROM t_assignment_change ac JOIN t_user s ON s.id = ac.student_id
       WHERE ac.status = 0${cw}`, cp);

    return [
      { key: 'checkin_cheat', label: '打卡异常(30天)', value: checkinRisk },
      { key: 'complaint', label: '未处理投诉', value: complaints },
      { key: 'uninsured', label: '未投保在册', value: uninsured },
      { key: 'no_checkin', label: '3天未打卡', value: noCheckin3d },
      { key: 'assign_change', label: '待审换岗/终止', value: changes },
    ];
  },
};

module.exports = bigscreenModel;
