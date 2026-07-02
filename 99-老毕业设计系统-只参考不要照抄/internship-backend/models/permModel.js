const pool = require('../config/db');

/**
 * 自定义角色 + 数据权限引擎（增量式，不影响既有 role 1-5 与 requireRole）
 * ───────────────────────────────────────────────────────────
 * · t_perm_role：自定义角色（含数据范围 data_scope：all/college/class/self）
 * · t_perm_grant：角色→权限码（多对多）
 * · t_user_perm_role：用户→自定义角色（多对多）
 * 供 requirePermission 中间件与 dataScope 解析使用；为新接口提供灵活权限，
 * 大机构/监管局可自定义岗位角色与可见数据范围，无需改代码。
 */

// 权限码目录（功能点）。新增功能点往这里加即可在后台勾选授权。
const PERMISSIONS = [
  { code: 'user:view', label: '查看用户' },
  { code: 'user:manage', label: '管理用户' },
  { code: 'intern:view', label: '查看实习' },
  { code: 'intern:manage', label: '管理实习' },
  { code: 'checkin:view', label: '查看打卡' },
  { code: 'report:view', label: '查看报告/报表' },
  { code: 'report:export', label: '导出报表/报送' },
  { code: 'stipend:manage', label: '管理实习报酬' },
  { code: 'risk:view', label: '查看风险/大屏' },
  { code: 'complaint:handle', label: '处理投诉' },
  { code: 'guardian:manage', label: '家长签署管理' },
  { code: 'perm:admin', label: '权限/角色管理' },
];
const SCOPES = ['all', 'college', 'class', 'self'];

const permModel = {
  PERMISSIONS, SCOPES,

  async ensureTables() {
    await pool.query(`CREATE TABLE IF NOT EXISTS t_perm_role (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(50) NOT NULL,
      code VARCHAR(50) NOT NULL UNIQUE,
      data_scope VARCHAR(10) DEFAULT 'self' COMMENT 'all/college/class/self',
      remark VARCHAR(255) NULL,
      status TINYINT DEFAULT 1,
      is_deleted TINYINT DEFAULT 0,
      create_time DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自定义角色'`);
    await pool.query(`CREATE TABLE IF NOT EXISTS t_perm_grant (
      role_id INT NOT NULL, perm_code VARCHAR(50) NOT NULL,
      PRIMARY KEY (role_id, perm_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色权限授予'`);
    await pool.query(`CREATE TABLE IF NOT EXISTS t_user_perm_role (
      user_id INT NOT NULL, role_id INT NOT NULL,
      PRIMARY KEY (user_id, role_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户自定义角色'`);
  },

  async listRoles() {
    const [rows] = await pool.query(
      `SELECT r.*, (SELECT GROUP_CONCAT(perm_code) FROM t_perm_grant g WHERE g.role_id = r.id) AS perms
       FROM t_perm_role r WHERE r.is_deleted = 0 ORDER BY r.id`
    );
    return rows.map((r) => ({ ...r, perms: r.perms ? r.perms.split(',') : [] }));
  },

  async createRole({ name, code, data_scope, remark, perms }) {
    const [r] = await pool.query(
      'INSERT INTO t_perm_role (name, code, data_scope, remark) VALUES (?, ?, ?, ?)',
      [name, code, SCOPES.includes(data_scope) ? data_scope : 'self', remark || null]
    );
    await permModel.setPerms(r.insertId, perms || []);
    return r.insertId;
  },

  async setPerms(roleId, perms) {
    await pool.query('DELETE FROM t_perm_grant WHERE role_id = ?', [roleId]);
    const valid = (perms || []).filter((c) => PERMISSIONS.some((p) => p.code === c));
    if (valid.length) {
      await pool.query(
        'INSERT INTO t_perm_grant (role_id, perm_code) VALUES ?',
        [valid.map((c) => [roleId, c])]
      );
    }
  },

  async removeRole(roleId) {
    await pool.query('UPDATE t_perm_role SET is_deleted = 1 WHERE id = ?', [roleId]);
    await pool.query('DELETE FROM t_user_perm_role WHERE role_id = ?', [roleId]);
  },

  async assignToUser(userId, roleId) {
    await pool.query('INSERT IGNORE INTO t_user_perm_role (user_id, role_id) VALUES (?, ?)', [userId, roleId]);
  },
  async revokeFromUser(userId, roleId) {
    await pool.query('DELETE FROM t_user_perm_role WHERE user_id = ? AND role_id = ?', [userId, roleId]);
  },

  // 取用户的全部权限码 + 最宽数据范围
  async getUserPerms(userId) {
    const [rows] = await pool.query(
      `SELECT DISTINCT g.perm_code, r.data_scope
       FROM t_user_perm_role ur
       JOIN t_perm_role r ON r.id = ur.role_id AND r.is_deleted = 0 AND r.status = 1
       LEFT JOIN t_perm_grant g ON g.role_id = r.id
       WHERE ur.user_id = ?`, [userId]
    );
    const perms = new Set();
    let scope = null;
    for (const row of rows) {
      if (row.perm_code) perms.add(row.perm_code);
      scope = widestScope(scope, row.data_scope);
    }
    return { perms: [...perms], scope: scope || 'self' };
  },
};

// 数据范围宽窄：all > college > class > self
const SCOPE_RANK = { all: 3, college: 2, class: 1, self: 0 };
function widestScope(a, b) {
  if (!a) return b; if (!b) return a;
  return (SCOPE_RANK[a] ?? 0) >= (SCOPE_RANK[b] ?? 0) ? a : b;
}

// 纯函数：判断一组权限码是否覆盖所需权限（供中间件与单测复用）
function hasPermission(userPerms, required) {
  if (!required) return true;
  return Array.isArray(userPerms) && userPerms.includes(required);
}

// 纯函数：把数据范围 + 用户身份解析为查询过滤条件
function scopeToFilter(scope, user) {
  switch (scope) {
    case 'all': return {};
    case 'college': return { collegeId: user.collegeId };
    case 'class': return { classId: user.classId };
    case 'self': default: return { userId: user.id };
  }
}

module.exports = permModel;
module.exports.hasPermission = hasPermission;
module.exports.scopeToFilter = scopeToFilter;
module.exports.widestScope = widestScope;
