const pool = require('../config/db');

// 电子实习协议。status: 0待签署 1签署中 2已生效 3已作废
const agreementModel = {
  async findAll({ studentId, teacherId, collegeId, status } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE ag.is_deleted = 0';
    const params = [];
    if (studentId !== undefined) { where += ' AND ag.student_id = ?'; params.push(studentId); }
    if (teacherId !== undefined) { where += ' AND ag.teacher_id = ?'; params.push(teacherId); }
    if (collegeId !== undefined) { where += ' AND ag.college_id = ?'; params.push(collegeId); }
    if (status !== undefined)    { where += ' AND ag.status = ?';     params.push(status); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_agreement ag ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT ag.*, s.real_name AS student_name, s.eeid AS student_eeid,
              t.real_name AS teacher_name, e.name AS enterprise_name, p.title AS position_title
       FROM t_agreement ag
       LEFT JOIN t_user s ON ag.student_id = s.id
       LEFT JOIN t_user t ON ag.teacher_id = t.id
       LEFT JOIN t_enterprise e ON ag.enterprise_id = e.id
       LEFT JOIN t_position p ON ag.position_id = p.id
       ${where} ORDER BY ag.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT ag.*, s.real_name AS student_name, s.eeid AS student_eeid,
              t.real_name AS teacher_name, e.name AS enterprise_name, p.title AS position_title
       FROM t_agreement ag
       LEFT JOIN t_user s ON ag.student_id = s.id
       LEFT JOIN t_user t ON ag.teacher_id = t.id
       LEFT JOIN t_enterprise e ON ag.enterprise_id = e.id
       LEFT JOIN t_position p ON ag.position_id = p.id
       WHERE ag.id = ? AND ag.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async create(a) {
    const [result] = await pool.query(
      `INSERT INTO t_agreement
        (student_id, application_id, enterprise_id, position_id, teacher_id, college_id,
         title, content, start_date, end_date, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)`,
      [a.student_id, a.application_id || null, a.enterprise_id || null, a.position_id || null,
       a.teacher_id || null, a.college_id || null, a.title, a.content || null,
       a.start_date || null, a.end_date || null]
    );
    return result.insertId;
  },

  async studentSign(id, signName) {
    await pool.query(
      `UPDATE t_agreement
       SET student_signed = 1, student_sign_name = ?, student_sign_time = NOW(),
           status = CASE WHEN status = 0 THEN 1 ELSE status END
       WHERE id = ? AND is_deleted = 0`,
      [signName, id]
    );
  },

  async teacherSign(id) {
    await pool.query(
      `UPDATE t_agreement
       SET teacher_signed = 1, teacher_sign_time = NOW(),
           status = CASE WHEN status = 0 THEN 1 ELSE status END
       WHERE id = ? AND is_deleted = 0`,
      [id]
    );
  },

  // 校方盖章并生效（要求三方均已签署）
  async schoolActivate(id) {
    await pool.query(
      `UPDATE t_agreement
       SET school_signed = 1, school_sign_time = NOW(), status = 2
       WHERE id = ? AND is_deleted = 0`,
      [id]
    );
  },

  async voidAgreement(id) {
    await pool.query(`UPDATE t_agreement SET status = 3 WHERE id = ? AND is_deleted = 0`, [id]);
  },

  async remove(id) {
    await pool.query(`UPDATE t_agreement SET is_deleted = 1 WHERE id = ?`, [id]);
  }
};

module.exports = agreementModel;
