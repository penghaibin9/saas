const pool = require('../config/db');

const satisfactionModel = {
  async findAll({ enterpriseId, collegeId, studentId } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE sf.is_deleted = 0';
    const params = [];
    if (enterpriseId !== undefined) { where += ' AND sf.enterprise_id = ?'; params.push(enterpriseId); }
    if (collegeId !== undefined)    { where += ' AND sf.college_id = ?';    params.push(collegeId); }
    if (studentId !== undefined)    { where += ' AND sf.student_id = ?';    params.push(studentId); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_satisfaction sf ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT sf.*, e.name AS enterprise_name, s.real_name AS student_name, u.real_name AS author_name
       FROM t_satisfaction sf
       LEFT JOIN t_enterprise e ON sf.enterprise_id = e.id
       LEFT JOIN t_user s ON sf.student_id = s.id
       LEFT JOIN t_user u ON sf.created_by = u.id
       ${where} ORDER BY sf.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT sf.*, e.name AS enterprise_name FROM t_satisfaction sf
       LEFT JOIN t_enterprise e ON sf.enterprise_id = e.id
       WHERE sf.id = ? AND sf.is_deleted = 0`, [id]);
    return rows[0] || null;
  },

  async create(s) {
    const [result] = await pool.query(
      `INSERT INTO t_satisfaction (enterprise_id, student_id, college_id, score, content, created_by)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [s.enterprise_id, s.student_id || null, s.college_id || null, s.score, s.content || null, s.created_by || null]
    );
    return result.insertId;
  },

  async remove(id) {
    const [result] = await pool.query('UPDATE t_satisfaction SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  },

  // 各企业平均满意度（用于可视化）
  async byEnterprise(collegeId) {
    let where = 'WHERE sf.is_deleted = 0';
    const params = [];
    if (collegeId !== undefined) { where += ' AND sf.college_id = ?'; params.push(collegeId); }
    const [rows] = await pool.query(
      `SELECT e.name AS enterprise_name, ROUND(AVG(sf.score), 2) AS avg_score, COUNT(*) AS cnt
       FROM t_satisfaction sf
       LEFT JOIN t_enterprise e ON sf.enterprise_id = e.id
       ${where} GROUP BY sf.enterprise_id, e.name ORDER BY avg_score DESC LIMIT 20`, params);
    return rows;
  },

  async overall(collegeId) {
    let where = 'WHERE is_deleted = 0';
    const params = [];
    if (collegeId !== undefined) { where += ' AND college_id = ?'; params.push(collegeId); }
    const [[r]] = await pool.query(
      `SELECT COUNT(*) AS total, ROUND(AVG(score), 2) AS avg_score,
              SUM(CASE WHEN score >= 4 THEN 1 ELSE 0 END) AS satisfied
       FROM t_satisfaction ${where}`, params);
    return r;
  }
};

module.exports = satisfactionModel;
