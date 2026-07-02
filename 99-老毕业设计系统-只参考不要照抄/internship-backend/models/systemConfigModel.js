const pool = require('../config/db');

const DEFAULTS = {
  school_name: '湖南石化职业技术学院',
  batch_year: '2026',
  notify_wx_enabled: '1',
  notify_sms_enabled: '0',
  province_api_mode: 'mock',
  cas_enabled: '0',
  cas_login_url: '',
  webhook_url: '',
  sla_phone: '',
  sla_email: '',
  checkin_double_slot: '0',   // 1=启用上班/下班双时段打卡
  checkin_fence_mode: 'hard', // hard=超范围拒绝；soft=允许但标记待审
  module_intern_enabled: '1', // 岗位实习子系统授权开关（1启用,0关闭）
  module_gd_enabled: '1'      // 毕业设计子系统授权开关（1启用,0关闭）
};

const systemConfigModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_system_config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        config_key VARCHAR(64) NOT NULL UNIQUE,
        config_value TEXT NULL,
        description VARCHAR(255) NULL,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统/学校配置（单校部署，可扩展租户）'
    `);
    for (const [k, v] of Object.entries(DEFAULTS)) {
      await pool.query(
        'INSERT IGNORE INTO t_system_config (config_key, config_value, description) VALUES (?, ?, ?)',
        [k, v, k]
      );
    }
  },

  async getAll() {
    const [rows] = await pool.query('SELECT config_key, config_value, description FROM t_system_config ORDER BY id');
    const map = { ...DEFAULTS };
    rows.forEach(r => { map[r.config_key] = r.config_value ?? ''; });
    return map;
  },

  async get(key) {
    const [rows] = await pool.query('SELECT config_value FROM t_system_config WHERE config_key = ?', [key]);
    if (rows.length) return rows[0].config_value;
    return DEFAULTS[key] ?? null;
  },

  async setMany(pairs) {
    for (const [key, value] of Object.entries(pairs)) {
      await pool.query(
        `INSERT INTO t_system_config (config_key, config_value) VALUES (?, ?)
         ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)`,
        [key, value == null ? '' : String(value)]
      );
    }
  }
};

module.exports = systemConfigModel;
