const pool = require('../config/db');

// 教师工作记录（月报/寻访）。status: 0草稿 1已提交
const teacherRecordModel = {
  async findAll({ teacherId, type, status, collegeId } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE r.is_deleted = 0';
    const params = [];
    if (teacherId !== undefined) { where += ' AND r.teacher_id = ?'; params.push(teacherId); }
    if (type !== undefined)      { where += ' AND r.type = ?';       params.push(type); }
    if (status !== undefined)    { where += ' AND r.status = ?';     params.push(status); }
    if (collegeId !== undefined) { where += ' AND r.college_id = ?'; params.push(collegeId); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_teacher_record r ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT r.*, t.real_name AS teacher_name, s.real_name AS student_name, e.name AS enterprise_name
       FROM t_teacher_record r
       LEFT JOIN t_user t ON r.teacher_id = t.id
       LEFT JOIN t_user s ON r.student_id = s.id
       LEFT JOIN t_enterprise e ON r.enterprise_id = e.id
       ${where} ORDER BY r.record_date DESC, r.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT r.*, t.real_name AS teacher_name, s.real_name AS student_name, e.name AS enterprise_name
       FROM t_teacher_record r
       LEFT JOIN t_user t ON r.teacher_id = t.id
       LEFT JOIN t_user s ON r.student_id = s.id
       LEFT JOIN t_enterprise e ON r.enterprise_id = e.id
       WHERE r.id = ? AND r.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async create(r) {
    const [result] = await pool.query(
      `INSERT INTO t_teacher_record
        (teacher_id, type, title, content, file_url, record_date, student_id, enterprise_id, college_id, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [r.teacher_id, r.type || 'monthly', r.title, r.content || null, r.file_url || null,
       r.record_date || null, r.student_id || null, r.enterprise_id || null, r.college_id || null, r.status ?? 0]
    );
    return result.insertId;
  },

  async update(id, fields) {
    const allowed = ['title', 'content', 'file_url', 'record_date', 'student_id', 'enterprise_id', 'type'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_teacher_record SET ${setClauses.join(', ')} WHERE id = ? AND status = 0 AND is_deleted = 0`, params
    );
    return result.affectedRows;
  },

  async submit(id) {
    const [result] = await pool.query(
      'UPDATE t_teacher_record SET status = 1 WHERE id = ? AND is_deleted = 0', [id]
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query('UPDATE t_teacher_record SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  }
};

module.exports = teacherRecordModel;
