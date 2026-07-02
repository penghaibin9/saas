const pool = require('../config/db');

// 毕业设计选题及指导老师。status: 0待确认 1已指派 2已确认
const gdTopicModel = {
  async findAll({ collegeId, majorId, classId, teacherId, studentId, status, keyword } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE tp.is_deleted = 0';
    const params = [];
    if (collegeId !== undefined) { where += ' AND tp.college_id = ?'; params.push(collegeId); }
    if (majorId !== undefined)   { where += ' AND tp.major_id = ?';   params.push(majorId); }
    if (classId !== undefined)   { where += ' AND tp.class_id = ?';   params.push(classId); }
    if (teacherId !== undefined) { where += ' AND tp.teacher_id = ?'; params.push(teacherId); }
    if (studentId !== undefined) { where += ' AND tp.student_id = ?'; params.push(studentId); }
    if (status !== undefined)    { where += ' AND tp.status = ?';     params.push(status); }
    if (keyword)                 { where += ' AND tp.title LIKE ?';   params.push(`%${keyword}%`); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_gd_topic tp ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT tp.*, s.real_name AS student_name, s.eeid AS student_eeid,
              t.real_name AS teacher_name, cl.name AS class_name
       FROM t_gd_topic tp
       LEFT JOIN t_user s  ON tp.student_id = s.id
       LEFT JOIN t_user t  ON tp.teacher_id = t.id
       LEFT JOIN t_class cl ON tp.class_id = cl.id
       ${where} ORDER BY tp.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT tp.*, s.real_name AS student_name, s.eeid AS student_eeid,
              s.college_id AS student_college_id, t.real_name AS teacher_name
       FROM t_gd_topic tp
       LEFT JOIN t_user s ON tp.student_id = s.id
       LEFT JOIN t_user t ON tp.teacher_id = t.id
       WHERE tp.id = ? AND tp.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async create(t, conn = pool) {
    const [result] = await conn.query(
      `INSERT INTO t_gd_topic
        (title, student_id, teacher_id, college_id, major_id, class_id, source, type, description, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [t.title, t.student_id || null, t.teacher_id || null, t.college_id || null,
       t.major_id || null, t.class_id || null, t.source || null, t.type || null,
       t.description || null, t.status ?? (t.teacher_id ? 1 : 0)]
    );
    return result.insertId;
  },

  async update(id, fields) {
    const allowed = ['title', 'student_id', 'teacher_id', 'college_id', 'major_id', 'class_id', 'source', 'type', 'description', 'status'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_gd_topic SET ${setClauses.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query('UPDATE t_gd_topic SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  }
};

module.exports = gdTopicModel;
