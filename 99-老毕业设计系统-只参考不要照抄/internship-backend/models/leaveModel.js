const pool = require('../config/db');

// 请假申请。status: 0草稿 1提交 2通过 3驳回
const leaveModel = {
  async findAll({ studentId, teacherId, status, collegeId } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE lv.is_deleted = 0';
    const params = [];
    if (studentId !== undefined) { where += ' AND lv.student_id = ?'; params.push(studentId); }
    if (teacherId !== undefined) { where += ' AND lv.teacher_id = ?'; params.push(teacherId); }
    if (status !== undefined)    { where += ' AND lv.status = ?';     params.push(status); }
    if (collegeId !== undefined) { where += ' AND s.college_id = ?';  params.push(collegeId); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_leave lv
       LEFT JOIN t_user s ON lv.student_id = s.id ${where}`,
      params
    );
    const [rows] = await pool.query(
      `SELECT lv.*, s.real_name AS student_name, s.eeid AS student_eeid
       FROM t_leave lv
       LEFT JOIN t_user s ON lv.student_id = s.id
       ${where} ORDER BY lv.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT lv.*, s.real_name AS student_name, s.eeid AS student_eeid, s.college_id AS student_college_id
       FROM t_leave lv
       LEFT JOIN t_user s ON lv.student_id = s.id
       WHERE lv.id = ? AND lv.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async create(lv) {
    const [result] = await pool.query(
      `INSERT INTO t_leave
        (student_id, assignment_id, teacher_id, start_date, end_date, days, reason, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, 0)`,
      [lv.student_id, lv.assignment_id || null, lv.teacher_id || null,
       lv.start_date || null, lv.end_date || null, lv.days ?? null, lv.reason || null]
    );
    return result.insertId;
  },

  async updateDraft(id, { start_date, end_date, days, reason }) {
    const fields = [];
    const params = [];
    if (start_date !== undefined) { fields.push('start_date = ?'); params.push(start_date); }
    if (end_date !== undefined)   { fields.push('end_date = ?');   params.push(end_date); }
    if (days !== undefined)       { fields.push('days = ?');       params.push(days); }
    if (reason !== undefined)     { fields.push('reason = ?');     params.push(reason); }
    if (!fields.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_leave SET ${fields.join(', ')} WHERE id = ? AND status = 0 AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async submit(id) {
    const [result] = await pool.query(
      'UPDATE t_leave SET status = 1, submit_time = NOW() WHERE id = ? AND status IN (0, 3) AND is_deleted = 0',
      [id]
    );
    return result.affectedRows;
  },

  async review(id, { agree, reject_reason }) {
    const [result] = await pool.query(
      `UPDATE t_leave SET status = ?, reject_reason = ?, review_time = NOW()
       WHERE id = ? AND status = 1 AND is_deleted = 0`,
      [agree ? 2 : 3, agree ? null : (reject_reason || null), id]
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_leave SET is_deleted = 1 WHERE id = ?', [id]
    );
    return result.affectedRows;
  }
};

module.exports = leaveModel;
