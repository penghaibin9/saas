const pool = require('../config/db');

// 毕业设计成绩（每个学生一条，唯一）
const gdGradeModel = {
  async findAll({ collegeId, classId, teacherId, studentId, keyword } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE g.is_deleted = 0';
    const params = [];
    if (classId !== undefined)   { where += ' AND g.class_id = ?';   params.push(classId); }
    if (teacherId !== undefined) { where += ' AND g.teacher_id = ?'; params.push(teacherId); }
    if (studentId !== undefined) { where += ' AND g.student_id = ?'; params.push(studentId); }
    if (collegeId !== undefined) { where += ' AND s.college_id = ?'; params.push(collegeId); }
    if (keyword)                 { where += ' AND (s.real_name LIKE ? OR s.eeid LIKE ?)'; params.push(`%${keyword}%`, `%${keyword}%`); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_gd_grade g
       LEFT JOIN t_user s ON g.student_id = s.id ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT g.*, s.real_name AS student_name, s.eeid AS student_eeid,
              cl.name AS class_name, t.real_name AS teacher_name
       FROM t_gd_grade g
       LEFT JOIN t_user s   ON g.student_id = s.id
       LEFT JOIN t_class cl ON g.class_id = cl.id
       LEFT JOIN t_user t   ON g.teacher_id = t.id
       ${where} ORDER BY g.update_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findByStudent(studentId) {
    const [rows] = await pool.query(
      `SELECT g.*, s.real_name AS student_name, s.eeid AS student_eeid, t.real_name AS teacher_name
       FROM t_gd_grade g
       LEFT JOIN t_user s ON g.student_id = s.id
       LEFT JOIN t_user t ON g.teacher_id = t.id
       WHERE g.student_id = ? AND g.is_deleted = 0 LIMIT 1`,
      [studentId]
    );
    return rows[0] || null;
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT g.*, s.college_id AS student_college_id FROM t_gd_grade g
       LEFT JOIN t_user s ON g.student_id = s.id
       WHERE g.id = ? AND g.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  // 按学生 upsert：存在则更新，不存在则插入
  async upsert(g, conn = pool) {
    const [result] = await conn.query(
      `INSERT INTO t_gd_grade
        (student_id, topic_id, teacher_id, class_id, topic_title, review_score, defense_score, total_score, remark)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON DUPLICATE KEY UPDATE
         topic_id = VALUES(topic_id), teacher_id = VALUES(teacher_id), class_id = VALUES(class_id),
         topic_title = VALUES(topic_title), review_score = VALUES(review_score),
         defense_score = VALUES(defense_score), total_score = VALUES(total_score),
         remark = VALUES(remark), is_deleted = 0`,
      [g.student_id, g.topic_id || null, g.teacher_id || null, g.class_id || null,
       g.topic_title || null, g.review_score ?? null, g.defense_score ?? null,
       g.total_score ?? null, g.remark || null]
    );
    return result.insertId || result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query('UPDATE t_gd_grade SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  }
};

module.exports = gdGradeModel;
