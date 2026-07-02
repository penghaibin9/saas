const pool = require('../config/db');

const provinceModel = {
  async findAll({ matched, uploaded, keyword, batchYear } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE is_deleted = 0';
    const params = [];
    if (matched !== undefined)   { where += ' AND matched = ?';   params.push(matched); }
    if (uploaded !== undefined)  { where += ' AND uploaded = ?';  params.push(uploaded); }
    if (batchYear !== undefined) { where += ' AND batch_year = ?'; params.push(batchYear); }
    if (keyword) { where += ' AND (name LIKE ? OR eeid LIKE ? OR id_card LIKE ?)'; params.push(`%${keyword}%`, `%${keyword}%`, `%${keyword}%`); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_province_student ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT * FROM t_province_student ${where} ORDER BY name LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query('SELECT * FROM t_province_student WHERE id = ? AND is_deleted = 0', [id]);
    return rows[0] || null;
  },

  async upsertByKey(s, conn = pool) {
    // 按 身份证/学号/姓名 去重：存在则更新，否则插入
    const [exist] = await conn.query(
      `SELECT id FROM t_province_student
       WHERE is_deleted = 0 AND (
         (id_card IS NOT NULL AND id_card = ?) OR
         (eeid IS NOT NULL AND eeid = ?) OR
         (name = ? AND major_name = ?)
       ) LIMIT 1`,
      [s.id_card || null, s.eeid || null, s.name, s.major_name || null]
    );
    if (exist.length) {
      await conn.query(
        `UPDATE t_province_student SET name=?, gender=?, id_card=?, eeid=?, cert_no=?,
            edu_system=?, major_code=?, major_name=?, batch_year=? WHERE id=?`,
        [s.name, s.gender || null, s.id_card || null, s.eeid || null, s.cert_no || null,
         s.edu_system || null, s.major_code || null, s.major_name || null, s.batch_year || null, exist[0].id]
      );
      return exist[0].id;
    }
    const [result] = await conn.query(
      `INSERT INTO t_province_student (name, gender, id_card, eeid, cert_no, edu_system, major_code, major_name, batch_year)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [s.name, s.gender || null, s.id_card || null, s.eeid || null, s.cert_no || null,
       s.edu_system || null, s.major_code || null, s.major_name || null, s.batch_year || null]
    );
    return result.insertId;
  },

  async setMatch(id, localStudentId) {
    await pool.query(
      'UPDATE t_province_student SET matched = ?, local_student_id = ? WHERE id = ?',
      [localStudentId ? 1 : 0, localStudentId || null, id]
    );
  },

  async markUploaded(id, link) {
    const [result] = await pool.query(
      'UPDATE t_province_student SET uploaded = 1, achievement_link = ?, upload_time = NOW() WHERE id = ? AND is_deleted = 0',
      [link || null, id]
    );
    return result.affectedRows;
  },

  async all() {
    const [rows] = await pool.query('SELECT * FROM t_province_student WHERE is_deleted = 0');
    return rows;
  }
};

module.exports = provinceModel;
