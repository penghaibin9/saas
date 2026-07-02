const pool = require('../config/db');

// status: 0待审核 1教师同意 2教师拒绝 3院校审核通过 4院校审核拒绝 5已录用 6未录用
const applicationModel = {
  async findAll({ studentId, positionId, enterpriseId, teacherId, status, collegeId } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE a.is_deleted = 0';
    const params = [];
    if (studentId !== undefined)    { where += ' AND a.student_id = ?';    params.push(studentId); }
    if (positionId !== undefined)   { where += ' AND a.position_id = ?';   params.push(positionId); }
    if (enterpriseId !== undefined) { where += ' AND a.enterprise_id = ?'; params.push(enterpriseId); }
    if (teacherId !== undefined)    { where += ' AND a.teacher_id = ?';    params.push(teacherId); }
    if (status !== undefined)       { where += ' AND a.status = ?';        params.push(status); }
    if (collegeId !== undefined)    { where += ' AND u.college_id = ?';    params.push(collegeId); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_application a
       LEFT JOIN t_user u ON a.student_id = u.id ${where}`,
      params
    );
    const [rows] = await pool.query(
      `SELECT a.*,
              u.real_name AS student_name, u.eeid AS student_eeid,
              p.title AS position_title,
              e.name AS enterprise_name,
              t.real_name AS teacher_name
       FROM t_application a
       LEFT JOIN t_user u       ON a.student_id = u.id
       LEFT JOIN t_position p   ON a.position_id = p.id
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       LEFT JOIN t_user t       ON a.teacher_id = t.id
       ${where} ORDER BY a.apply_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT a.*,
              u.real_name AS student_name, u.eeid AS student_eeid, u.college_id AS student_college_id,
              p.title AS position_title, p.headcount,
              e.name AS enterprise_name,
              t.real_name AS teacher_name
       FROM t_application a
       LEFT JOIN t_user u       ON a.student_id = u.id
       LEFT JOIN t_position p   ON a.position_id = p.id
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       LEFT JOIN t_user t       ON a.teacher_id = t.id
       WHERE a.id = ? AND a.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async findByStudentAndPosition(studentId, positionId) {
    const [rows] = await pool.query(
      'SELECT * FROM t_application WHERE student_id = ? AND position_id = ? AND is_deleted = 0',
      [studentId, positionId]
    );
    return rows[0] || null;
  },

  async create({ student_id, position_id, enterprise_id, teacher_id, student_remark }) {
    const [result] = await pool.query(
      `INSERT INTO t_application (student_id, position_id, enterprise_id, teacher_id, student_remark, status)
       VALUES (?, ?, ?, ?, ?, 0)`,
      [student_id, position_id, enterprise_id, teacher_id || null, student_remark || null]
    );
    return result.insertId;
  },

  async updateStatus(id, { status, teacher_opinion, admin_opinion }) {
    const fields = ['status = ?'];
    const params = [status];
    if (teacher_opinion !== undefined) { fields.push('teacher_opinion = ?'); params.push(teacher_opinion); }
    if (admin_opinion !== undefined)   { fields.push('admin_opinion = ?');   params.push(admin_opinion); }
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_application SET ${fields.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async countByPositionAndStatus(positionId, status) {
    const [[{ total }]] = await pool.query(
      'SELECT COUNT(*) AS total FROM t_application WHERE position_id = ? AND status = ? AND is_deleted = 0',
      [positionId, status]
    );
    return total;
  },

  async assignTeacher(id, teacherId) {
    const [result] = await pool.query(
      'UPDATE t_application SET teacher_id = ? WHERE id = ? AND is_deleted = 0',
      [teacherId, id]
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_application SET is_deleted = 1 WHERE id = ?',
      [id]
    );
    return result.affectedRows;
  }
};

module.exports = applicationModel;
