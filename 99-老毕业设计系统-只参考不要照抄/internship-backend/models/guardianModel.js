const pool = require('../config/db');
const crypto = require('crypto');

/**
 * 家长在线签署模型（监护人知情同意电子签）
 * 与 benchmark 的"家长知情书文件上传"互补：此处由学校发起、家长凭安全令牌在线确认，
 * 留存签署人、关系、签名、IP、时间等可追溯的电子签记录，更符合中职监护人合规要求。
 * sign_status：0待签 1已签 2拒签 3失效
 */
const guardianModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_guardian_consent (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        token CHAR(48) NOT NULL UNIQUE COMMENT '家长签署安全令牌',
        title VARCHAR(200) NOT NULL,
        content MEDIUMTEXT NOT NULL COMMENT '知情同意书正文快照',
        guardian_name VARCHAR(50) NULL,
        guardian_phone VARCHAR(20) NULL,
        relation VARCHAR(20) NULL COMMENT '与学生关系',
        sign_status TINYINT DEFAULT 0 COMMENT '0待签,1已签,2拒签,3失效',
        sign_name VARCHAR(50) NULL COMMENT '签署姓名',
        sign_ip VARCHAR(64) NULL,
        sign_ua VARCHAR(255) NULL,
        reject_reason VARCHAR(255) NULL,
        signed_at DATETIME NULL,
        expires_at DATETIME NULL,
        created_by INT NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_student (student_id),
        KEY idx_status (sign_status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='家长在线签署'
    `);
  },

  genToken() { return crypto.randomBytes(24).toString('hex'); },

  async create(d) {
    const token = guardianModel.genToken();
    const [r] = await pool.query(
      `INSERT INTO t_guardian_consent (student_id, token, title, content, guardian_name, guardian_phone, relation, expires_at, created_by)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [d.student_id, token, d.title, d.content, d.guardian_name || null, d.guardian_phone || null,
       d.relation || null, d.expires_at || null, d.created_by || null]
    );
    return { id: r.insertId, token };
  },

  async findByToken(token) {
    const [rows] = await pool.query(
      `SELECT g.*, u.real_name AS student_name, u.eeid AS student_eeid
       FROM t_guardian_consent g JOIN t_user u ON g.student_id = u.id
       WHERE g.token = ? AND g.is_deleted = 0 LIMIT 1`, [token]
    );
    return rows[0] || null;
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT g.*, u.real_name AS student_name, u.college_id, u.eeid AS student_eeid
       FROM t_guardian_consent g JOIN t_user u ON g.student_id = u.id
       WHERE g.id = ? AND g.is_deleted = 0 LIMIT 1`, [id]
    );
    return rows[0] || null;
  },

  async findAll(filter = {}, { page = 1, pageSize = 20 } = {}) {
    let where = ' WHERE g.is_deleted = 0';
    const params = [];
    if (filter.studentId !== undefined) { where += ' AND g.student_id = ?'; params.push(filter.studentId); }
    if (filter.status !== undefined) { where += ' AND g.sign_status = ?'; params.push(filter.status); }
    if (filter.collegeId) { where += ' AND u.college_id = ?'; params.push(filter.collegeId); }
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_guardian_consent g JOIN t_user u ON g.student_id = u.id ${where}`, params
    );
    const offset = (page - 1) * pageSize;
    const [rows] = await pool.query(
      `SELECT g.id, g.student_id, g.token, g.title, g.guardian_name, g.relation, g.sign_status,
              g.sign_name, g.signed_at, g.expires_at, g.create_time,
              u.real_name AS student_name, u.eeid AS student_eeid, u.college_id
       FROM t_guardian_consent g JOIN t_user u ON g.student_id = u.id
       ${where} ORDER BY g.create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { list: rows, total, page, pageSize };
  },

  // 家长签署（仅在待签状态允许）
  async sign(token, { sign_name, guardian_name, guardian_phone, relation, ip, ua }) {
    const [r] = await pool.query(
      `UPDATE t_guardian_consent
       SET sign_status = 1, sign_name = ?, guardian_name = COALESCE(?, guardian_name),
           guardian_phone = COALESCE(?, guardian_phone), relation = COALESCE(?, relation),
           sign_ip = ?, sign_ua = ?, signed_at = NOW()
       WHERE token = ? AND sign_status = 0 AND is_deleted = 0`,
      [sign_name, guardian_name || null, guardian_phone || null, relation || null, ip || null, (ua || '').slice(0, 255), token]
    );
    return r.affectedRows;
  },

  async reject(token, { reason, ip, ua }) {
    const [r] = await pool.query(
      `UPDATE t_guardian_consent SET sign_status = 2, reject_reason = ?, sign_ip = ?, sign_ua = ?, signed_at = NOW()
       WHERE token = ? AND sign_status = 0 AND is_deleted = 0`,
      [(reason || '').slice(0, 255), ip || null, (ua || '').slice(0, 255), token]
    );
    return r.affectedRows;
  },

  async remove(id) {
    const [r] = await pool.query('UPDATE t_guardian_consent SET is_deleted = 1 WHERE id = ?', [id]);
    return r.affectedRows;
  },
};

module.exports = guardianModel;
