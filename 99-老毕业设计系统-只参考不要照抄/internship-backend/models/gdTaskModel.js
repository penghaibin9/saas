const pool = require('../config/db');

// 毕业设计任务时间节点。status: 0未开始 1进行中 2已完成
const gdTaskModel = {
  async findAll({ collegeId, status, parentId, onlyRoot } = {}, { page = 1, pageSize = 50 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE t.is_deleted = 0';
    const params = [];
    if (collegeId !== undefined) { where += ' AND (t.college_id = ? OR t.college_id IS NULL)'; params.push(collegeId); }
    if (status !== undefined)    { where += ' AND t.status = ?'; params.push(status); }
    if (parentId !== undefined)  { where += ' AND t.parent_id = ?'; params.push(parentId); }
    if (onlyRoot)                { where += ' AND t.parent_id IS NULL'; }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_gd_task t ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT t.*, c.name AS college_name
       FROM t_gd_task t
       LEFT JOIN t_college c ON t.college_id = c.id
       ${where} ORDER BY t.sort_order ASC, t.require_time ASC, t.id ASC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT t.*, c.name AS college_name FROM t_gd_task t
       LEFT JOIN t_college c ON t.college_id = c.id
       WHERE t.id = ? AND t.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async create(t) {
    const [result] = await pool.query(
      `INSERT INTO t_gd_task
        (name, parent_id, scope, college_id, require_time, actual_time, description, status, sort_order)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [t.name, t.parent_id || null, t.scope || null, t.college_id || null,
       t.require_time || null, t.actual_time || null, t.description || null,
       t.status ?? 0, t.sort_order ?? 0]
    );
    return result.insertId;
  },

  async update(id, fields) {
    const allowed = ['name', 'parent_id', 'scope', 'college_id', 'require_time', 'actual_time', 'description', 'status', 'sort_order'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_gd_task SET ${setClauses.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    // 连带软删子任务
    await pool.query('UPDATE t_gd_task SET is_deleted = 1 WHERE parent_id = ?', [id]);
    const [result] = await pool.query('UPDATE t_gd_task SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  }
};

module.exports = gdTaskModel;
