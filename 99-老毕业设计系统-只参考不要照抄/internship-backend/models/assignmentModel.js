const pool = require('../config/db');

// 实习分配：为学生指配指导老师 + 实习企业。status: 1有效 0移除
const assignmentModel = {
  async findAll({ planId, studentId, teacherId, enterpriseId, collegeId, status } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE a.is_deleted = 0';
    const params = [];
    if (planId !== undefined)       { where += ' AND a.plan_id = ?';       params.push(planId); }
    if (studentId !== undefined)    { where += ' AND a.student_id = ?';    params.push(studentId); }
    if (teacherId !== undefined)    { where += ' AND a.teacher_id = ?';    params.push(teacherId); }
    if (enterpriseId !== undefined) { where += ' AND a.enterprise_id = ?'; params.push(enterpriseId); }
    if (collegeId !== undefined)    { where += ' AND s.college_id = ?';    params.push(collegeId); }
    if (status !== undefined)       { where += ' AND a.status = ?';        params.push(status); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_assignment a
       LEFT JOIN t_user s ON a.student_id = s.id ${where}`,
      params
    );
    const [rows] = await pool.query(
      `SELECT a.*,
              s.real_name AS student_name, s.eeid AS student_eeid, s.college_id AS student_college_id,
              t.real_name AS teacher_name,
              e.name AS enterprise_name,
              p.title AS plan_title,
              p.start_date AS plan_start_date,
              p.end_date AS plan_end_date
       FROM t_assignment a
       LEFT JOIN t_user s       ON a.student_id = s.id
       LEFT JOIN t_user t       ON a.teacher_id = t.id
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       LEFT JOIN t_intern_plan p ON a.plan_id = p.id
       ${where} ORDER BY a.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT a.*,
              s.real_name AS student_name, s.eeid AS student_eeid, s.college_id AS student_college_id,
              t.real_name AS teacher_name,
              e.name AS enterprise_name, e.latitude, e.longitude, e.checkin_radius,
              p.title AS plan_title
       FROM t_assignment a
       LEFT JOIN t_user s       ON a.student_id = s.id
       LEFT JOIN t_user t       ON a.teacher_id = t.id
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       LEFT JOIN t_intern_plan p ON a.plan_id = p.id
       WHERE a.id = ? AND a.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  // 获取某学生当前有效的实习分配（含企业坐标，用于打卡校验）
  async findActiveByStudent(studentId) {
    const [rows] = await pool.query(
      `SELECT a.*, e.name AS enterprise_name, e.latitude, e.longitude, e.checkin_radius
       FROM t_assignment a
       LEFT JOIN t_enterprise e ON a.enterprise_id = e.id
       WHERE a.student_id = ? AND a.status = 1 AND a.is_deleted = 0
       ORDER BY a.create_time DESC LIMIT 1`,
      [studentId]
    );
    return rows[0] || null;
  },

  async findExisting(studentId, planId) {
    const [rows] = await pool.query(
      `SELECT * FROM t_assignment
       WHERE student_id = ? AND ((? IS NULL AND plan_id IS NULL) OR plan_id = ?)
         AND status = 1 AND is_deleted = 0 LIMIT 1`,
      [studentId, planId || null, planId || null]
    );
    return rows[0] || null;
  },

  async create({ plan_id, student_id, teacher_id, enterprise_id }, conn = pool) {
    const [result] = await conn.query(
      `INSERT INTO t_assignment (plan_id, student_id, teacher_id, enterprise_id, status)
       VALUES (?, ?, ?, ?, 1)`,
      [plan_id || null, student_id, teacher_id || null, enterprise_id || null]
    );
    return result.insertId;
  },

  async update(id, { teacher_id, enterprise_id, plan_id }) {
    const fields = [];
    const params = [];
    if (teacher_id !== undefined)    { fields.push('teacher_id = ?');    params.push(teacher_id); }
    if (enterprise_id !== undefined) { fields.push('enterprise_id = ?'); params.push(enterprise_id); }
    if (plan_id !== undefined)       { fields.push('plan_id = ?');       params.push(plan_id); }
    if (!fields.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_assignment SET ${fields.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  // 移除学生（置为移除状态）
  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_assignment SET status = 0, is_deleted = 1 WHERE id = ?', [id]
    );
    return result.affectedRows;
  }
};

module.exports = assignmentModel;
