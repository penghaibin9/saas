/**
 * 迁移：毕业设计指导记录 (t_gd_guidance)。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-gd-guidance.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_guidance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        topic_id INT COMMENT '关联选题',
        student_id INT NOT NULL COMMENT '学生',
        teacher_id INT NOT NULL COMMENT '指导老师',
        college_id INT COMMENT '学院',
        title VARCHAR(200) COMMENT '指导主题',
        content TEXT COMMENT '指导内容',
        guidance_date DATE COMMENT '指导日期',
        file_url VARCHAR(255) COMMENT '附件',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_teacher (teacher_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计指导记录表'
    `);
    console.log('✅ t_gd_guidance 就绪');
    console.log('🎉 毕业设计指导记录表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
