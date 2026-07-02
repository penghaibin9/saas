const pool = require('../config/db');

/**
 * 操作审计日志模型（等保/迎检合规核心）。
 * 记录所有写操作的责任链：谁、在哪个IP、几点、对什么对象、做了什么、结果如何。
 * 设计为「只增不改」，前端仅提供查询，任何角色都无法删除/编辑，保证可追溯性。
 */
const auditLogModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_audit_log (
        id           BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id      INT COMMENT '操作人ID(未登录为空)',
        username     VARCHAR(64) COMMENT '操作人账号',
        real_name    VARCHAR(64) COMMENT '操作人姓名',
        role         TINYINT COMMENT '操作人角色',
        college_id   INT COMMENT '操作人所属学院(用于分院隔离查询)',
        ip           VARCHAR(64) COMMENT '客户端IP',
        method       VARCHAR(10) COMMENT 'HTTP方法',
        path         VARCHAR(255) COMMENT '请求路径',
        action       VARCHAR(100) COMMENT '可读操作描述',
        target_type  VARCHAR(50) COMMENT '操作对象类型',
        target_id    VARCHAR(50) COMMENT '操作对象ID',
        status_code  INT COMMENT 'HTTP响应码',
        success      TINYINT DEFAULT 1 COMMENT '是否成功(2xx)',
        detail       TEXT COMMENT '请求摘要(已脱敏)',
        create_time  DATETIME DEFAULT NOW(),
        INDEX idx_user (user_id),
        INDEX idx_college (college_id),
        INDEX idx_action (action),
        INDEX idx_target (target_type, target_id),
        INDEX idx_create_time (create_time)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '操作审计日志表'
    `);
  },

  async create(entry) {
    const {
      user_id = null, username = null, real_name = null, role = null,
      college_id = null, ip = null, method = null, path = null,
      action = null, target_type = null, target_id = null,
      status_code = null, success = 1, detail = null
    } = entry;
    const [result] = await pool.query(
      `INSERT INTO t_audit_log
       (user_id, username, real_name, role, college_id, ip, method, path,
        action, target_type, target_id, status_code, success, detail)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [user_id, username, real_name, role, college_id, ip, method, path,
       action, target_type, target_id, status_code, success, detail]
    );
    return result.insertId;
  },

  /**
   * 条件分页查询。filters 支持：keyword(账号/姓名/动作模糊)、userId、collegeId、
   * action、success、startDate、endDate。collegeId 由控制层按角色注入，实现分院隔离。
   */
  async query(filters = {}, { page = 1, pageSize = 20 } = {}) {
    const where = [];
    const params = [];
    if (filters.keyword) {
      where.push('(username LIKE ? OR real_name LIKE ? OR action LIKE ?)');
      const kw = `%${filters.keyword}%`;
      params.push(kw, kw, kw);
    }
    if (filters.userId) { where.push('user_id = ?'); params.push(filters.userId); }
    if (filters.collegeId) { where.push('college_id = ?'); params.push(filters.collegeId); }
    if (filters.action) { where.push('action LIKE ?'); params.push(`%${filters.action}%`); }
    if (filters.success !== undefined && filters.success !== null && filters.success !== '') {
      where.push('success = ?'); params.push(Number(filters.success));
    }
    if (filters.startDate) { where.push('create_time >= ?'); params.push(filters.startDate); }
    if (filters.endDate) { where.push('create_time <= ?'); params.push(filters.endDate); }

    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';
    const offset = (page - 1) * pageSize;

    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_audit_log ${whereSql}`, params
    );
    const [rows] = await pool.query(
      `SELECT * FROM t_audit_log ${whereSql} ORDER BY id DESC LIMIT ? OFFSET ?`,
      [...params, pageSize, offset]
    );
    return { total, list: rows, page, pageSize };
  },

  /** 概览统计：近 N 天操作量、失败次数、活跃操作人，用于审计页头部卡片。 */
  async overview(days = 7, collegeId = null) {
    const collegeFilter = collegeId ? 'AND college_id = ?' : '';
    const baseParams = collegeId ? [days, collegeId] : [days];
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM t_audit_log
       WHERE create_time >= DATE_SUB(NOW(), INTERVAL ? DAY) ${collegeFilter}`,
      baseParams
    );
    const [[{ failed }]] = await pool.query(
      `SELECT COUNT(*) AS failed FROM t_audit_log
       WHERE success = 0 AND create_time >= DATE_SUB(NOW(), INTERVAL ? DAY) ${collegeFilter}`,
      baseParams
    );
    const [[{ actors }]] = await pool.query(
      `SELECT COUNT(DISTINCT user_id) AS actors FROM t_audit_log
       WHERE create_time >= DATE_SUB(NOW(), INTERVAL ? DAY) ${collegeFilter}`,
      baseParams
    );
    const [topActions] = await pool.query(
      `SELECT action, COUNT(*) AS cnt FROM t_audit_log
       WHERE create_time >= DATE_SUB(NOW(), INTERVAL ? DAY) ${collegeFilter}
       GROUP BY action ORDER BY cnt DESC LIMIT 8`,
      baseParams
    );
    return { days, total, failed, actors, topActions };
  }
};

module.exports = auditLogModel;
