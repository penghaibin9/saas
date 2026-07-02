/**
 * 迁移：操作审计日志表 (t_audit_log)。
 * 等保/迎检合规核心：记录所有写操作的责任链，只增不改不删。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-audit.js
 */
require('dotenv').config();
const auditLogModel = require('../models/auditLogModel');
const pool = require('../config/db');

async function run() {
  try {
    await auditLogModel.ensureTable();
    console.log('✅ t_audit_log 就绪');
    console.log('🎉 审计日志表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
