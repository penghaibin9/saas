const pool = require('../config/db');

const collegeModel = {
  async findAll({ status, keyword } = {}) {
    let sql = 'SELECT * FROM t_college WHERE is_deleted = 0';
    const params = [];
    if (status !== undefined) { sql += ' AND status = ?'; params.push(status); }
    if (keyword) { sql += ' AND name LIKE ?'; params.push(`%${keyword}%`); }
    sql += ' ORDER BY create_time DESC';
    const [rows] = await pool.query(sql, params);
    return rows;
  },

  async findById(id) {
    const [rows] = await pool.query(
      'SELECT * FROM t_college WHERE id = ? AND is_deleted = 0',
      [id]
    );
    return rows[0] || null;
  },

  async findByCode(code) {
    const [rows] = await pool.query(
      'SELECT * FROM t_college WHERE code = ? AND is_deleted = 0',
      [code]
    );
    return rows[0] || null;
  },

  async create({ name, code, description, status = 1 }) {
    const [result] = await pool.query(
      'INSERT INTO t_college (name, code, description, status) VALUES (?, ?, ?, ?)',
      [name, code, description || null, status]
    );
    return result.insertId;
  },

  async update(id, { name, code, description, status }) {
    const fields = [];
    const params = [];
    if (name !== undefined)        { fields.push('name = ?');        params.push(name); }
    if (code !== undefined)        { fields.push('code = ?');        params.push(code); }
    if (description !== undefined) { fields.push('description = ?'); params.push(description); }
    if (status !== undefined)      { fields.push('status = ?');      params.push(status); }
    if (!fields.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_college SET ${fields.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_college SET is_deleted = 1 WHERE id = ?',
      [id]
    );
    return result.affectedRows;
  }
};

module.exports = collegeModel;
