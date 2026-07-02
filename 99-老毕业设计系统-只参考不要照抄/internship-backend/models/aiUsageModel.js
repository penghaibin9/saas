const pool = require('../config/db');

/**
 * AI 用量台账（成本护栏）
 * 按月累计 AI 调用次数；多租户下经 config/db 代理自动落到各校独立库（各校独立配额）。
 * 配合 AI_MONTHLY_QUOTA 环境变量：超额后 AI 自动降级为演示，避免账单失控。
 */
function curMonth() { return new Date().toISOString().slice(0, 7); } // YYYY-MM

const aiUsageModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_ai_usage (
        period VARCHAR(7) PRIMARY KEY COMMENT '统计月份 YYYY-MM',
        calls INT NOT NULL DEFAULT 0,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI调用用量台账'
    `);
  },

  async monthTotal(period = curMonth()) {
    try {
      const [rows] = await pool.query('SELECT calls FROM t_ai_usage WHERE period = ? LIMIT 1', [period]);
      return rows[0] ? Number(rows[0].calls) : 0;
    } catch (_) { return 0; } // 表未建/异常时不阻断
  },

  async incr(n = 1, period = curMonth()) {
    try {
      await pool.query(
        'INSERT INTO t_ai_usage (period, calls) VALUES (?, ?) ON DUPLICATE KEY UPDATE calls = calls + VALUES(calls)',
        [period, n]
      );
    } catch (_) { /* 计量失败不影响主流程 */ }
  },

  curMonth,
};

module.exports = aiUsageModel;
