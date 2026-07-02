const pool = require('../config/db');

// 院校管理员(1)看全部；分院(2)按本学院。其余角色不应进入分析接口。
function collegeScope(user, col = 's.college_id') {
  if (user.role === 2 && user.collegeId) return { sql: ` AND ${col} = ?`, param: user.collegeId };
  return { sql: '', param: null };
}

const analyticsModel = {
  // ===== 岗位实习分析 =====
  async intern(user) {
    const sc = collegeScope(user);
    const p = sc.param !== null ? [sc.param] : [];

    // 申请状态分布
    const [statusDist] = await pool.query(
      `SELECT a.status, COUNT(*) AS cnt
       FROM t_application a JOIN t_user s ON a.student_id = s.id
       WHERE a.is_deleted = 0${sc.sql} GROUP BY a.status`, p);

    // 实习企业 Top10（按在册实习学生数）
    const [enterpriseTop] = await pool.query(
      `SELECT e.name, COUNT(*) AS cnt
       FROM t_assignment a
       JOIN t_user s ON a.student_id = s.id
       JOIN t_enterprise e ON a.enterprise_id = e.id
       WHERE a.status = 1 AND a.is_deleted = 0${sc.sql}
       GROUP BY e.id, e.name ORDER BY cnt DESC LIMIT 10`, p);

    // 近 14 天打卡趋势
    const [checkinTrend] = await pool.query(
      `SELECT DATE(ck.checkin_time) AS day, COUNT(*) AS cnt
       FROM t_checkin ck
       JOIN t_assignment a ON a.student_id = ck.student_id AND a.status = 1
       JOIN t_user s ON ck.student_id = s.id
       WHERE ck.checkin_time >= (NOW() - INTERVAL 14 DAY)${sc.sql}
       GROUP BY DATE(ck.checkin_time) ORDER BY day`, p);

    // 各学院实习规模（院校管理员视角）
    let collegeDist = [];
    if (user.role === 1) {
      const [rows] = await pool.query(
        `SELECT c.name, COUNT(DISTINCT a.student_id) AS cnt
         FROM t_assignment a
         JOIN t_user s ON a.student_id = s.id
         LEFT JOIN t_college c ON s.college_id = c.id
         WHERE a.status = 1 AND a.is_deleted = 0
         GROUP BY c.id, c.name ORDER BY cnt DESC`);
      collegeDist = rows;
    }

    // 实习企业行业分布
    const [industryDist] = await pool.query(
      `SELECT COALESCE(e.industry,'未填写') AS industry, COUNT(*) AS cnt
       FROM t_assignment a
       JOIN t_user s ON a.student_id = s.id
       JOIN t_enterprise e ON a.enterprise_id = e.id
       WHERE a.status = 1 AND a.is_deleted = 0${sc.sql}
       GROUP BY e.industry ORDER BY cnt DESC`, p);

    return { statusDist, enterpriseTop, checkinTrend, collegeDist, industryDist };
  },

  // 今日处于已批准请假期内的实习学生数（用于在岗率计算）
  async todayLeaveCount(user) {
    const sc = collegeScope(user, 's.college_id');
    const p = sc.param !== null ? [sc.param] : [];
    const [[{ cnt }]] = await pool.query(
      `SELECT COUNT(DISTINCT lv.student_id) AS cnt
       FROM t_leave lv JOIN t_user s ON lv.student_id = s.id
       JOIN t_assignment a ON a.student_id = lv.student_id AND a.status = 1 AND a.is_deleted = 0
       WHERE lv.is_deleted = 0 AND lv.status = 2
         AND CURDATE() BETWEEN lv.start_date AND lv.end_date${sc.sql}`, p);
    return cnt || 0;
  },

  // ===== 毕业设计分析 =====
  async gd(user) {
    const sc = collegeScope(user, 's.college_id');
    const p = sc.param !== null ? [sc.param] : [];

    // 选题指派情况
    const [[assign]] = await pool.query(
      `SELECT
         COUNT(*) AS total,
         SUM(CASE WHEN tp.teacher_id IS NOT NULL THEN 1 ELSE 0 END) AS assigned
       FROM t_gd_topic tp
       LEFT JOIN t_user s ON tp.student_id = s.id
       WHERE tp.is_deleted = 0${sc.sql}`, p);

    // 成果审阅状态分布
    const [achievementStatus] = await pool.query(
      `SELECT ac.status, COUNT(*) AS cnt
       FROM t_gd_achievement ac JOIN t_user s ON ac.student_id = s.id
       WHERE ac.is_deleted = 0${sc.sql} GROUP BY ac.status`, p);

    // 成绩分布（综合成绩分档）
    const [gradeDist] = await pool.query(
      `SELECT CASE
                WHEN g.total_score >= 90 THEN '优(90+)'
                WHEN g.total_score >= 80 THEN '良(80-89)'
                WHEN g.total_score >= 70 THEN '中(70-79)'
                WHEN g.total_score >= 60 THEN '及格(60-69)'
                WHEN g.total_score IS NOT NULL THEN '不及格(<60)'
                ELSE '未录入'
              END AS grade_level,
              COUNT(*) AS cnt
       FROM t_gd_grade g JOIN t_user s ON g.student_id = s.id
       WHERE g.is_deleted = 0${sc.sql}
       GROUP BY grade_level`, p);

    // 任务节点完成情况
    const taskScope = user.role === 2 && user.collegeId
      ? { sql: ' AND (college_id = ? OR college_id IS NULL)', param: [user.collegeId] }
      : { sql: '', param: [] };
    const [taskStatus] = await pool.query(
      `SELECT status, COUNT(*) AS cnt FROM t_gd_task
       WHERE is_deleted = 0${taskScope.sql} GROUP BY status`, taskScope.param);

    return {
      topicAssign: { total: assign.total || 0, assigned: Number(assign.assigned) || 0 },
      achievementStatus, gradeDist, taskStatus
    };
  },

  // 优秀学生 / 优秀指导老师（按毕设综合成绩）
  async excellence(user) {
    const sc = collegeScope(user, 's.college_id');
    const p = sc.param !== null ? [sc.param] : [];

    const [topStudents] = await pool.query(
      `SELECT s.real_name AS name, s.eeid AS eeid, g.total_score AS score
       FROM t_gd_grade g JOIN t_user s ON g.student_id = s.id
       WHERE g.is_deleted = 0 AND g.total_score IS NOT NULL${sc.sql}
       ORDER BY g.total_score DESC LIMIT 10`, p);

    const [topTeachers] = await pool.query(
      `SELECT t.real_name AS name,
              COUNT(DISTINCT a.student_id) AS student_count,
              ROUND(AVG(g.total_score), 1) AS avg_grade
       FROM t_assignment a
       JOIN t_user t ON a.teacher_id = t.id
       JOIN t_user s ON a.student_id = s.id
       LEFT JOIN t_gd_grade g ON g.student_id = a.student_id AND g.is_deleted = 0
       WHERE a.status = 1 AND a.is_deleted = 0${sc.sql}
       GROUP BY t.id, t.real_name
       ORDER BY avg_grade DESC, student_count DESC LIMIT 10`, p);

    return { topStudents, topTeachers };
  },

  // 毕业设计仪表盘卡片
  async gdSummary(user) {
    const sc = collegeScope(user, 's.college_id');
    const p = sc.param !== null ? [sc.param] : [];
    const one = async (sql, params = p) => { const [[r]] = await pool.query(sql, params); return r; };

    const topic = await one(
      `SELECT COUNT(*) AS total, SUM(CASE WHEN tp.teacher_id IS NOT NULL THEN 1 ELSE 0 END) AS assigned
       FROM t_gd_topic tp LEFT JOIN t_user s ON tp.student_id = s.id
       WHERE tp.is_deleted = 0${sc.sql}`);
    const ach = await one(
      `SELECT COUNT(*) AS total,
              SUM(CASE WHEN ac.status = 1 THEN 1 ELSE 0 END) AS passed,
              SUM(CASE WHEN ac.status = 0 THEN 1 ELSE 0 END) AS pending
       FROM t_gd_achievement ac LEFT JOIN t_user s ON ac.student_id = s.id
       WHERE ac.is_deleted = 0${sc.sql}`);
    const grade = await one(
      `SELECT COUNT(*) AS entered FROM t_gd_grade g LEFT JOIN t_user s ON g.student_id = s.id
       WHERE g.is_deleted = 0${sc.sql}`);

    const taskScope = user.role === 2 && user.collegeId
      ? { sql: ' AND (college_id = ? OR college_id IS NULL)', param: [user.collegeId] }
      : { sql: '', param: [] };
    const task = await one(
      `SELECT COUNT(*) AS total, SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS completed
       FROM t_gd_task WHERE is_deleted = 0${taskScope.sql}`, taskScope.param);

    return {
      topicTotal: topic.total || 0,
      topicAssigned: Number(topic.assigned) || 0,
      achievementTotal: ach.total || 0,
      achievementPassed: Number(ach.passed) || 0,
      achievementPending: Number(ach.pending) || 0,
      gradeEntered: grade.entered || 0,
      taskTotal: task.total || 0,
      taskCompleted: Number(task.completed) || 0
    };
  }
};

module.exports = analyticsModel;
