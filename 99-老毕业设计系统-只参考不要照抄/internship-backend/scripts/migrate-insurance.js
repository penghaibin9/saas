/**
 * 迁移：实习保险单 (t_insurance)。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-insurance.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_insurance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL COMMENT '学生',
        insurance_type VARCHAR(100) COMMENT '保险险种',
        policy_no VARCHAR(100) COMMENT '保单号',
        company VARCHAR(200) COMMENT '承保公司',
        start_date DATE COMMENT '生效开始日期',
        end_date DATE COMMENT '生效结束日期',
        college_id INT COMMENT '所属学院',
        remark VARCHAR(255) COMMENT '备注',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_college (college_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习保险单表'
    `);
    console.log('✅ t_insurance 就绪');
    console.log('🎉 实习保险单表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
