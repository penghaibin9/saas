const pool = require('../config/db');

const statsModel = {
  // 管理员仪表板统计
  async adminOverview(collegeId) {
    const cond = collegeId ? 'AND u.college_id = ?' : '';
    const p = collegeId ? [collegeId] : [];

    const [[apps]] = await pool.query(
      `SELECT
         COUNT(*) AS total,
         SUM(a.status = 0) AS pending,
         SUM(a.status = 1) AS teacher_agreed,
         SUM(a.status = 3) AS admin_passed,
         SUM(a.status = 5) AS hired,
         SUM(a.status IN (2,4,6)) AS rejected
       FROM t_application a
       LEFT JOIN t_user u ON a.student_id = u.id
       WHERE a.is_deleted = 0 ${cond}`, p
    );

    const [[reports]] = await pool.query(
      `SELECT
         COUNT(*) AS total,
         SUM(r.status = 0) AS draft,
         SUM(r.status = 1) AS submitted,
         SUM(r.status = 2) AS reviewed
       FROM t_report r
       LEFT JOIN t_application a ON r.application_id = a.id
       LEFT JOIN t_user u ON a.student_id = u.id
       WHERE r.is_deleted = 0 ${cond}`, p
    );

    const positionsCondition = collegeId ? 'WHERE is_deleted=0 AND (college_id = ? OR college_id IS NULL)' : 'WHERE is_deleted=0';
    const positionsParams = collegeId ? [collegeId] : [];
    const [[positions]] = await pool.query(
      `SELECT COUNT(*) AS total, SUM(status=1) AS active FROM t_position ${positionsCondition}`,
      positionsParams
    );

    const userCondition = collegeId ? 'WHERE is_deleted=0 AND status=1 AND college_id = ?' : 'WHERE is_deleted=0 AND status=1';
    const userParams = collegeId ? [collegeId] : [];
    const [[users]] = await pool.query(
      `SELECT COUNT(*) AS total,
              SUM(role=1) AS admin_college,
              SUM(role=2) AS admin_branch,
              SUM(role=3) AS teacher,
              SUM(role=4) AS student
       FROM t_user ${userCondition}`,
      userParams
    );

    // 近6月申请趋势
    const [trend] = await pool.query(
      `SELECT DATE_FORMAT(apply_time,'%Y-%m') AS month, COUNT(*) AS cnt
       FROM t_application a
       LEFT JOIN t_user u ON a.student_id = u.id
       WHERE apply_time >= DATE_SUB(NOW(), INTERVAL 6 MONTH) AND a.is_deleted=0 ${cond}
       GROUP BY month ORDER BY month`, p
    );

    return { apps, reports, positions, users, trend };
  },

  // 教师仪表板
  async teacherOverview(teacherId) {
    const [[apps]] = await pool.query(
      `SELECT COUNT(*) AS total,
              SUM(status=0) AS pending,
              SUM(status=1) AS agreed,
              SUM(status=2) AS rejected
       FROM t_application WHERE teacher_id=? AND is_deleted=0`, [teacherId]
    );
    const [[reports]] = await pool.query(
      `SELECT COUNT(*) AS total, SUM(r.status=1) AS submitted, SUM(r.status=2) AS reviewed
       FROM t_report r
       JOIN t_application a ON r.application_id=a.id
       WHERE a.teacher_id=? AND r.is_deleted=0`, [teacherId]
    );
    return { apps, reports };
  },

  // 学生仪表板
  async studentOverview(studentId) {
    const [[apps]] = await pool.query(
      `SELECT COUNT(*) AS total,
              SUM(status=0) AS pending,
              SUM(status=5) AS hired,
              SUM(status IN(2,4,6)) AS rejected
       FROM t_application WHERE student_id=? AND is_deleted=0`, [studentId]
    );
    const [[reports]] = await pool.query(
      `SELECT COUNT(*) AS total, SUM(r.status=2) AS reviewed, AVG(r.teacher_score) AS avg_score
       FROM t_report r
       JOIN t_application a ON r.application_id=a.id
       WHERE a.student_id=? AND r.is_deleted=0`, [studentId]
    );
    const [recentApps] = await pool.query(
      `SELECT a.id, a.status, a.apply_time, p.title AS position_title, e.name AS enterprise_name
       FROM t_application a
       JOIN t_position p ON a.position_id=p.id
       JOIN t_enterprise e ON a.enterprise_id=e.id
       WHERE a.student_id=? AND a.is_deleted=0
       ORDER BY a.apply_time DESC LIMIT 5`, [studentId]
    );
    return { apps, reports, recentApps };
  }
};

module.exports = statsModel;
