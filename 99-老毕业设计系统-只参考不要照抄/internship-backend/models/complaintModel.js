const pool = require('../config/db');

// 投诉/异常/安全上报。status: 0待处理 1处理中 2已处理 3已关闭
const complaintModel = {
  async findAll({ status, category, collegeId, studentId, reporterId, keyword } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE c.is_deleted = 0';
    const params = [];
    if (status !== undefined)     { where += ' AND c.status = ?';      params.push(status); }
    if (category !== undefined)   { where += ' AND c.category = ?';    params.push(category); }
    if (collegeId !== undefined)  { where += ' AND c.college_id = ?';  params.push(collegeId); }
    if (studentId !== undefined)  { where += ' AND c.student_id = ?';  params.push(studentId); }
    if (reporterId !== undefined) { where += ' AND c.reporter_id = ?'; params.push(reporterId); }
    if (keyword) { where += ' AND (c.title LIKE ? OR c.content LIKE ?)'; params.push(`%${keyword}%`, `%${keyword}%`); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_complaint c ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT c.*, s.real_name AS student_name, s.eeid AS student_eeid,
              r.real_name AS reporter_name, h.real_name AS handler_name
       FROM t_complaint c
       LEFT JOIN t_user s ON c.student_id = s.id
       LEFT JOIN t_user r ON c.reporter_id = r.id
       LEFT JOIN t_user h ON c.handler_id = h.id
       ${where} ORDER BY c.status ASC, c.urgency DESC, c.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT c.*, s.real_name AS student_name, r.real_name AS reporter_name, h.real_name AS handler_name
       FROM t_complaint c
       LEFT JOIN t_user s ON c.student_id = s.id
       LEFT JOIN t_user r ON c.reporter_id = r.id
       LEFT JOIN t_user h ON c.handler_id = h.id
       WHERE c.id = ? AND c.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async create(c) {
    const [result] = await pool.query(
      `INSERT INTO t_complaint
        (category, title, content, student_id, reporter_id, reporter_role, contact_phone, college_id, urgency)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [c.category || 'complaint', c.title, c.content || null, c.student_id || null,
       c.reporter_id || null, c.reporter_role || null, c.contact_phone || null,
       c.college_id || null, c.urgency ?? 1]
    );
    return result.insertId;
  },

  async handle(id, { status, handle_remark, handler_id }) {
    const [result] = await pool.query(
      `UPDATE t_complaint SET status = ?, handle_remark = ?, handler_id = ?, handle_time = NOW()
       WHERE id = ? AND is_deleted = 0`,
      [status, handle_remark || null, handler_id || null, id]
    );
    return result.affectedRows;
  },

  // 各状态计数（用于角标/概览），按可选学院范围
  async countByStatus(collegeId) {
    const where = collegeId ? 'WHERE is_deleted = 0 AND college_id = ?' : 'WHERE is_deleted = 0';
    const params = collegeId ? [collegeId] : [];
    const [rows] = await pool.query(
      `SELECT status, COUNT(*) AS cnt FROM t_complaint ${where} GROUP BY status`, params
    );
    const out = { pending: 0, processing: 0, done: 0, closed: 0, total: 0 };
    for (const r of rows) {
      out.total += r.cnt;
      if (r.status === 0) out.pending = r.cnt;
      else if (r.status === 1) out.processing = r.cnt;
      else if (r.status === 2) out.done = r.cnt;
      else if (r.status === 3) out.closed = r.cnt;
    }
    return out;
  }
};

module.exports = complaintModel;
