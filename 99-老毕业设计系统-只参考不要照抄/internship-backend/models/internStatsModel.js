const pool = require('../config/db');

function scopeClause(user) {
  // 院校管理员(1)看全部；分院(2)按学院；教师(3)按本人指导
  if (user.role === 2) return { sql: ' AND s.college_id = ?', param: user.collegeId };
  if (user.role === 3) return { sql: ' AND a.teacher_id = ?', param: user.id };
  return { sql: '', param: null };
}

const internStatsModel = {
  // 指定天数内未打卡的实习学生
  async uncheckedStudents(user, days = 1) {
    const sc = scopeClause(user);
    const params = [];
    if (sc.param !== null) params.push(sc.param);
    params.push(days);
    const [rows] = await pool.query(
      `SELECT s.id AS student_id, s.real_name AS student_name, s.eeid AS student_eeid,
              s.phone, e.name AS enterprise_name, t.real_name AS teacher_name,
              MAX(ck.checkin_time) AS last_checkin
       FROM t_assignment a
       JOIN t_user s ON a.student_id = s.id
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       LEFT JOIN t_user t ON a.teacher_id = t.id
       LEFT JOIN t_checkin ck ON ck.student_id = s.id
       WHERE a.status = 1 AND a.is_deleted = 0${sc.sql}
       GROUP BY s.id, s.real_name, s.eeid, s.phone, e.name, t.real_name
       HAVING last_checkin IS NULL OR last_checkin < (NOW() - INTERVAL ? DAY)
       ORDER BY last_checkin IS NULL DESC, last_checkin ASC`,
      params
    );
    return rows;
  },

  // 实习过程统计：每个在册学生的签到/周报/月报完成情况 vs 计划要求
  async processStats(user, { page = 1, pageSize = 20, keyword } = {}) {
    const offset = (page - 1) * pageSize;
    const sc = scopeClause(user);
    const baseParams = [];
    if (sc.param !== null) baseParams.push(sc.param);

    let kwSql = '';
    const kwParams = [];
    const kw = keyword ? String(keyword).trim() : '';
    if (kw) {
      kwSql = ' AND (s.real_name LIKE ? OR s.eeid LIKE ? OR s.phone LIKE ? OR e.name LIKE ?)';
      const like = `%${kw}%`;
      kwParams.push(like, like, like, like);
    }

    const fromWhere = `FROM t_assignment a
       JOIN t_user s ON a.student_id = s.id
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       LEFT JOIN t_user t ON a.teacher_id = t.id
       LEFT JOIN t_intern_plan p ON a.plan_id = p.id
       WHERE a.status = 1 AND a.is_deleted = 0${sc.sql}${kwSql}`;

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total ${fromWhere}`,
      [...baseParams, ...kwParams]
    );

    const [rows] = await pool.query(
      `SELECT s.id AS student_id, s.real_name AS student_name, s.eeid AS student_eeid,
              e.name AS enterprise_name, t.real_name AS teacher_name,
              (SELECT COUNT(*) FROM t_checkin c WHERE c.student_id = s.id) AS checkin_count,
              (SELECT COUNT(*) FROM t_intern_log l WHERE l.student_id = s.id AND l.type='weekly'  AND l.status IN (1,2) AND l.is_deleted=0) AS weekly_count,
              (SELECT COUNT(*) FROM t_intern_log l WHERE l.student_id = s.id AND l.type='monthly' AND l.status IN (1,2) AND l.is_deleted=0) AS monthly_count,
              (SELECT MAX(c.checkin_time) FROM t_checkin c WHERE c.student_id = s.id) AS last_checkin,
              p.checkin_count AS req_checkin, p.weekly_count AS req_weekly, p.monthly_count AS req_monthly
       ${fromWhere}
       ORDER BY s.eeid
       LIMIT ? OFFSET ?`,
      [...baseParams, ...kwParams, pageSize, offset]
    );
    return { total, list: rows, page, pageSize, keyword: kw || undefined };
  },

  // 未达标学生：签到/周报/月报 未满足实习计划要求
  async incompleteStudents(user, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    const sc = scopeClause(user);
    const baseParams = [];
    if (sc.param !== null) baseParams.push(sc.param);

    // 用子查询计算完成数，再在外层 HAVING 比较计划要求
    const inner = `
      SELECT s.id AS student_id, s.real_name AS student_name, s.eeid AS student_eeid,
             e.name AS enterprise_name, t.real_name AS teacher_name,
             (SELECT COUNT(*) FROM t_checkin c WHERE c.student_id = s.id) AS checkin_count,
             (SELECT COUNT(*) FROM t_intern_log l WHERE l.student_id = s.id AND l.type='weekly'  AND l.status IN (1,2) AND l.is_deleted=0) AS weekly_count,
             (SELECT COUNT(*) FROM t_intern_log l WHERE l.student_id = s.id AND l.type='monthly' AND l.status IN (1,2) AND l.is_deleted=0) AS monthly_count,
             COALESCE(p.checkin_count,0) AS req_checkin, COALESCE(p.weekly_count,0) AS req_weekly, COALESCE(p.monthly_count,0) AS req_monthly
      FROM t_assignment a
      JOIN t_user s ON a.student_id = s.id
      LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
      LEFT JOIN t_user t ON a.teacher_id = t.id
      LEFT JOIN t_intern_plan p ON a.plan_id = p.id
      WHERE a.status = 1 AND a.is_deleted = 0${sc.sql}`;

    const having = 'WHERE checkin_count < req_checkin OR weekly_count < req_weekly OR monthly_count < req_monthly';

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM (${inner}) x ${having}`, baseParams
    );
    const [rows] = await pool.query(
      `SELECT * FROM (${inner}) x ${having} ORDER BY student_eeid LIMIT ? OFFSET ?`,
      [...baseParams, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  // 汇总卡片：实习人数、企业数、今日打卡数、待批阅周报/月报、待审批请假
  async summary(user) {
    const sc = scopeClause(user);
    const p = sc.param !== null ? [sc.param] : [];

    const [[{ studentCount }]] = await pool.query(
      `SELECT COUNT(DISTINCT a.student_id) AS studentCount
       FROM t_assignment a JOIN t_user s ON a.student_id = s.id
       WHERE a.status = 1 AND a.is_deleted = 0${sc.sql}`, p);

    const [[{ enterpriseCount }]] = await pool.query(
      `SELECT COUNT(DISTINCT a.enterprise_id) AS enterpriseCount
       FROM t_assignment a JOIN t_user s ON a.student_id = s.id
       WHERE a.status = 1 AND a.is_deleted = 0 AND a.enterprise_id IS NOT NULL${sc.sql}`, p);

    // 今日打卡：人次(todayCheckins) 与 去重人数(todayCheckinStudents)，后者用于计算打卡率
    const [[{ todayCheckins, todayCheckinStudents }]] = await pool.query(
      `SELECT COUNT(*) AS todayCheckins, COUNT(DISTINCT ck.student_id) AS todayCheckinStudents
       FROM t_checkin ck
       JOIN t_assignment a ON a.student_id = ck.student_id AND a.status = 1
       JOIN t_user s ON ck.student_id = s.id
       WHERE DATE(ck.checkin_time) = CURDATE()${sc.sql}`, p);

    let pendingLogs = 0, pendingLeaves = 0;
    if (user.role === 3) {
      const [[{ c1 }]] = await pool.query(
        `SELECT COUNT(*) AS c1 FROM t_intern_log WHERE teacher_id = ? AND status = 1 AND is_deleted = 0`, [user.id]);
      const [[{ c2 }]] = await pool.query(
        `SELECT COUNT(*) AS c2 FROM t_leave WHERE teacher_id = ? AND status = 1 AND is_deleted = 0`, [user.id]);
      pendingLogs = c1; pendingLeaves = c2;
    }

    return { studentCount, enterpriseCount, todayCheckins, todayCheckinStudents, pendingLogs, pendingLeaves };
  }
};

module.exports = internStatsModel;
