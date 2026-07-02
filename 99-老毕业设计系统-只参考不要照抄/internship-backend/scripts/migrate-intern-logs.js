/**
 * 迁移：实习周报/月报(t_intern_log) 与 请假申请(t_leave)。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-intern-logs.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_intern_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL COMMENT '学生',
        assignment_id INT COMMENT '关联实习分配',
        plan_id INT COMMENT '关联实习计划',
        teacher_id INT COMMENT '指导老师(冗余,便于查询)',
        type VARCHAR(10) NOT NULL DEFAULT 'weekly' COMMENT '类型：weekly周报,monthly月报',
        title VARCHAR(200) NOT NULL COMMENT '标题',
        content LONGTEXT COMMENT '内容',
        file_url VARCHAR(255) COMMENT '附件',
        status TINYINT DEFAULT 0 COMMENT '0草稿,1提交,2通过,3驳回',
        teacher_comment TEXT COMMENT '教师评语',
        reject_reason VARCHAR(255) COMMENT '驳回原因',
        submit_time DATETIME COMMENT '提交时间',
        review_time DATETIME COMMENT '批阅时间',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_teacher (teacher_id),
        INDEX idx_type (type),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习周报/月报表'
    `);
    console.log('✅ t_intern_log 就绪');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_leave (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL COMMENT '学生',
        assignment_id INT COMMENT '关联实习分配',
        teacher_id INT COMMENT '审批教师',
        start_date DATE COMMENT '请假开始',
        end_date DATE COMMENT '请假结束',
        days DECIMAL(4,1) COMMENT '请假天数',
        reason TEXT COMMENT '请假事由',
        status TINYINT DEFAULT 0 COMMENT '0草稿,1提交,2通过,3驳回',
        reject_reason VARCHAR(255) COMMENT '驳回原因',
        submit_time DATETIME COMMENT '提交时间',
        review_time DATETIME COMMENT '审批时间',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_teacher (teacher_id),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '请假申请表'
    `);
    console.log('✅ t_leave 就绪');

    console.log('🎉 周报/月报/请假表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
