const pool = require('../config/db');

// 实习周报/月报。type: weekly/monthly  status: 0草稿 1提交 2通过 3驳回
const internLogModel = {
  async findAll({ studentId, teacherId, type, status, collegeId } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE l.is_deleted = 0';
    const params = [];
    if (studentId !== undefined) { where += ' AND l.student_id = ?'; params.push(studentId); }
    if (teacherId !== undefined) { where += ' AND l.teacher_id = ?'; params.push(teacherId); }
    if (type !== undefined)      { where += ' AND l.type = ?';       params.push(type); }
    if (status !== undefined)    { where += ' AND l.status = ?';     params.push(status); }
    if (collegeId !== undefined) { where += ' AND s.college_id = ?'; params.push(collegeId); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_intern_log l
       LEFT JOIN t_user s ON l.student_id = s.id ${where}`,
      params
    );
    const [rows] = await pool.query(
      `SELECT l.*, s.real_name AS student_name, s.eeid AS student_eeid
       FROM t_intern_log l
       LEFT JOIN t_user s ON l.student_id = s.id
       ${where} ORDER BY l.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT l.*, s.real_name AS student_name, s.eeid AS student_eeid, s.college_id AS student_college_id
       FROM t_intern_log l
       LEFT JOIN t_user s ON l.student_id = s.id
       WHERE l.id = ? AND l.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async countByStudentAndType(studentId, type, onlySubmitted = true) {
    let sql = 'SELECT COUNT(*) AS total FROM t_intern_log WHERE student_id = ? AND type = ? AND is_deleted = 0';
    const params = [studentId, type];
    if (onlySubmitted) sql += ' AND status IN (1, 2)';
    const [[{ total }]] = await pool.query(sql, params);
    return total;
  },

  async create(log) {
    const [result] = await pool.query(
      `INSERT INTO t_intern_log
        (student_id, assignment_id, plan_id, teacher_id, type, title, content, file_url, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)`,
      [log.student_id, log.assignment_id || null, log.plan_id || null, log.teacher_id || null,
       log.type || 'weekly', log.title, log.content || null, log.file_url || null]
    );
    return result.insertId;
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
      `UPDATE t_intern_log SET ${fields.join(', ')} WHERE id = ? AND status = 0 AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async submit(id) {
    const [result] = await pool.query(
      'UPDATE t_intern_log SET status = 1, submit_time = NOW() WHERE id = ? AND status IN (0, 3) AND is_deleted = 0',
      [id]
    );
    return result.affectedRows;
  },

  async review(id, { agree, teacher_comment, reject_reason }) {
    const [result] = await pool.query(
      `UPDATE t_intern_log
       SET status = ?, teacher_comment = ?, reject_reason = ?, review_time = NOW()
       WHERE id = ? AND status = 1 AND is_deleted = 0`,
      [agree ? 2 : 3, teacher_comment || null, agree ? null : (reject_reason || null), id]
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_intern_log SET is_deleted = 1 WHERE id = ?', [id]
    );
    return result.affectedRows;
  }
};

module.exports = internLogModel;
