const pool = require('../config/db');

const insuranceModel = {
  async findAll({ studentId, collegeId, keyword } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE i.is_deleted = 0';
    const params = [];
    if (studentId !== undefined) { where += ' AND i.student_id = ?'; params.push(studentId); }
    if (collegeId !== undefined) { where += ' AND i.college_id = ?'; params.push(collegeId); }
    if (keyword) {
      where += ' AND (s.real_name LIKE ? OR s.eeid LIKE ? OR i.policy_no LIKE ?)';
      params.push(`%${keyword}%`, `%${keyword}%`, `%${keyword}%`);
    }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_insurance i
       LEFT JOIN t_user s ON i.student_id = s.id ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT i.*, s.real_name AS student_name, s.eeid AS student_eeid
       FROM t_insurance i
       LEFT JOIN t_user s ON i.student_id = s.id
       ${where} ORDER BY i.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT i.*, s.real_name AS student_name, s.college_id AS student_college_id
       FROM t_insurance i LEFT JOIN t_user s ON i.student_id = s.id
       WHERE i.id = ? AND i.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async create(i) {
    const [result] = await pool.query(
      `INSERT INTO t_insurance
        (student_id, insurance_type, policy_no, company, start_date, end_date, college_id, remark)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [i.student_id, i.insurance_type || null, i.policy_no || null, i.company || null,
       i.start_date || null, i.end_date || null, i.college_id || null, i.remark || null]
    );
    return result.insertId;
  },

  async update(id, fields) {
    const allowed = ['insurance_type', 'policy_no', 'company', 'start_date', 'end_date', 'remark'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_insurance SET ${setClauses.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query('UPDATE t_insurance SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  },

  // 即将到期的保单（end_date 在未来 days 天内，含已过期 grace 天内）。用于到期预警。
  async findExpiringSoon(days = 15) {
    const [rows] = await pool.query(
      `SELECT i.*, s.real_name AS student_name, s.eeid AS student_eeid, s.phone AS student_phone,
              DATEDIFF(i.end_date, CURDATE()) AS days_left
       FROM t_insurance i
       JOIN t_user s ON i.student_id = s.id
       WHERE i.is_deleted = 0 AND i.end_date IS NOT NULL
         AND i.end_date <= DATE_ADD(CURDATE(), INTERVAL ? DAY)
         AND i.end_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
       ORDER BY i.end_date ASC`,
      [days]
    );
    return rows;
  },

  // 在册实习但无有效保险的学生（未投保 / 保险已过期）。用于未投保预警。
  async findUninsuredInterns(collegeId) {
    const scope = collegeId ? ' AND s.college_id = ?' : '';
    const params = collegeId ? [collegeId] : [];
    const [rows] = await pool.query(
      `SELECT DISTINCT s.id AS student_id, s.real_name AS student_name, s.eeid AS student_eeid,
              s.phone AS student_phone, s.college_id, e.name AS enterprise_name, t.real_name AS teacher_name
       FROM t_assignment a
       JOIN t_user s ON a.student_id = s.id
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       LEFT JOIN t_user t ON a.teacher_id = t.id
       WHERE a.status = 1 AND a.is_deleted = 0${scope}
         AND NOT EXISTS (
           SELECT 1 FROM t_insurance i
           WHERE i.student_id = s.id AND i.is_deleted = 0
             AND (i.end_date IS NULL OR i.end_date >= CURDATE())
         )
       ORDER BY s.college_id, s.eeid`,
      params
    );
    return rows;
  }
};

module.exports = insuranceModel;
