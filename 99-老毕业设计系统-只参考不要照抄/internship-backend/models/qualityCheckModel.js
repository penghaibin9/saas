const pool = require('../config/db');

// 质量监控/互查。status: 0待审阅 1通过 2驳回 3未完成
const qualityCheckModel = {
  async findAll({ checkerId, studentId, collegeId, status, scope } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE q.is_deleted = 0';
    const params = [];
    if (checkerId !== undefined) { where += ' AND q.checker_id = ?'; params.push(checkerId); }
    if (studentId !== undefined) { where += ' AND q.student_id = ?'; params.push(studentId); }
    if (collegeId !== undefined) { where += ' AND q.college_id = ?'; params.push(collegeId); }
    if (status !== undefined)    { where += ' AND q.status = ?';     params.push(status); }
    if (scope !== undefined)     { where += ' AND q.scope = ?';      params.push(scope); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_quality_check q ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT q.*, s.real_name AS student_name, s.eeid AS student_eeid,
              ck.real_name AS checker_name, ac.title AS achievement_title
       FROM t_quality_check q
       LEFT JOIN t_user s  ON q.student_id = s.id
       LEFT JOIN t_user ck ON q.checker_id = ck.id
       LEFT JOIN t_gd_achievement ac ON q.achievement_id = ac.id
       ${where} ORDER BY q.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT q.*, s.real_name AS student_name, ck.real_name AS checker_name
       FROM t_quality_check q
       LEFT JOIN t_user s  ON q.student_id = s.id
       LEFT JOIN t_user ck ON q.checker_id = ck.id
       WHERE q.id = ? AND q.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async create(q, conn = pool) {
    const [result] = await conn.query(
      `INSERT INTO t_quality_check
        (batch_name, check_type, scope, checker_id, student_id, achievement_id, college_id, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, 0)`,
      [q.batch_name, q.check_type || 'census', q.scope || 'cross',
       q.checker_id || null, q.student_id, q.achievement_id || null, q.college_id || null]
    );
    return result.insertId;
  },

  async review(id, { status, opinion }) {
    const [result] = await pool.query(
      `UPDATE t_quality_check SET status = ?, opinion = ?, review_time = NOW()
       WHERE id = ? AND is_deleted = 0`,
      [status, opinion || null, id]
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query('UPDATE t_quality_check SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  }
};

module.exports = qualityCheckModel;
