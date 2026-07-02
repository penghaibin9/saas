const pool = require('../config/db');

/**
 * 配置化流程引擎数据层（状态机，每租户库独立）
 * ───────────────────────────────────────────────────────────
 * 把"审批/阶段流转"从代码 if-else 改为配置驱动：每校一份定义，可后台改而不改代码。
 *   t_workflow_def        流程定义（biz_type 唯一，如 intern_apply/report/leave）
 *   t_workflow_state      状态节点（含起始/终止标记）
 *   t_workflow_transition 流转：from→to + 动作 + 允许角色
 *   t_workflow_instance   运行实例（某业务单据当前所处状态）
 *   t_workflow_history    流转历史（审计）
 */

// 默认流程（开通学校/初始化时种入；学校可在后台改）
const DEFAULTS = {
  intern_apply: {
    name: '实习申请审批',
    states: [
      { code: 'draft', name: '草稿', is_start: 1, is_end: 0 },
      { code: 'submitted', name: '待教师审核', is_start: 0, is_end: 0 },
      { code: 'teacher_ok', name: '待院校审批', is_start: 0, is_end: 0 },
      { code: 'approved', name: '已通过', is_start: 0, is_end: 1 },
      { code: 'rejected', name: '已驳回', is_start: 0, is_end: 1 },
    ],
    transitions: [
      { from_state: 'draft', to_state: 'submitted', action: 'submit', name: '提交', roles: '4' },
      { from_state: 'submitted', to_state: 'teacher_ok', action: 'approve', name: '教师通过', roles: '3' },
      { from_state: 'submitted', to_state: 'rejected', action: 'reject', name: '教师驳回', roles: '3' },
      { from_state: 'teacher_ok', to_state: 'approved', action: 'approve', name: '院校通过', roles: '1,2' },
      { from_state: 'teacher_ok', to_state: 'rejected', action: 'reject', name: '院校驳回', roles: '1,2' },
      { from_state: 'rejected', to_state: 'draft', action: 'return', name: '退回修改', roles: '1,2,3' },
    ],
  },
  report: {
    name: '实习报告审批',
    states: [
      { code: 'draft', name: '草稿', is_start: 1, is_end: 0 },
      { code: 'submitted', name: '待批阅', is_start: 0, is_end: 0 },
      { code: 'approved', name: '已通过', is_start: 0, is_end: 1 },
      { code: 'rejected', name: '已驳回', is_start: 0, is_end: 1 },
    ],
    transitions: [
      { from_state: 'draft', to_state: 'submitted', action: 'submit', name: '提交', roles: '4' },
      { from_state: 'submitted', to_state: 'approved', action: 'approve', name: '通过', roles: '3' },
      { from_state: 'submitted', to_state: 'rejected', action: 'reject', name: '驳回', roles: '3' },
      { from_state: 'rejected', to_state: 'draft', action: 'return', name: '退回', roles: '3' },
    ],
  },
  leave: {
    name: '请假审批',
    states: [
      { code: 'draft', name: '草稿', is_start: 1, is_end: 0 },
      { code: 'submitted', name: '待审批', is_start: 0, is_end: 0 },
      { code: 'approved', name: '已批准', is_start: 0, is_end: 1 },
      { code: 'rejected', name: '已拒绝', is_start: 0, is_end: 1 },
    ],
    transitions: [
      { from_state: 'draft', to_state: 'submitted', action: 'submit', name: '提交', roles: '4' },
      { from_state: 'submitted', to_state: 'approved', action: 'approve', name: '批准', roles: '3,1,2' },
      { from_state: 'submitted', to_state: 'rejected', action: 'reject', name: '拒绝', roles: '3,1,2' },
    ],
  },
};

