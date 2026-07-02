const pool = require('../config/db');

const classModel = {
  async findAll({ collegeId, majorId, grade, status, keyword } = {}) {
    let sql = 'SELECT * FROM t_class WHERE is_deleted = 0';
    const params = [];
    if (collegeId !== undefined) { sql += ' AND college_id = ?'; params.push(collegeId); }
    if (majorId !== undefined)   { sql += ' AND major_id = ?';   params.push(majorId); }
    if (grade !== undefined)     { sql += ' AND grade = ?';      params.push(grade); }
    if (status !== undefined)    { sql += ' AND status = ?';     params.push(status); }
    if (keyword)                 { sql += ' AND name LIKE ?';    params.push(`%${keyword}%`); }
    sql += ' ORDER BY grade DESC, create_time DESC';
    const [rows] = await pool.query(sql, params);
    return rows;
  },

  async findById(id) {
    const [rows] = await pool.query(
      'SELECT * FROM t_class WHERE id = ? AND is_deleted = 0',
      [id]
    );
    return rows[0] || null;
  },

  async create({ major_id, college_id, name, grade, status = 1 }) {
    const [result] = await pool.query(
      'INSERT INTO t_class (major_id, college_id, name, grade, status) VALUES (?, ?, ?, ?, ?)',
      [major_id, college_id, name, grade, status]
    );
    return result.insertId;
  },

  async update(id, { major_id, college_id, name, grade, status }) {
    const fields = [];
    const params = [];
    if (major_id !== undefined)   { fields.push('major_id = ?');   params.push(major_id); }
    if (college_id !== undefined) { fields.push('college_id = ?'); params.push(college_id); }
    if (name !== undefined)       { fields.push('name = ?');       params.push(name); }
    if (grade !== undefined)      { fields.push('grade = ?');      params.push(grade); }
    if (status !== undefined)     { fields.push('status = ?');     params.push(status); }
    if (!fields.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_class SET ${fields.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_class SET is_deleted = 1 WHERE id = ?',
      [id]
    );
    return result.affectedRows;
  }
};

module.exports = classModel;
