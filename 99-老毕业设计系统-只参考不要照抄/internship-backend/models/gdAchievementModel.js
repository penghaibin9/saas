const pool = require('../config/db');

// 毕业设计成果上传/审阅。status: 0待审阅 1通过 2驳回 3未完成
const gdAchievementModel = {
  async findAll({ studentId, teacherId, status, collegeId, docType } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE ac.is_deleted = 0';
    const params = [];
    if (studentId !== undefined) { where += ' AND ac.student_id = ?'; params.push(studentId); }
    if (teacherId !== undefined) { where += ' AND ac.teacher_id = ?'; params.push(teacherId); }
    if (status !== undefined)    { where += ' AND ac.status = ?';     params.push(status); }
    if (collegeId !== undefined) { where += ' AND s.college_id = ?';  params.push(collegeId); }
    if (docType)                 { where += ' AND ac.doc_type = ?';   params.push(docType); }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_gd_achievement ac
       LEFT JOIN t_user s ON ac.student_id = s.id ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT ac.*, s.real_name AS student_name, s.eeid AS student_eeid,
              t.real_name AS teacher_name
       FROM t_gd_achievement ac
       LEFT JOIN t_user s ON ac.student_id = s.id
       LEFT JOIN t_user t ON ac.teacher_id = t.id
       ${where} ORDER BY ac.update_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT ac.*, s.real_name AS student_name, s.college_id AS student_college_id,
              t.real_name AS teacher_name
       FROM t_gd_achievement ac
       LEFT JOIN t_user s ON ac.student_id = s.id
       LEFT JOIN t_user t ON ac.teacher_id = t.id
       WHERE ac.id = ? AND ac.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async create(a) {
    const [result] = await pool.query(
      `INSERT INTO t_gd_achievement
        (student_id, topic_id, teacher_id, title, link, file_url, doc_type, version, status, submit_time)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NOW())`,
      [a.student_id, a.topic_id || null, a.teacher_id || null, a.title,
       a.link || null, a.file_url || null, a.doc_type || 'other', a.version || 1]
    );
    return result.insertId;
  },

  async update(id, { title, link, file_url, doc_type }) {
    const fields = [];
    const params = [];
    if (title !== undefined)    { fields.push('title = ?');    params.push(title); }
    if (link !== undefined)     { fields.push('link = ?');     params.push(link); }
    if (file_url !== undefined) { fields.push('file_url = ?'); params.push(file_url); }
    if (doc_type !== undefined) { fields.push('doc_type = ?'); params.push(doc_type); }
    if (!fields.length) return 0;
    // 重新提交后回到待审阅
    fields.push("status = 0", "submit_time = NOW()", "reject_reason = NULL");
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_gd_achievement SET ${fields.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async review(id, { status, reject_reason }) {
    const [result] = await pool.query(
      `UPDATE t_gd_achievement SET status = ?, reject_reason = ?, review_time = NOW()
       WHERE id = ? AND is_deleted = 0`,
      [status, reject_reason || null, id]
    );
    return result.affectedRows;
  },

  // 同一学生同一文档类型的下一个版本号（开题/中期/初稿/定稿各自独立计数）
  async nextVersion(studentId, docType) {
    const [[r]] = await pool.query(
      `SELECT MAX(version) AS mx FROM t_gd_achievement WHERE student_id = ? AND doc_type = ? AND is_deleted = 0`,
      [studentId, docType || 'other']
    );
    return (r && r.mx ? Number(r.mx) : 0) + 1;
  },

  // 某学生某文档类型的版本历史（按版本倒序）
  async listVersions(studentId, docType) {
    const [rows] = await pool.query(
      `SELECT ac.*, t.real_name AS teacher_name
       FROM t_gd_achievement ac LEFT JOIN t_user t ON ac.teacher_id = t.id
       WHERE ac.student_id = ? AND ac.doc_type = ? AND ac.is_deleted = 0
       ORDER BY ac.version DESC, ac.id DESC`,
      [studentId, docType || 'other']
    );
    return rows;
  },

  // 教师批注（不改变通过/驳回状态,用于过程指导留痕）
  async annotate(id, comment) {
    const [result] = await pool.query(
      `UPDATE t_gd_achievement SET review_comment = ?, review_time = NOW() WHERE id = ? AND is_deleted = 0`,
      [comment || null, id]
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query('UPDATE t_gd_achievement SET is_deleted = 1 WHERE id = ?', [id]);
    return result.affectedRows;
  }
};

module.exports = gdAchievementModel;