const workflowModel = {
  DEFAULTS,

  async ensureTables() {
    await pool.query(`CREATE TABLE IF NOT EXISTS t_workflow_def (
      id INT AUTO_INCREMENT PRIMARY KEY, biz_type VARCHAR(40) NOT NULL UNIQUE,
      name VARCHAR(80) NOT NULL, enabled TINYINT DEFAULT 1, version INT DEFAULT 1,
      update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流程定义'`);
    await pool.query(`CREATE TABLE IF NOT EXISTS t_workflow_state (
      id INT AUTO_INCREMENT PRIMARY KEY, def_id INT NOT NULL, code VARCHAR(40) NOT NULL,
      name VARCHAR(40) NOT NULL, is_start TINYINT DEFAULT 0, is_end TINYINT DEFAULT 0, sort INT DEFAULT 0,
      KEY idx_def (def_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流程状态节点'`);
    await pool.query(`CREATE TABLE IF NOT EXISTS t_workflow_transition (
      id INT AUTO_INCREMENT PRIMARY KEY, def_id INT NOT NULL, from_state VARCHAR(40) NOT NULL,
      to_state VARCHAR(40) NOT NULL, action VARCHAR(40) NOT NULL, name VARCHAR(40),
      roles VARCHAR(40) NULL COMMENT '允许角色(逗号分隔)', perm_code VARCHAR(50) NULL,
      KEY idx_def (def_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流程流转'`);
    await pool.query(`CREATE TABLE IF NOT EXISTS t_workflow_instance (
      id INT AUTO_INCREMENT PRIMARY KEY, biz_type VARCHAR(40) NOT NULL, biz_id INT NOT NULL,
      def_id INT NOT NULL, cur_state VARCHAR(40) NOT NULL,
      create_time DATETIME DEFAULT CURRENT_TIMESTAMP, update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uk_biz (biz_type, biz_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流程实例'`);
    await pool.query(`CREATE TABLE IF NOT EXISTS t_workflow_history (
      id INT AUTO_INCREMENT PRIMARY KEY, instance_id INT NOT NULL, from_state VARCHAR(40),
      to_state VARCHAR(40), action VARCHAR(40), operator INT NULL, operator_name VARCHAR(64) NULL,
      remark VARCHAR(255) NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, KEY idx_inst (instance_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流程流转历史'`);
    await workflowModel.seedDefaults();
  },

  // 种入默认流程（仅当对应 biz_type 不存在时）
  async seedDefaults() {
    for (const [biz, def] of Object.entries(DEFAULTS)) {
      const [exist] = await pool.query('SELECT id FROM t_workflow_def WHERE biz_type = ? LIMIT 1', [biz]);
      if (exist.length) continue;
      await workflowModel.replaceDefinition(biz, def);
    }
  },

  // 覆盖式设置流程定义（学校配置化的核心：替换状态+流转）
  async replaceDefinition(bizType, def) {
    let [rows] = await pool.query('SELECT id FROM t_workflow_def WHERE biz_type = ? LIMIT 1', [bizType]);
    let defId;
    if (rows.length) {
      defId = rows[0].id;
      await pool.query('UPDATE t_workflow_def SET name = ?, version = version + 1 WHERE id = ?', [def.name || bizType, defId]);
      await pool.query('DELETE FROM t_workflow_state WHERE def_id = ?', [defId]);
      await pool.query('DELETE FROM t_workflow_transition WHERE def_id = ?', [defId]);
    } else {
      const [r] = await pool.query('INSERT INTO t_workflow_def (biz_type, name) VALUES (?, ?)', [bizType, def.name || bizType]);
      defId = r.insertId;
    }
    let sort = 0;
    for (const s of def.states || []) {
      await pool.query('INSERT INTO t_workflow_state (def_id, code, name, is_start, is_end, sort) VALUES (?,?,?,?,?,?)',
        [defId, s.code, s.name, s.is_start ? 1 : 0, s.is_end ? 1 : 0, sort++]);
    }
    for (const t of def.transitions || []) {
      await pool.query('INSERT INTO t_workflow_transition (def_id, from_state, to_state, action, name, roles, perm_code) VALUES (?,?,?,?,?,?,?)',
        [defId, t.from_state, t.to_state, t.action, t.name || t.action, t.roles || null, t.perm_code || null]);
    }
    return defId;
  },

  async getDef(bizType) {
    const [defs] = await pool.query('SELECT * FROM t_workflow_def WHERE biz_type = ? AND enabled = 1 LIMIT 1', [bizType]);
    if (!defs.length) return null;
    const def = defs[0];
    const [states] = await pool.query('SELECT code, name, is_start, is_end, sort FROM t_workflow_state WHERE def_id = ? ORDER BY sort', [def.id]);
    const [transitions] = await pool.query('SELECT from_state, to_state, action, name, roles, perm_code FROM t_workflow_transition WHERE def_id = ?', [def.id]);
    return { ...def, states, transitions };
  },

  async listDefs() {
    const [rows] = await pool.query('SELECT id, biz_type, name, enabled, version FROM t_workflow_def ORDER BY id');
    return rows;
  },
  async setEnabled(bizType, enabled) {
    await pool.query('UPDATE t_workflow_def SET enabled = ? WHERE biz_type = ?', [enabled ? 1 : 0, bizType]);
  },

  async getInstance(bizType, bizId) {
    const [rows] = await pool.query('SELECT * FROM t_workflow_instance WHERE biz_type = ? AND biz_id = ? LIMIT 1', [bizType, Number(bizId)]);
    return rows[0] || null;
  },
  async createInstance(bizType, bizId, defId, startState) {
    const [r] = await pool.query(
      'INSERT INTO t_workflow_instance (biz_type, biz_id, def_id, cur_state) VALUES (?,?,?,?)',
      [bizType, Number(bizId), defId, startState]
    );
    return r.insertId;
  },
  async moveTo(instanceId, toState) {
    await pool.query('UPDATE t_workflow_instance SET cur_state = ? WHERE id = ?', [toState, instanceId]);
  },
  async addHistory(instanceId, h) {
    await pool.query(
      'INSERT INTO t_workflow_history (instance_id, from_state, to_state, action, operator, operator_name, remark) VALUES (?,?,?,?,?,?,?)',
      [instanceId, h.from_state, h.to_state, h.action, h.operator || null, h.operator_name || null, h.remark || null]
    );
  },
  async history(instanceId) {
    const [rows] = await pool.query('SELECT from_state, to_state, action, operator_name, remark, created_at FROM t_workflow_history WHERE instance_id = ? ORDER BY id', [instanceId]);
    return rows;
  },
};

// ── 纯函数（引擎核心，可单测，无 IO）──
// 找出 from_state 下匹配 action 的流转
function resolveTransition(transitions, fromState, action) {
  return (transitions || []).find((t) => t.from_state === fromState && t.action === action) || null;
}
// 用户角色是否被该流转允许（roles 逗号分隔角色号；空=不限）
function canPerform(transition, userRole) {
  if (!transition) return false;
  if (!transition.roles) return true;
  return String(transition.roles).split(',').map((s) => s.trim()).includes(String(userRole));
}
// 某状态下，给定用户可执行的动作列表
function availableActions(transitions, fromState, userRole) {
  return (transitions || [])
    .filter((t) => t.from_state === fromState && canPerform(t, userRole))
    .map((t) => ({ action: t.action, name: t.name, to_state: t.to_state }));
}

module.exports = workflowModel;
module.exports.resolveTransition = resolveTransition;
module.exports.canPerform = canPerform;
module.exports.availableActions = availableActions;
