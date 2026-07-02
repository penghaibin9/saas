const pool = require('../config/db');

const USER_FIELDS = `
  id, username, real_name, phone, email, role, college_id, enterprise_id,
  major_id, class_id, eeid, last_login_time, status, must_change_password,
  skill_tags, emergency_name, emergency_phone, emergency_relation, create_time, update_time
`;

const userModel = {
  async findByUsername(username) {
    const [rows] = await pool.query(
      `SELECT * FROM t_user WHERE username = ? AND is_deleted = 0 LIMIT 1`,
      [username]
    );
    return rows[0] || null;
  },

  /** CAS 返回的工号/用户名，优先 username 再学号 eeid */
  async findByCasIdentity(identity) {
    if (!identity) return null;
    const [rows] = await pool.query(
      `SELECT * FROM t_user WHERE (username = ? OR eeid = ?) AND is_deleted = 0 LIMIT 1`,
      [identity, identity]
    );
    return rows[0] || null;
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT ${USER_FIELDS} FROM t_user WHERE id = ? AND is_deleted = 0 LIMIT 1`,
      [id]
    );
    return rows[0] || null;
  },

  async create(user) {
    const [result] = await pool.query(
      `INSERT INTO t_user
        (username, password, real_name, phone, email, role, college_id, enterprise_id, major_id, class_id, eeid, status, must_change_password)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        user.username,
        user.password,
        user.real_name,
        user.phone || null,
        user.email || null,
        user.role,
        user.college_id || null,
        user.enterprise_id || null,
        user.major_id || null,
        user.class_id || null,
        user.eeid || null,
        user.status ?? 1,
        user.must_change_password ? 1 : 0
      ]
    );
    return result.insertId;
  },

  // 按所属企业查企业导师账号（用于入驻审核时激活/停用账号）
  async findByEnterpriseId(enterpriseId) {
    const [rows] = await pool.query(
      `SELECT ${USER_FIELDS} FROM t_user WHERE enterprise_id = ? AND role = 5 AND is_deleted = 0 LIMIT 1`,
      [enterpriseId]
    );
    return rows[0] || null;
  },

  async setOpenid(id, openid) {
    await pool.query('UPDATE t_user SET wx_openid = ? WHERE id = ? AND is_deleted = 0', [openid, id]);
  },

  async updateLastLoginTime(id) {
    await pool.query(
      `UPDATE t_user SET last_login_time = NOW() WHERE id = ?`,
      [id]
    );
  },

  async updatePassword(id, password, { mustChange = 0 } = {}) {
    await pool.query(
      `UPDATE t_user SET password = ?, must_change_password = ?, update_time = NOW() WHERE id = ? AND is_deleted = 0`,
      [password, mustChange ? 1 : 0, id]
    );
  },

  async findAll({ role, collegeId, classId, status, keyword } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE is_deleted = 0';
    const params = [];
    if (role !== undefined)      { where += ' AND role = ?';       params.push(role); }
    if (collegeId !== undefined) { where += ' AND college_id = ?'; params.push(collegeId); }
    if (classId !== undefined)   { where += ' AND class_id = ?';   params.push(classId); }
    if (status !== undefined)    { where += ' AND status = ?';     params.push(status); }
    if (keyword) {
      where += ' AND (username LIKE ? OR real_name LIKE ? OR eeid LIKE ?)';
      params.push(`%${keyword}%`, `%${keyword}%`, `%${keyword}%`);
    }
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_user ${where}`, params
    );
    const [rows] = await pool.query(
      `SELECT ${USER_FIELDS} FROM t_user ${where} ORDER BY create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async updateInfo(id, fields) {
    const allowed = ['real_name','phone','email','role','college_id','major_id','class_id','eeid','status','skill_tags','emergency_name','emergency_phone','emergency_relation'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_user SET ${setClauses.join(', ')}, update_time = NOW() WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_user SET is_deleted = 1 WHERE id = ?',
      [id]
    );
    return result.affectedRows;
  }
};

module.exports = userModel;
