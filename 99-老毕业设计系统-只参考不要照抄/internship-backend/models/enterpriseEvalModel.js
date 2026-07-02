const pool = require('../config/db');

// 企业导师评价：管理员/教师为学生生成评价令牌，企业导师免登录填写。
const enterpriseEvalModel = {
  async findAll({ collegeId, studentId, status } = {}, { page = 1, pageSize = 50 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE ev.is_deleted = 0';
    const params = [];
    if (collegeId !== undefined) { where += ' AND ev.college_id = ?'; params.push(collegeId); }
    if (studentId !== undefined) { where += ' AND ev.student_id = ?'; params.push(studentId); }
    if (status !== undefined)    { where += ' AND ev.status = ?';     params.push(status); }
    const [[{ total }]] = await pool.query(`SELECT COUNT(*) AS total FROM t_enterprise_eval ev ${where}`, params);
    const [rows] = await pool.query(
      `SELECT ev.*, s.real_name AS student_name, s.eeid AS student_eeid, e.name AS enterprise_name
       FROM t_enterprise_eval ev
       LEFT JOIN t_user s ON ev.student_id = s.id
       LEFT JOIN t_enterprise e ON ev.enterprise_id = e.id
       ${where} ORDER BY ev.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query('SELECT * FROM t_enterprise_eval WHERE id = ? AND is_deleted = 0', [id]);
    return rows[0] || null;
  },

  async findByToken(token) {
    const [rows] = await pool.query(
      `SELECT ev.*, s.real_name AS student_name, e.name AS enterprise_name
       FROM t_enterprise_eval ev
       LEFT JOIN t_user s ON ev.student_id = s.id
       LEFT JOIN t_enterprise e ON ev.enterprise_id = e.id
       WHERE ev.token = ? AND ev.is_deleted = 0 LIMIT 1`, [token]
    );
    return rows[0] || null;
  },

  async create(ev) {
    const [r] = await pool.query(
      `INSERT INTO t_enterprise_eval (student_id, enterprise_id, assignment_id, college_id, token, mentor_name)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [ev.student_id, ev.enterprise_id || null, ev.assignment_id || null, ev.college_id || null, ev.token, ev.mentor_name || null]
    );
    return r.insertId;
  },

  async submitByToken(token, f) {
    const [r] = await pool.query(
      `UPDATE t_enterprise_eval
       SET mentor_name = ?, mentor_title = ?, score_overall = ?, score_attitude = ?,
           score_skill = ?, score_discipline = ?, comment = ?, status = 1, submit_time = NOW()
       WHERE token = ? AND is_deleted = 0`,
      [f.mentor_name || null, f.mentor_title || null, f.score_overall || null, f.score_attitude || null,
       f.score_skill || null, f.score_discipline || null, f.comment || null, token]
    );
    return r.affectedRows;
  },

  async remove(id) {
    await pool.query('UPDATE t_enterprise_eval SET is_deleted = 1 WHERE id = ?', [id]);
  }
};

module.exports = enterpriseEvalModel;
