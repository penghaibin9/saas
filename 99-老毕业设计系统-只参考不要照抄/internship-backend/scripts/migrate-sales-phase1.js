/**
 * 真卖路线 Phase1 迁移：换岗/终止 + CAS 扩展配置
 * 运行：node scripts/migrate-sales-phase1.js
 */
require('dotenv').config();
const assignmentChangeModel = require('../models/assignmentChangeModel');
const systemConfigModel = require('../models/systemConfigModel');
const workflowConfigModel = require('../models/workflowConfigModel');

async function addConfig(key, value, desc) {
  await systemConfigModel.ensureTable();
  const pool = require('../config/db');
  await pool.query(
    'INSERT IGNORE INTO t_system_config (config_key, config_value, description) VALUES (?, ?, ?)',
    [key, value, desc]
  );
}

async function main() {
  await assignmentChangeModel.ensureTable();
  console.log('✅ t_assignment_change');
  await addConfig('cas_server_url', '', 'CAS 服务根地址，如 https://sso.school.edu.cn/cas');
  await addConfig('cas_validate_url', '', 'CAS 校验地址，默认可填 .../serviceValidate');
  await addConfig('app_public_url', '', '系统对外访问根 URL（HTTPS），用于 CAS 回调');
  await workflowConfigModel.ensureTable();
  console.log('✅ 流程配置步骤已扩展');
  console.log('✅ 系统配置项已扩展');
  console.log('真卖 Phase1 迁移完成');
  process.exit(0);
}

main().catch(e => { console.error(e); process.exit(1); });
