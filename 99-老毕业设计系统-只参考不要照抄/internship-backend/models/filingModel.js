const pool = require('../config/db');

// 实习备案状态：0待生成 1待提交 2已提交省平台 3已备案 4驳回
const filingModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_filing_record (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        assignment_id INT NULL,
        batch_year VARCHAR(8) NULL,
        enterprise_name VARCHAR(128) NULL,
        position_title VARCHAR(128) NULL,
        start_date DATE NULL,
        end_date DATE NULL,
        status TINYINT DEFAULT 0 COMMENT '0待生成,1待提交,2已提交,3已备案,4驳回',
        province_ref_no VARCHAR(64) NULL COMMENT '省平台回执号',
        export_batch VARCHAR(32) NULL,
        remark VARCHAR(255) NULL,
        submit_time DATETIME NULL,
        filed_time DATETIME NULL,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        is_deleted TINYINT DEFAULT 0,
        KEY idx_student (student_id),
        KEY idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实习备案记录'
    `);
  },

  async findAll(filter = {}, { page = 1, pageSize = 20 } = {}) {
    let where = ' WHERE f.is_deleted = 0';
    const params = [];
    if (filter.status !== undefined) { where += ' AND f.status = ?'; params.push(filter.status); }
    if (filter.batchYear) { where += ' AND f.batch_year = ?'; params.push(filter.batchYear); }
    if (filter.collegeId) { where += ' AND s.college_id = ?'; params.push(filter.collegeId); }
    if (filter.keyword) {
      where += ' AND (s.real_name LIKE ? OR s.eeid LIKE ? OR f.enterprise_name LIKE ?)';
      const kw = `%${filter.keyword}%`;
      params.push(kw, kw, kw);
    }
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_filing_record f
       JOIN t_user s ON f.student_id = s.id ${where}`, params
    );
    const offset = (page - 1) * pageSize;
    const [rows] = await pool.query(
      `SELECT f.*, s.real_name AS student_name, s.eeid AS student_eeid, s.college_id
       FROM t_filing_record f
       JOIN t_user s ON f.student_id = s.id
       ${where} ORDER BY f.update_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { list: rows, total, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT f.*, s.real_name AS student_name, s.eeid AS student_eeid, s.phone AS student_phone,
              s.college_id, c.name AS college_name
       FROM t_filing_record f
       JOIN t_user s ON f.student_id = s.id
       LEFT JOIN t_college c ON s.college_id = c.id
       WHERE f.id = ? AND f.is_deleted = 0`, [id]
    );
    return rows[0] || null;
  },

  async createFromAssignment(assignment, batchYear) {
    const [r] = await pool.query(
      `INSERT INTO t_filing_record
       (student_id, assignment_id, batch_year, enterprise_name, position_title, start_date, end_date, status)
       VALUES (?, ?, ?, ?, ?, ?, ?, 1)`,
      [
        assignment.student_id, assignment.id, batchYear || null,
        assignment.enterprise_name || null, assignment.position_title || null,
        assignment.start_date || null, assignment.end_date || null
      ]
    );
    return r.insertId;
  },

  async updateStatus(id, status, extra = {}) {
    const sets = ['status = ?'];
    const params = [status];
    if (extra.province_ref_no !== undefined) { sets.push('province_ref_no = ?'); params.push(extra.province_ref_no); }
    if (extra.remark !== undefined) { sets.push('remark = ?'); params.push(extra.remark); }
    if (extra.export_batch !== undefined) { sets.push('export_batch = ?'); params.push(extra.export_batch); }
    if (status === 2) { sets.push('submit_time = NOW()'); }
    if (status === 3) { sets.push('filed_time = NOW()'); }
    params.push(id);
    const [r] = await pool.query(`UPDATE t_filing_record SET ${sets.join(', ')} WHERE id = ? AND is_deleted = 0`, params);
    return r.affectedRows;
  },

  async overview(collegeId) {
    const scope = collegeId ? ' AND s.college_id = ?' : '';
    const params = collegeId ? [collegeId] : [];
    const [rows] = await pool.query(
      `SELECT f.status, COUNT(*) AS cnt FROM t_filing_record f
       JOIN t_user s ON f.student_id = s.id
       WHERE f.is_deleted = 0${scope} GROUP BY f.status`, params
    );
    const map = { pending: 0, submitted: 0, filed: 0, rejected: 0, total: 0 };
    rows.forEach(r => {
      map.total += r.cnt;
      if (r.status === 0 || r.status === 1) map.pending += r.cnt;
      else if (r.status === 2) map.submitted += r.cnt;
      else if (r.status === 3) map.filed += r.cnt;
      else if (r.status === 4) map.rejected += r.cnt;
    });
    return map;
  }
};

module.exports = filingModel;
