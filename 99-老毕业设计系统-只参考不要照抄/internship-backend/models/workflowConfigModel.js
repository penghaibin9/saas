const pool = require('../config/db');

const DEFAULT_STEPS = [
  { module_key: 'application', step_no: 1, step_name: '学生提交', role_id: 4, action: 'submit', description: '学生选择岗位并提交申请' },
  { module_key: 'application', step_no: 2, step_name: '指导教师审核', role_id: 3, action: 'teacher_review', description: '教师同意/拒绝' },
  { module_key: 'application', step_no: 3, step_name: '院校审核', role_id: 1, action: 'admin_review', description: '院校/分院管理员终审' },
  { module_key: 'application', step_no: 4, step_name: '企业确认录用', role_id: 5, action: 'enterprise_confirm', description: '企业导师确认录用或不录用' },
  { module_key: 'leave', step_no: 1, step_name: '学生申请', role_id: 4, action: 'submit', description: '填写请假时间与事由' },
  { module_key: 'leave', step_no: 2, step_name: '指导教师审批', role_id: 3, action: 'teacher_approve', description: '教师通过/驳回' },
  { module_key: 'intern_plan', step_no: 1, step_name: '教师申报', role_id: 3, action: 'submit', description: '提交实习计划' },
  { module_key: 'intern_plan', step_no: 2, step_name: '管理员审批', role_id: 1, action: 'admin_approve', description: '院校/分院审批计划' },
  { module_key: 'position', step_no: 1, step_name: '企业发布', role_id: 5, action: 'submit', description: '企业提交岗位' },
  { module_key: 'position', step_no: 2, step_name: '学校审核上架', role_id: 1, action: 'admin_audit', description: '管理员审核后上架' },
  { module_key: 'assignment_change', step_no: 1, step_name: '发起申请', role_id: 4, action: 'submit', description: '学生或教师发起换岗/终止' },
  { module_key: 'assignment_change', step_no: 2, step_name: '指导教师审批', role_id: 3, action: 'teacher_review', description: '教师同意/驳回' },
  { module_key: 'assignment_change', step_no: 3, step_name: '管理员终审', role_id: 1, action: 'admin_review', description: '管理员执行变更' },
  { module_key: 'complaint', step_no: 1, step_name: '上报', role_id: 4, action: 'submit', description: '学生/教师提交投诉或异常' },
  { module_key: 'complaint', step_no: 2, step_name: '学校处理', role_id: 1, action: 'handle', description: '管理员/教师处理' },
  { module_key: 'enterprise', step_no: 1, step_name: '企业注册', role_id: 5, action: 'register', description: '企业自助入驻' },
  { module_key: 'enterprise', step_no: 2, step_name: '学校审核', role_id: 1, action: 'audit', description: '审核通过后激活账号' },
  { module_key: 'filing', step_no: 1, step_name: '生成备案包', role_id: 1, action: 'generate', description: '从在册实习生成' },
  { module_key: 'filing', step_no: 2, step_name: '提交备案', role_id: 1, action: 'submit', description: '提交省平台（mock/live）' },
  { module_key: 'filing', step_no: 3, step_name: '确认备案', role_id: 1, action: 'filed', description: '确认省平台已备案' }
];

const MODULE_LABEL = {
  application: '实习申请',
  leave: '请假',
  intern_plan: '实习计划',
  position: '岗位发布',
  assignment_change: '换岗/终止',
  complaint: '投诉与安全',
  enterprise: '企业入驻',
  filing: '实习备案'
};

const workflowConfigModel = {
  async ensureTable() {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_workflow_config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        module_key VARCHAR(32) NOT NULL,
        step_no INT NOT NULL,
        step_name VARCHAR(64) NOT NULL,
        role_id TINYINT NOT NULL COMMENT '处理角色',
        action VARCHAR(64) NULL,
        description VARCHAR(255) NULL,
        is_enabled TINYINT DEFAULT 1,
        UNIQUE KEY uk_module_step (module_key, step_no)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审批流程配置（可配置展示，业务按步骤键匹配）'
    `);
    for (const s of DEFAULT_STEPS) {
      await pool.query(
        `INSERT IGNORE INTO t_workflow_config (module_key, step_no, step_name, role_id, action, description)
         VALUES (?, ?, ?, ?, ?, ?)`,
        [s.module_key, s.step_no, s.step_name, s.role_id, s.action, s.description]
      );
    }
  },

  async listByModule(moduleKey) {
    const [rows] = await pool.query(
      'SELECT * FROM t_workflow_config WHERE module_key = ? AND is_enabled = 1 ORDER BY step_no',
      [moduleKey]
    );
    return rows;
  },

  async listAll() {
    const [rows] = await pool.query('SELECT * FROM t_workflow_config ORDER BY module_key, step_no');
    return rows;
  },

  async updateStep(id, fields) {
    const allowed = ['step_name', 'role_id', 'description', 'is_enabled'];
    const sets = [];
    const params = [];
    for (const k of allowed) {
      if (fields[k] !== undefined) { sets.push(`${k} = ?`); params.push(fields[k]); }
    }
    if (!sets.length) return 0;
    params.push(id);
    const [r] = await pool.query(`UPDATE t_workflow_config SET ${sets.join(', ')} WHERE id = ?`, params);
    return r.affectedRows;
  },

  moduleLabel(key) { return MODULE_LABEL[key] || key; }
};

module.exports = workflowConfigModel;
