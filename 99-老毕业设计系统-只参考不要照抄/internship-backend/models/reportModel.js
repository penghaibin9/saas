const pool = require('../config/db');

const reportModel = {
  async findAll({ studentId, teacherId, applicationId, status } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE r.is_deleted = 0';
    const params = [];
    if (studentId !== undefined)     { where += ' AND r.student_id = ?';     params.push(studentId); }
    if (applicationId !== undefined) { where += ' AND r.application_id = ?'; params.push(applicationId); }
    if (status !== undefined)        { where += ' AND r.status = ?';         params.push(status); }
    if (teacherId !== undefined) {
      where += ' AND a.teacher_id = ?'; params.push(teacherId);
    }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_report r
       LEFT JOIN t_application a ON r.application_id = a.id ${where}`,
      params
    );
    const [rows] = await pool.query(
      `SELECT r.*, u.real_name AS student_name, u.eeid AS student_eeid
       FROM t_report r
       LEFT JOIN t_application a ON r.application_id = a.id
       LEFT JOIN t_user u ON r.student_id = u.id
       ${where} ORDER BY r.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT r.*, u.real_name AS student_name, a.teacher_id
       FROM t_report r
       LEFT JOIN t_application a ON r.application_id = a.id
       LEFT JOIN t_user u ON r.student_id = u.id
       WHERE r.id = ? AND r.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async findByApplication(applicationId) {
    const [rows] = await pool.query(
      'SELECT * FROM t_report WHERE application_id = ? AND is_deleted = 0',
      [applicationId]
    );
    return rows[0] || null;
  },

  async create({ application_id, student_id, title, content, file_url }) {
    const [result] = await pool.query(
      `INSERT INTO t_report (application_id, student_id, title, content, file_url, status)
       VALUES (?, ?, ?, ?, ?, 0)`,
      [application_id, student_id, title, content || null, file_url || null]
    );
    return result.insertId;
  },

  async submit(id) {
    const [result] = await pool.query(
      'UPDATE t_report SET status = 1, submit_time = NOW() WHERE id = ? AND is_deleted = 0',
      [id]
    );
    return result.affectedRows;
  },

  async updateDraft(id, { title, content, file_url }) {
    const fields = [];
    const params = [];
    if (title !== undefined)    { fields.push('title = ?');    params.push(title); }
    if (content !== undefined)  { fields.push('content = ?');  params.push(content); }
    if (file_url !== undefined) { fields.push('file_url = ?'); params.push(file_url); }
    if (!fields.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_report SET ${fields.join(', ')} WHERE id = ? AND status = 0 AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async review(id, { teacher_score, teacher_comment }) {
    const [result] = await pool.query(
      `UPDATE t_report SET status = 2, teacher_score = ?, teacher_comment = ?
       WHERE id = ? AND status = 1 AND is_deleted = 0`,
      [teacher_score, teacher_comment || null, id]
    );
    return result.affectedRows;
  }
};

module.exports = reportModel;
