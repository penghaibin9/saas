/**
 * 迁移：企业端自助门户。
 *  - t_user 增加 enterprise_id（企业导师账号 → 所属企业）
 *  - t_enterprise 增加 audit_status（0待审核,1已通过,2已拒绝）、audit_remark、contact_email
 * 幂等：列存在性判断。运行：node scripts/migrate-enterprise-portal.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function columnExists(table, column) {
  const [rows] = await pool.query(
    `SELECT COUNT(*) AS c FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?`,
    [table, column]
  );
  return rows[0].c > 0;
}

async function addColumn(table, column, ddl) {
  if (await columnExists(table, column)) {
    console.log(`· ${table}.${column} 已存在，跳过`);
  } else {
    await pool.query(`ALTER TABLE ${table} ADD COLUMN ${ddl}`);
    console.log(`✅ ${table}.${column} 已添加`);
  }
}

async function run() {
  try {
    await addColumn('t_user', 'enterprise_id', "enterprise_id INT NULL COMMENT '企业导师所属企业ID' AFTER college_id");
    await addColumn('t_enterprise', 'audit_status', "audit_status TINYINT DEFAULT 1 COMMENT '入驻审核:0待审核,1通过,2拒绝'");
    await addColumn('t_enterprise', 'audit_remark', "audit_remark VARCHAR(255) NULL COMMENT '审核意见'");
    await addColumn('t_enterprise', 'contact_email', "contact_email VARCHAR(100) NULL COMMENT '联系邮箱'");
    // 存量企业视为已通过审核
    await pool.query('UPDATE t_enterprise SET audit_status = 1 WHERE audit_status IS NULL');
    console.log('🎉 企业端自助门户迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
