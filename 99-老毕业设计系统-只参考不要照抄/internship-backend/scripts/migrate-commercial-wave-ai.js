/**
 * 迁移：商业化增强（AI/合规/触达波次）
 * 非破坏性建表：实习报酬台账 t_stipend、家长在线签署 t_guardian_consent。
 * 幂等（CREATE TABLE IF NOT EXISTS），可反复执行。
 * 运行：node scripts/migrate-commercial-wave-ai.js
 */
require('dotenv').config();
const pool = require('../config/db');
const stipendModel = require('../models/stipendModel');
const guardianModel = require('../models/guardianModel');
const aiUsageModel = require('../models/aiUsageModel');
const checkinModel = require('../models/checkinModel');

async function run() {
  try {
    await stipendModel.ensureTable();
    console.log('✅ t_stipend 就绪（实习报酬台账）');
    await guardianModel.ensureTable();
    console.log('✅ t_guardian_consent 就绪（家长在线签署）');
    await aiUsageModel.ensureTable();
    console.log('✅ t_ai_usage 就绪（AI用量台账）');
    await checkinModel.ensureAntiCheatColumns();
    console.log('✅ t_checkin 反作弊字段就绪（精度/模拟定位/设备/风险）');
    await require('../models/permModel').ensureTables();
    console.log('✅ 自定义角色/权限表就绪（t_perm_role / t_perm_grant / t_user_perm_role）');
    await require('../models/workflowModel').ensureTables();
    console.log('✅ 配置化流程引擎表就绪 + 默认流程（t_workflow_def/state/transition/instance/history）');
    console.log('🎉 商业化增强波次建表完成（未删除任何已有数据）');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
