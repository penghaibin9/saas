/**
 * 迁移：毕业设计 选题指导 / 成绩 / 设计成果。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-gd-thesis.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    // 选题与指导老师
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_topic (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(200) NOT NULL COMMENT '选题名称',
        student_id INT COMMENT '学生',
        teacher_id INT COMMENT '指导老师',
        college_id INT COMMENT '学院',
        major_id INT COMMENT '专业',
        class_id INT COMMENT '班级',
        source VARCHAR(100) COMMENT '课题来源',
        type VARCHAR(100) COMMENT '课题类型',
        description TEXT COMMENT '课题简介',
        status TINYINT DEFAULT 0 COMMENT '0待确认,1已指派,2已确认',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_teacher (teacher_id),
        INDEX idx_college (college_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计选题及指导老师表'
    `);
    console.log('✅ t_gd_topic 就绪');

    // 成绩
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_grade (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL COMMENT '学生',
        topic_id INT COMMENT '选题',
        teacher_id INT COMMENT '录入教师',
        class_id INT COMMENT '班级',
        topic_title VARCHAR(200) COMMENT '选题名称(冗余)',
        review_score DECIMAL(5,2) COMMENT '评阅成绩',
        defense_score DECIMAL(5,2) COMMENT '答辩成绩',
        total_score DECIMAL(5,2) COMMENT '综合成绩',
        remark VARCHAR(255) COMMENT '备注',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_student (student_id),
        INDEX idx_teacher (teacher_id)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计成绩表'
    `);
    console.log('✅ t_gd_grade 就绪');

    // 设计成果上传/审阅
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_gd_achievement (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL COMMENT '学生',
        topic_id INT COMMENT '选题',
        teacher_id INT COMMENT '指导老师',
        title VARCHAR(200) NOT NULL COMMENT '成果标题',
        link VARCHAR(500) COMMENT '成果链接',
        file_url VARCHAR(255) COMMENT '成果附件',
        status TINYINT DEFAULT 0 COMMENT '0待审阅,1通过,2驳回,3未完成',
        reject_reason VARCHAR(255) COMMENT '驳回原因',
        submit_time DATETIME COMMENT '提交时间',
        review_time DATETIME COMMENT '审阅时间',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_teacher (teacher_id),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '毕业设计成果表'
    `);
    console.log('✅ t_gd_achievement 就绪');

    console.log('🎉 毕业设计选题/成绩/成果表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
