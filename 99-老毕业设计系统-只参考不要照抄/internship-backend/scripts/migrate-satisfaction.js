/**
 * 迁移：企业满意度评价 (t_satisfaction)。
 * 幂等：CREATE TABLE IF NOT EXISTS。运行：node scripts/migrate-satisfaction.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_satisfaction (
        id INT AUTO_INCREMENT PRIMARY KEY,
        enterprise_id INT NOT NULL COMMENT '企业',
        student_id INT COMMENT '被评价学生(可空)',
        college_id INT COMMENT '学院',
        score TINYINT NOT NULL COMMENT '满意度评分 1-5',
        content VARCHAR(500) COMMENT '评价内容',
        created_by INT COMMENT '填写人',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_enterprise (enterprise_id),
        INDEX idx_college (college_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '企业满意度评价表'
    `);
    console.log('✅ t_satisfaction 就绪');
    console.log('🎉 企业满意度表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
