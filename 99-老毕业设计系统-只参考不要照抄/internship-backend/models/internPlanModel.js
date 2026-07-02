const pool = require('../config/db');

// status: 1申报 2通过 3开启 4结束 5驳回
const PLAN_FIELDS = `
  p.id, p.college_id, p.major_id, p.class_id, p.title, p.start_date, p.end_date,
  p.purpose, p.content, p.requirement, p.checkin_count, p.weekly_count, p.monthly_count,
  p.summary_required, p.materials, p.assess_method, p.attachment_url, p.status,
  p.reject_reason, p.created_by, p.create_time, p.update_time
`;

const internPlanModel = {
  async findAll({ collegeId, majorId, classId, status, openedOnly } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE p.is_deleted = 0';
    const params = [];
    if (collegeId !== undefined) { where += ' AND p.college_id = ?'; params.push(collegeId); }
    if (majorId !== undefined)   { where += ' AND (p.major_id = ? OR p.major_id IS NULL)'; params.push(majorId); }
    if (classId !== undefined)   { where += ' AND (p.class_id = ? OR p.class_id IS NULL)'; params.push(classId); }
    if (status !== undefined)    { where += ' AND p.status = ?'; params.push(status); }
    if (openedOnly)              { where += ' AND p.status IN (3, 4)'; }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_intern_plan p ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT ${PLAN_FIELDS},
              c.name AS college_name, m.name AS major_name, cl.name AS class_name,
              u.real_name AS created_by_name
       FROM t_intern_plan p
       LEFT JOIN t_college c ON p.college_id = c.id
       LEFT JOIN t_major m   ON p.major_id = m.id
       LEFT JOIN t_class cl  ON p.class_id = cl.id
       LEFT JOIN t_user u    ON p.created_by = u.id
       ${where} ORDER BY p.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT ${PLAN_FIELDS},
              c.name AS college_name, m.name AS major_name, cl.name AS class_name,
              u.real_name AS created_by_name
       FROM t_intern_plan p
       LEFT JOIN t_college c ON p.college_id = c.id
       LEFT JOIN t_major m   ON p.major_id = m.id
       LEFT JOIN t_class cl  ON p.class_id = cl.id
       LEFT JOIN t_user u    ON p.created_by = u.id
       WHERE p.id = ? AND p.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async create(plan) {
    const [result] = await pool.query(
      `INSERT INTO t_intern_plan
        (college_id, major_id, class_id, title, start_date, end_date, purpose, content,
         requirement, checkin_count, weekly_count, monthly_count, summary_required,
         materials, assess_method, attachment_url, status, created_by)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)`,
      [
        plan.college_id, plan.major_id || null, plan.class_id || null, plan.title,
        plan.start_date || null, plan.end_date || null, plan.purpose || null, plan.content || null,
        plan.requirement || null, plan.checkin_count || 0, plan.weekly_count || 0,
        plan.monthly_count || 0, plan.summary_required ?? 1, plan.materials || null,
        plan.assess_method || null, plan.attachment_url || null, plan.created_by || null
      ]
    );
    return result.insertId;
  },

  async update(id, fields) {
    const allowed = ['major_id','class_id','title','start_date','end_date','purpose','content',
      'requirement','checkin_count','weekly_count','monthly_count','summary_required',
      'materials','assess_method','attachment_url'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_intern_plan SET ${setClauses.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async updateStatus(id, status, rejectReason) {
    const [result] = await pool.query(
      `UPDATE t_intern_plan SET status = ?, reject_reason = ? WHERE id = ? AND is_deleted = 0`,
      [status, rejectReason || null, id]
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_intern_plan SET is_deleted = 1 WHERE id = ?', [id]
    );
    return result.affectedRows;
  }
};

module.exports = internPlanModel;
