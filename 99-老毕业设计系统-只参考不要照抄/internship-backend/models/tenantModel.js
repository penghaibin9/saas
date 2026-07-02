const tenancy = require('../config/tenancy');

/**
 * 租户注册表 + SaaS 控制面（master 库）
 * ───────────────────────────────────────────────────────────
 * 记录每所学校 → 独立库的映射，并承载商品化所需的套餐/配额/计费/开通审计。
 * 直接使用 masterPool，不经租户代理（控制面不属于任何租户）。
 */
const M = () => tenancy.masterPool();

async function colExists(table, col) {
  const [rows] = await M().query(
    `SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = ? AND column_name = ? LIMIT 1`,
    [table, col]
  );
  return rows.length > 0;
}

const DEFAULT_PLANS = [
  { code: 'trial',    name: '试用版',  price_year: 0,     max_students: 300,   max_storage_mb: 5120,  ai_monthly_quota: 500 },
  { code: 'standard', name: '标准版',  price_year: 30000, max_students: 2000,  max_storage_mb: 51200, ai_monthly_quota: 5000 },
  { code: 'pro',      name: '专业版',  price_year: 60000, max_students: 8000,  max_storage_mb: 204800, ai_monthly_quota: 20000 },
];

const tenantModel = {
  async ensureTable() {
    await M().query(`
      CREATE TABLE IF NOT EXISTS t_tenant (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(64) NOT NULL COMMENT '租户标识(子域名/登录用)',
        name VARCHAR(128) NOT NULL COMMENT '学校名称',
        db_name VARCHAR(128) NOT NULL COMMENT '该校独立数据库名',
        contact_name VARCHAR(64) DEFAULT NULL,
        contact_phone VARCHAR(32) DEFAULT NULL,
        plan VARCHAR(32) DEFAULT 'standard' COMMENT '套餐编码',
        expire_date DATE DEFAULT NULL COMMENT '服务到期日',
        status TINYINT DEFAULT 1 COMMENT '1启用 0停用',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_code (code)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SaaS 租户注册表'
    `);
    // 幂等增补商品化字段（配额/区域/更新时间）
    const adds = [
      ['max_students', 'INT DEFAULT 2000'],
      ['max_storage_mb', 'INT DEFAULT 51200'],
      ['ai_monthly_quota', 'INT DEFAULT 5000'],
      ['region', 'VARCHAR(40) NULL'],
      ['remark', 'VARCHAR(255) NULL'],
      ['db_host', 'VARCHAR(128) NULL COMMENT \'V2预留:租户分片到不同MySQL实例时的库主机\''],
      ['updated_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'],
    ];
    for (const [c, def] of adds) if (!await colExists('t_tenant', c)) await M().query(`ALTER TABLE t_tenant ADD COLUMN ${c} ${def}`);

    await M().query(`CREATE TABLE IF NOT EXISTS t_plan (
      code VARCHAR(20) PRIMARY KEY, name VARCHAR(40), price_year DECIMAL(10,2) DEFAULT 0,
      max_students INT, max_storage_mb INT, ai_monthly_quota INT, features JSON NULL,
      update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SaaS 套餐定义'`);

    await M().query(`CREATE TABLE IF NOT EXISTS t_tenant_usage (
      tenant_code VARCHAR(64) NOT NULL, period CHAR(7) NOT NULL COMMENT 'YYYY-MM',
      students INT DEFAULT 0, storage_mb INT DEFAULT 0, ai_calls INT DEFAULT 0,
      update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (tenant_code, period)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租户用量计量'`);

    await M().query(`CREATE TABLE IF NOT EXISTS t_tenant_event (
      id INT AUTO_INCREMENT PRIMARY KEY, tenant_code VARCHAR(64) NOT NULL,
      type VARCHAR(20) NOT NULL COMMENT 'provision/renew/suspend/resume/update',
      detail JSON NULL, operator VARCHAR(64) NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP, KEY idx_code (tenant_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租户开通/续费/停服审计'`);

    await tenantModel.seedPlans();
  },

  async seedPlans() {
    for (const p of DEFAULT_PLANS) {
      await M().query(
        `INSERT IGNORE INTO t_plan (code, name, price_year, max_students, max_storage_mb, ai_monthly_quota)
         VALUES (?,?,?,?,?,?)`,
        [p.code, p.name, p.price_year, p.max_students, p.max_storage_mb, p.ai_monthly_quota]
      );
    }
  },

  async listPlans() {
    const [rows] = await M().query('SELECT * FROM t_plan ORDER BY price_year');
    return rows;
  },
  async getPlan(code) {
    const [rows] = await M().query('SELECT * FROM t_plan WHERE code = ? LIMIT 1', [code]);
    return rows[0] || null;
  },

  async list() {
    const [rows] = await M().query(
      `SELECT id, code, name, db_name, contact_name, contact_phone, plan, expire_date, status,
              max_students, max_storage_mb, ai_monthly_quota, region, remark, create_time
       FROM t_tenant WHERE is_deleted = 0 ORDER BY id`
    );
    return rows;
  },

  async findByCode(code) {
    const [rows] = await M().query('SELECT * FROM t_tenant WHERE code = ? AND is_deleted = 0 LIMIT 1', [code]);
    return rows[0] || null;
  },

  async create({ code, name, db_name, contact_name, contact_phone, plan, expire_date, region }) {
    // 套餐带出默认配额
    const p = plan ? await tenantModel.getPlan(plan) : null;
    const [r] = await M().query(
      `INSERT INTO t_tenant (code, name, db_name, contact_name, contact_phone, plan, expire_date, region, max_students, max_storage_mb, ai_monthly_quota)
       VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
      [code, name, db_name, contact_name || null, contact_phone || null, plan || 'standard', expire_date || null, region || null,
       p ? p.max_students : 2000, p ? p.max_storage_mb : 51200, p ? p.ai_monthly_quota : 5000]
    );
    await tenancy.loadTenants();
    return r.insertId;
  },

  // 改套餐：同步带出该套餐的默认配额（也可单独 setQuota 覆盖）
  async setPlan(code, planCode) {
    const p = await tenantModel.getPlan(planCode);
    if (!p) throw new Error('套餐不存在：' + planCode);
    await M().query(
      'UPDATE t_tenant SET plan = ?, max_students = ?, max_storage_mb = ?, ai_monthly_quota = ? WHERE code = ?',
      [planCode, p.max_students, p.max_storage_mb, p.ai_monthly_quota, code]
    );
    await tenancy.loadTenants();
  },

  async setQuota(code, { max_students, max_storage_mb, ai_monthly_quota }) {
    const sets = [], params = [];
    if (max_students !== undefined) { sets.push('max_students = ?'); params.push(max_students); }
    if (max_storage_mb !== undefined) { sets.push('max_storage_mb = ?'); params.push(max_storage_mb); }
    if (ai_monthly_quota !== undefined) { sets.push('ai_monthly_quota = ?'); params.push(ai_monthly_quota); }
    if (!sets.length) return;
    params.push(code);
    await M().query(`UPDATE t_tenant SET ${sets.join(', ')} WHERE code = ?`, params);
    await tenancy.loadTenants();
  },

  async setExpire(code, expire_date) {
    await M().query('UPDATE t_tenant SET expire_date = ? WHERE code = ?', [expire_date || null, code]);
  },

  async setStatus(code, status) {
    await M().query('UPDATE t_tenant SET status = ? WHERE code = ?', [status ? 1 : 0, code]);
    await tenancy.loadTenants();
  },

  async recordEvent(code, type, detail, operator) {
    await M().query(
      'INSERT INTO t_tenant_event (tenant_code, type, detail, operator) VALUES (?,?,?,?)',
      [code, type, detail ? JSON.stringify(detail) : null, operator || null]
    );
  },
  async events(code, limit = 50) {
    const [rows] = await M().query(
      'SELECT type, detail, operator, created_at FROM t_tenant_event WHERE tenant_code = ? ORDER BY id DESC LIMIT ?',
      [code, limit]
    );
    return rows;
  },

  // 用量计量（按月 upsert）
  async upsertUsage(code, period, { students, storage_mb, ai_calls }) {
    await M().query(
      `INSERT INTO t_tenant_usage (tenant_code, period, students, storage_mb, ai_calls)
       VALUES (?,?,?,?,?)
       ON DUPLICATE KEY UPDATE students=VALUES(students), storage_mb=VALUES(storage_mb), ai_calls=VALUES(ai_calls)`,
      [code, period, students || 0, storage_mb || 0, ai_calls || 0]
    );
  },
  async getUsage(code, period) {
    const [rows] = await M().query('SELECT * FROM t_tenant_usage WHERE tenant_code = ? AND period = ? LIMIT 1', [code, period]);
    return rows[0] || null;
  },
};

module.exports = tenantModel;
module.exports.DEFAULT_PLANS = DEFAULT_PLANS;
