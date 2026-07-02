/**
 * 打卡双时段迁移
 *  - t_checkin 增加 slot（day=全天/am=上班/pm=下班）支持每日上下班两次打卡
 *  - 同步两个系统配置：checkin_double_slot(双时段开关) / checkin_fence_mode(围栏模式)
 * 幂等：列存在性判断 + INSERT IGNORE。
 * 运行：node scripts/migrate-checkin-slot.js
 */
require('dotenv').config();
const pool = require('../config/db');
const systemConfigModel = require('../models/systemConfigModel');

async function columnExists(table, column) {
  const [rows] = await pool.query(
    `SELECT COUNT(*) AS c FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?`,
    [table, column]
  );
  return rows[0].c > 0;
}

async function run() {
  try {
    // 1) 打卡班次
    if (!(await columnExists('t_checkin', 'slot'))) {
      await pool.query(
        `ALTER TABLE t_checkin ADD COLUMN slot VARCHAR(8) NOT NULL DEFAULT 'day'
         COMMENT '打卡班次: day=全天/am=上班/pm=下班' AFTER remark`
      );
      console.log('✅ t_checkin.slot 已添加');
    } else {
      console.log('· t_checkin.slot 已存在，跳过');
    }

    // 2) 系统配置默认值（确保表存在并写入新键）
    await systemConfigModel.ensureTable();
    console.log('✅ 系统配置 checkin_double_slot / checkin_fence_mode 已就绪');

    console.log('🎉 打卡双时段迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
