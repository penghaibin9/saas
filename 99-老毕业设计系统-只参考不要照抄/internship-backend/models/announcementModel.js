const pool = require('../config/db');

const announcementModel = {
  async findAll({ category, collegeId, status, keyword, visibleCollegeId } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE a.is_deleted = 0';
    const params = [];
    if (category !== undefined) { where += ' AND a.category = ?'; params.push(category); }
    if (status !== undefined)   { where += ' AND a.status = ?';   params.push(status); }
    if (collegeId !== undefined){ where += ' AND a.college_id = ?'; params.push(collegeId); }
    // 可见性：全校(college_id 为空)或本学院
    if (visibleCollegeId !== undefined) {
      where += ' AND (a.college_id IS NULL OR a.college_id = ?)';
      params.push(visibleCollegeId);
    }
    if (keyword) { where += ' AND a.title LIKE ?'; params.push(`%${keyword}%`); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_announcement a ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT a.id, a.title, a.category, a.file_url, a.college_id, a.status,
              a.publish_time, a.create_time, a.update_time,
              c.name AS college_name, u.real_name AS publisher_name
       FROM t_announcement a
       LEFT JOIN t_college c ON a.college_id = c.id
       LEFT JOIN t_user u    ON a.publisher_id = u.id
       ${where} ORDER BY a.publish_time DESC, a.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT a.*, c.name AS college_name, u.real_name AS publisher_name
       FROM t_announcement a
       LEFT JOIN t_college c ON a.college_id = c.id
       LEFT JOIN t_user u    ON a.publisher_id = u.id
       WHERE a.id = ? AND a.is_deleted = 0`,
      [id]
    );
    return rows[0] || null;
  },

  async create(a) {
    const [result] = await pool.query(
      `INSERT INTO t_announcement
        (title, category, content, file_url, college_id, publisher_id, status, publish_time)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [a.title, a.category || '公示信息', a.content || null, a.file_url || null,
       a.college_id || null, a.publisher_id || null, a.status ?? 1,
       (a.status ?? 1) === 1 ? new Date() : null]
    );
    return result.insertId;
  },

  async update(id, fields) {
    const allowed = ['title', 'category', 'content', 'file_url', 'college_id', 'status'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    // 由草稿转为发布时补发布时间
    if (fields.status !== undefined && Number(fields.status) === 1) {
      setClauses.push('publish_time = COALESCE(publish_time, NOW())');
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_announcement SET ${setClauses.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_announcement SET is_deleted = 1 WHERE id = ?', [id]
    );
    return result.affectedRows;
  }
};

module.exports = announcementModel;
