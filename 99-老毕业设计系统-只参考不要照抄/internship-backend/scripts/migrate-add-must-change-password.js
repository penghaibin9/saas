/**
 * 迁移：为 t_user 增加 must_change_password 字段（首次登录强制改密）。
 * 幂等：列已存在时跳过。运行：node scripts/migrate-add-must-change-password.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    const [cols] = await pool.query(
      `SELECT COLUMN_NAME FROM information_schema.COLUMNS
       WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 't_user' AND COLUMN_NAME = 'must_change_password'`
    );
    if (cols.length) {
      console.log('✅ 字段 must_change_password 已存在，无需迁移');
      return;
    }
    await pool.query(
      `ALTER TABLE t_user
       ADD COLUMN must_change_password TINYINT DEFAULT 0
       COMMENT '是否需要强制修改密码：1是,0否' AFTER status`
    );
    console.log('✅ 已为 t_user 添加 must_change_password 字段');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
