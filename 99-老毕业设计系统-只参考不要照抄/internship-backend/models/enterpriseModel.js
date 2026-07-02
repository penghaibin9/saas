const pool = require('../config/db');

const enterpriseModel = {
  async findAll({ status, auditStatus, coopStatus, keyword } = {}, { page = 1, pageSize = 20 } = {}) {
    const offset = (page - 1) * pageSize;
    let where = 'WHERE is_deleted = 0';
    const params = [];
    if (status !== undefined) { where += ' AND status = ?'; params.push(status); }
    if (auditStatus !== undefined) { where += ' AND audit_status = ?'; params.push(auditStatus); }
    if (coopStatus !== undefined) { where += ' AND coop_status = ?'; params.push(coopStatus); }
    if (keyword) {
      where += ' AND (name LIKE ? OR short_name LIKE ? OR credit_code LIKE ?)';
      params.push(`%${keyword}%`, `%${keyword}%`, `%${keyword}%`);
    }

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_enterprise ${where}`,
      params
    );
    const [rows] = await pool.query(
      `SELECT * FROM t_enterprise ${where} ORDER BY create_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      'SELECT * FROM t_enterprise WHERE id = ? AND is_deleted = 0',
      [id]
    );
    return rows[0] || null;
  },

  async create({ name, short_name, industry, address, contact_name, contact_phone, contact_email, description, longitude, latitude, checkin_radius, audit_status, credit_code, nature, scale, legal_person, reg_capital, website, license_url, coop_status }) {
    const [result] = await pool.query(
      `INSERT INTO t_enterprise
        (name, short_name, industry, address, contact_name, contact_phone, contact_email, description, longitude, latitude, checkin_radius, audit_status,
         credit_code, nature, scale, legal_person, reg_capital, website, license_url, coop_status)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [name, short_name || null, industry || null, address || null,
       contact_name || null, contact_phone || null, contact_email || null, description || null,
       longitude ?? null, latitude ?? null, checkin_radius ?? 0, audit_status ?? 1,
       credit_code || null, nature || null, scale || null, legal_person || null,
       reg_capital || null, website || null, license_url || null, coop_status ?? 1]
    );
    return result.insertId;
  },

  // 入驻审核：设置审核状态与意见
  async setAudit(id, audit_status, audit_remark) {
    const [result] = await pool.query(
      `UPDATE t_enterprise SET audit_status = ?, audit_remark = ? WHERE id = ? AND is_deleted = 0`,
      [audit_status, audit_remark || null, id]
    );
    return result.affectedRows;
  },

  async update(id, fields) {
    const allowed = ['name','short_name','industry','address','contact_name','contact_phone','contact_email','description','status','audit_status','longitude','latitude','checkin_radius','credit_code','nature','scale','legal_person','reg_capital','website','license_url','coop_status'];
    const setClauses = [];
    const params = [];
    for (const key of allowed) {
      if (fields[key] !== undefined) { setClauses.push(`${key} = ?`); params.push(fields[key]); }
    }
    if (!setClauses.length) return 0;
    params.push(id);
    const [result] = await pool.query(
      `UPDATE t_enterprise SET ${setClauses.join(', ')} WHERE id = ? AND is_deleted = 0`,
      params
    );
    return result.affectedRows;
  },

  async remove(id) {
    const [result] = await pool.query(
      'UPDATE t_enterprise SET is_deleted = 1 WHERE id = ?',
      [id]
    );
    return result.affectedRows;
  }
};

module.exports = enterpriseModel;
