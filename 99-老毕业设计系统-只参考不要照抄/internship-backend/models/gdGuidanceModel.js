const pool = require('../config/db');

const gdGuidanceModel = {
  async findAll({ studentId, teacherId, collegeId, topicId } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE g.is_deleted = 0';
    const params = [];
    if (studentId !== undefined) { where += ' AND g.student_id = ?'; params.push(studentId); }
    if (teacherId !== undefined) { where += ' AND g.teacher_id = ?'; params.push(teacherId); }
    if (collegeId !== undefined) { where += ' AND g.college_id = ?'; params.push(collegeId); }
    if (topicId !== undefined)   { where += ' AND g.topic_id = ?';   params.push(topicId); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_gd_guidance g ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT g.*, s.real_name AS student_name, s.eeid AS student_eeid, t.real_name AS teacher_name
       FROM t_gd_guidance g
       LEFT JOIN t_user s ON g.student_id = s.id
       LEFT JOIN t_user t ON g.teacher_id = t.id
       ${where} ORDER BY g.guidance_date DESC, g.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT g.*, s.real_name AS student_name, t.real_name AS teacher_name
       FROM t_gd_guidance g
       LEFT JOIN t_user s ON g.student_id = s.id
       LEFT JOIN t_user t ON g.teacher_id = t.id
       WHERE g.id = ? AND g.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async create(g) {
    const [result] = await pool.query(
      `INSERT INTO t_gd_guidance
        (topic_id, student_id, teacher_id, college_id, title, content, guidance_date, file_url)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [g.topic_id || null, g.student_id, g.teacher_id, g.college_id || null,
       g.title || null, g.content || null, g.guidance_date || null, g.file_url || null]
    );
    return result.insertId;
  },

  async update(id, fields) {
    const allowed = ['title', 'content', 'guidance_date', 'file_url', 'topic_id'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_gd_guidance SET ${setClauses.join(', ')} WHERE id = ? AND is_deleted = 0`, params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query('UPDATE t_gd_guidance SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  }
};

module.exports = gdGuidanceModel;
