/**
 * 商业化第二波：系统配置、审批流程配置、实习备案、对接集成
 * 运行：node scripts/migrate-commercial-wave2.js
 */
const systemConfigModel = require('../models/systemConfigModel');
const workflowConfigModel = require('../models/workflowConfigModel');
const filingModel = require('../models/filingModel');

async function main() {
  await systemConfigModel.ensureTable();
  console.log('✅ t_system_config');
  await workflowConfigModel.ensureTable();
  console.log('✅ t_workflow_config');
  await filingModel.ensureTable();
  console.log('✅ t_filing_record');
  console.log('商业化第二波迁移完成');
  process.exit(0);
}

main().catch(e => { console.error(e); process.exit(1); });
