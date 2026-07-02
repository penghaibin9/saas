const pool = require('../config/db');

/**
 * 实习报酬台账模型
 * 合规依据：教育部《职业学校学生实习管理规定》——实习报酬原则上不低于相同岗位
 * 试用期工资的 80%，且应有发放记录。base_salary_ref 记录参考工资，便于自动校验。
 * status：0待发放 1已发放 2异常
 */
const stipendModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_stipend (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        assignment_id INT NULL,
        enterprise_name VARCHAR(200) NULL,
        period VARCHAR(7) NOT NULL COMMENT '发放周期 YYYY-MM',
        amount DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '实发金额',
        base_salary_ref DECIMAL(10,2) NULL COMMENT '相同岗位试用期工资参考',
        method VARCHAR(20) NULL COMMENT '发放方式：bank/cash/wechat/alipay',
        pay_date DATE NULL,
        status TINYINT DEFAULT 0 COMMENT '0待发放,1已发放,2异常',
        proof_url VARCHAR(255) NULL COMMENT '发放凭证',
        remark VARCHAR(255) NULL,
        created_by INT NULL,
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_student (student_id),
        KEY idx_period (period),
        KEY idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实习报酬台账'
    `);
  },

  async findAll(filter = {}, { page = 1, pageSize = 20 } = {}) {
    let where = ' WHERE s.is_deleted = 0';
    const params = [];
    if (filter.studentId !== undefined) { where += ' AND s.student_id = ?'; params.push(filter.studentId); }
    if (filter.period) { where += ' AND s.period = ?'; params.push(filter.period); }
    if (filter.status !== undefined) { where += ' AND s.status = ?'; params.push(filter.status); }
    if (filter.collegeId) { where += ' AND u.college_id = ?'; params.push(filter.collegeId); }
    if (filter.keyword) {
      where += ' AND (u.real_name LIKE ? OR u.eeid LIKE ? OR s.enterprise_name LIKE ?)';
      const kw = `%${filter.keyword}%`;
      params.push(kw, kw, kw);
    }
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_stipend s JOIN t_user u ON s.student_id = u.id ${where}`, params
    );
    const offset = (page - 1) * pageSize;
    const [rows] = await pool.query(
      `SELECT s.*, u.real_name AS student_name, u.eeid AS student_eeid, u.college_id
       FROM t_stipend s JOIN t_user u ON s.student_id = u.id
       ${where} ORDER BY s.period DESC, s.update_time DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    for (const r of rows) r.compliant = module.exports.compliant(r.amount, r.base_salary_ref);
    return { list: rows, total, page, pageSize };
  },

  async findById(id) {
    const [rows] = await pool.query(
      `SELECT s.*, u.real_name AS student_name, u.college_id
       FROM t_stipend s JOIN t_user u ON s.student_id = u.id
       WHERE s.id = ? AND s.is_deleted = 0 LIMIT 1`, [id]
    );
    return rows[0] || null;
  },

  async create(d) {
    const [r] = await pool.query(
      `INSERT INTO t_stipend (student_id, assignment_id, enterprise_name, period, amount, base_salary_ref, method, pay_date, status, proof_url, remark, created_by)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [d.student_id, d.assignment_id || null, d.enterprise_name || null, d.period,
       d.amount || 0, d.base_salary_ref || null, d.method || null, d.pay_date || null,
       d.status ?? 0, d.proof_url || null, d.remark || null, d.created_by || null]
    );
    return r.insertId;
  },

  async update(id, fields) {
    const allowed = ['enterprise_name', 'period', 'amount', 'base_salary_ref', 'method', 'pay_date', 'status', 'proof_url', 'remark'];
    const set = [], params = [];
    for (const k of allowed) if (fields[k] !== undefined) { set.push(`${k} = ?`); params.push(fields[k]); }
    if (!set.length) return 0;
    params.push(id);
    const [r] = await pool.query(`UPDATE t_stipend SET ${set.join(', ')} WHERE id = ? AND is_deleted = 0`, params);
    return r.affectedRows;
  },

  async remove(id) {
    const [r] = await pool.query('UPDATE t_stipend SET is_deleted = 1 WHERE id = ?', [id]);
    return r.affectedRows;
  },

  // 统计：发放进度 + 合规率（按学院过滤）
  async stats(filter = {}) {
    let where = ' WHERE s.is_deleted = 0';
    const params = [];
    if (filter.period) { where += ' AND s.period = ?'; params.push(filter.period); }
    if (filter.collegeId) { where += ' AND u.college_id = ?'; params.push(filter.collegeId); }
    const [rows] = await pool.query(
      `SELECT s.amount, s.base_salary_ref, s.status
       FROM t_stipend s JOIN t_user u ON s.student_id = u.id ${where}`, params
    );
    let paid = 0, pending = 0, abnormal = 0, total = 0, checkable = 0, compliantCount = 0;
    for (const r of rows) {
      total++;
      if (r.status === 1) paid++; else if (r.status === 2) abnormal++; else pending++;
      const c = module.exports.compliant(r.amount, r.base_salary_ref);
      if (c !== null) { checkable++; if (c) compliantCount++; }
    }
    return {
      total, paid, pending, abnormal,
      complianceRate: checkable ? Math.round((compliantCount / checkable) * 100) : null,
      checkable, compliantCount,
    };
  },
};

// 静态合规判定（供 controller/导出复用）
module.exports = stipendModel;
module.exports.compliant = function (amount, baseRef) {
  const a = Number(amount), b = Number(baseRef);
  if (!Number.isFinite(b) || b <= 0) return null;
  return a >= b * 0.8;
};
