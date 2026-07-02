/**
 * 迁移：教师工作记录 (t_teacher_record) —— 覆盖「我的月报」与「我的寻访」。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-teacher-record.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_teacher_record (
        id INT AUTO_INCREMENT PRIMARY KEY,
        teacher_id INT NOT NULL COMMENT '教师',
        type VARCHAR(10) NOT NULL DEFAULT 'monthly' COMMENT 'monthly月报, visit寻访',
        title VARCHAR(200) NOT NULL COMMENT '标题',
        content LONGTEXT COMMENT '内容',
        file_url VARCHAR(255) COMMENT '附件',
        record_date DATE COMMENT '记录日期',
        student_id INT COMMENT '寻访对象学生(可选)',
        enterprise_id INT COMMENT '寻访企业(可选)',
        college_id INT COMMENT '教师所属学院',
        status TINYINT DEFAULT 0 COMMENT '0草稿,1已提交',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_teacher (teacher_id),
        INDEX idx_type (type),
        INDEX idx_college (college_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '教师工作记录(月报/寻访)表'
    `);
    console.log('✅ t_teacher_record 就绪');
    console.log('🎉 教师工作记录表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
