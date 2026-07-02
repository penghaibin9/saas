const pool = require('../config/db');

// change_type: transfer换岗 terminate终止
// status: 0待教师审 1待管理员审 2已执行 3已驳回
const assignmentChangeModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_assignment_change (
        id INT AUTO_INCREMENT PRIMARY KEY,
        assignment_id INT NOT NULL,
        student_id INT NOT NULL,
        change_type VARCHAR(16) NOT NULL COMMENT 'transfer|terminate',
        old_enterprise_id INT NULL,
        new_enterprise_id INT NULL,
        new_teacher_id INT NULL,
        reason TEXT NULL,
        status TINYINT DEFAULT 0,
        applicant_id INT NULL,
        applicant_role TINYINT NULL,
        teacher_opinion VARCHAR(255) NULL,
        admin_opinion VARCHAR(255) NULL,
        teacher_id INT NULL COMMENT '审批教师',
        handler_id INT NULL COMMENT '终审管理员',
        execute_time DATETIME NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='换岗/终止实习申请'
    `);
  },

  async findAll(filter = {}, { page = 1, pageSize = 20 } = {}) {
    let where = ' WHERE c.is_deleted = 0';
    const params = [];
    if (filter.status !== undefined) { where += ' AND c.status = ?'; params.push(filter.status); }
    if (filter.changeType) { where += ' AND c.change_type = ?'; params.push(filter.changeType); }
    if (filter.studentId) { where += ' AND c.student_id = ?'; params.push(filter.studentId); }
    if (filter.collegeId) { where += ' AND s.college_id = ?'; params.push(filter.collegeId); }
    if (filter.teacherId) { where += ' AND a.teacher_id = ?'; params.push(filter.teacherId); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_assignment_change c
       JOIN t_user s ON c.student_id = s.id
       JOIN t_assignment a ON c.assignment_id = a.id ${where}`, params
    );
    const offset = (page - 1) * pageSize;
    const [rows] = await pool.query(
      `SELECT c.*,
              s.real_name AS student_name, s.eeid AS student_eeid,
              oe.name AS old_enterprise_name, ne.name AS new_enterprise_name,
              t.real_name AS teacher_name, ap.real_name AS applicant_name
       FROM t_assignment_change c
       JOIN t_user s ON c.student_id = s.id
       JOIN t_assignment a ON c.assignment_id = a.id
       LEFT JOIN t_enterprise oe ON c.old_enterprise_id = oe.id
       LEFT JOIN t_enterprise ne ON c.new_enterprise_id = ne.id
       LEFT JOIN t_user t ON a.teacher_id = t.id
       LEFT JOIN t_user ap ON c.applicant_id = ap.id
       ${where} ORDER BY c.status ASC, c.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { list: rows, total, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT c.*, s.real_name AS student_name, s.college_id AS student_college_id,
              a.teacher_id, oe.name AS old_enterprise_name, ne.name AS new_enterprise_name
       FROM t_assignment_change c
       JOIN t_user s ON c.student_id = s.id
       JOIN t_assignment a ON c.assignment_id = a.id
       LEFT JOIN t_enterprise oe ON c.old_enterprise_id = oe.id
       LEFT JOIN t_enterprise ne ON c.new_enterprise_id = ne.id
       WHERE c.id = ? AND c.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async create(row) {
    const [r] = await pool.query(
      `INSERT INTO t_assignment_change
       (assignment_id, student_id, change_type, old_enterprise_id, new_enterprise_id,
        new_teacher_id, reason, applicant_id, applicant_role, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)`,
      [row.assignment_id, row.student_id, row.change_type, row.old_enterprise_id || null,
       row.new_enterprise_id || null, row.new_teacher_id || null, row.reason || null,
       row.applicant_id || null, row.applicant_role || null]
    );
    return r.insertId;
  },

  async findPendingByStudent(studentId) {
    const [rows] = await pool.query(
      `SELECT * FROM t_assignment_change WHERE student_id = ? AND status IN (0,1) AND is_deleted = 0 LIMIT 1`,
      [studentId]
    );
    return rows[0] || null;
  },

  async updateStatus(id, status, extra = {}) {
    const sets = ['status = ?'];
    const params = [status];
    ['teacher_opinion', 'admin_opinion', 'teacher_id', 'handler_id'].forEach(k => {
      if (extra[k] !== undefined) { sets.push(`${k} = ?`); params.push(extra[k]); }
    });
    if (status === 2) sets.push('execute_time = NOW()');
    params.push(id);
    const [r] = await pool.query(
      `UPDATE t_assignment_change SET ${sets.join(', ')} WHERE id = ? AND is_deleted = 0`, params
    );
    return r.affectedRows;
  }
};

module.exports = assignmentChangeModel;
