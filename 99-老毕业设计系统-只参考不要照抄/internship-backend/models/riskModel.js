const pool = require('../config/db');

// 风险预警数据源：基于有效实习分配，聚合每个学生的最近打卡/周报/月报情况。
const riskModel = {
  async getStudentRiskData({ teacherId, collegeId } = {}) {
    let where = 'WHERE a.status = 1 AND a.is_deleted = 0';
    const params = [];
    if (teacherId !== undefined) { where += ' AND a.teacher_id = ?'; params.push(teacherId); }
    if (collegeId !== undefined) { where += ' AND s.college_id = ?'; params.push(collegeId); }

    const [rows] = await pool.query(
      `SELECT
         s.id AS student_id, s.real_name AS student_name, s.eeid AS student_eeid, s.college_id,
         a.teacher_id, t.real_name AS teacher_name,
         e.name AS enterprise_name,
         (SELECT MAX(DATE(ck.checkin_time)) FROM t_checkin ck WHERE ck.student_id = s.id) AS last_checkin,
         (SELECT ck2.within_range FROM t_checkin ck2 WHERE ck2.student_id = s.id
            ORDER BY ck2.checkin_time DESC LIMIT 1) AS last_in_range,
         (SELECT MAX(DATE(l.submit_time)) FROM t_intern_log l
            WHERE l.student_id = s.id AND l.type = 'weekly' AND l.status IN (1,2) AND l.is_deleted = 0) AS last_weekly,
         (SELECT MAX(DATE(l.submit_time)) FROM t_intern_log l
            WHERE l.student_id = s.id AND l.type = 'monthly' AND l.status IN (1,2) AND l.is_deleted = 0) AS last_monthly
       FROM t_assignment a
       JOIN t_user s ON a.student_id = s.id
       LEFT JOIN t_user t ON a.teacher_id = t.id
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       ${where}
       ORDER BY s.college_id, a.teacher_id`,
      params
    );
    return rows;
  }
};

module.exports = riskModel;
