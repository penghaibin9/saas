/**
 * 迁移：毕业设计质量监控/互查 (t_quality_check)。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-gd-quality.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_quality_check (
        id INT AUTO_INCREMENT PRIMARY KEY,
        batch_name VARCHAR(200) NOT NULL COMMENT '检查批次名称',
        check_type VARCHAR(10) DEFAULT 'census' COMMENT 'census普查, sample抽查',
        scope VARCHAR(10) DEFAULT 'cross' COMMENT 'self自查, cross互查',
        checker_id INT COMMENT '检查主体(教师)',
        student_id INT NOT NULL COMMENT '待查学生',
        achievement_id INT COMMENT '关联成果',
        college_id INT COMMENT '学院',
        status TINYINT DEFAULT 0 COMMENT '0待审阅,1通过,2驳回,3未完成',
        opinion VARCHAR(500) COMMENT '检查意见/驳回原因',
        review_time DATETIME COMMENT '审阅时间',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_checker (checker_id),
        INDEX idx_student (student_id),
        INDEX idx_college (college_id),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计质量监控/互查表'
    `);
    console.log('✅ t_quality_check 就绪');
    console.log('🎉 质量监控表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
