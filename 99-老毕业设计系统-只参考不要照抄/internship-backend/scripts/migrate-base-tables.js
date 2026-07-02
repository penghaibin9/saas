/**
 * 迁移：非破坏性补齐基础表（college/major/class/enterprise/position/application/report/notification）。
 * 仅 CREATE TABLE IF NOT EXISTS，不 DROP、不动已存在的 t_user 数据。
 * 适用于数据库缺失基础表的情况（区别于会清库重建的 init-db.sql）。
 * 运行：node scripts/migrate-base-tables.js
 */
require('dotenv').config();
const pool = require('../config/db');

const TABLES = [
  ['t_college', `CREATE TABLE IF NOT EXISTS t_college (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL, code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT, status TINYINT DEFAULT 1, is_deleted TINYINT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '学院表'`],

  ['t_major', `CREATE TABLE IF NOT EXISTS t_major (
    id INT AUTO_INCREMENT PRIMARY KEY, college_id INT NOT NULL,
    name VARCHAR(100) NOT NULL, code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT, status TINYINT DEFAULT 1, is_deleted TINYINT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_college (college_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '专业表'`],

  ['t_class', `CREATE TABLE IF NOT EXISTS t_class (
    id INT AUTO_INCREMENT PRIMARY KEY, college_id INT NOT NULL, major_id INT NOT NULL,
    name VARCHAR(100) NOT NULL, grade INT, status TINYINT DEFAULT 1, is_deleted TINYINT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_college (college_id), INDEX idx_major (major_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '班级表'`],

  ['t_enterprise', `CREATE TABLE IF NOT EXISTS t_enterprise (
    id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(200) NOT NULL,
    short_name VARCHAR(100), industry VARCHAR(100), address VARCHAR(255),
    contact_name VARCHAR(100), contact_phone VARCHAR(20), description TEXT,
    status TINYINT DEFAULT 1, is_deleted TINYINT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '企业表'`],

  ['t_position', `CREATE TABLE IF NOT EXISTS t_position (
    id INT AUTO_INCREMENT PRIMARY KEY, enterprise_id INT NOT NULL,
    title VARCHAR(200) NOT NULL, description TEXT, requirement TEXT,
    salary VARCHAR(100), headcount INT DEFAULT 1, location VARCHAR(200),
    start_date DATE, end_date DATE, college_id INT, status TINYINT DEFAULT 1,
    is_deleted TINYINT DEFAULT 0, create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_enterprise (enterprise_id), INDEX idx_status (status)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '岗位表'`],

  ['t_application', `CREATE TABLE IF NOT EXISTS t_application (
    id INT AUTO_INCREMENT PRIMARY KEY, student_id INT NOT NULL, position_id INT NOT NULL,
    enterprise_id INT NOT NULL, teacher_id INT, student_remark TEXT, teacher_opinion TEXT,
    admin_opinion TEXT, status INT DEFAULT 0, apply_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted TINYINT DEFAULT 0, create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_student (student_id), INDEX idx_position (position_id),
    INDEX idx_teacher (teacher_id), INDEX idx_status (status)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '申请表'`],

  ['t_report', `CREATE TABLE IF NOT EXISTS t_report (
    id INT AUTO_INCREMENT PRIMARY KEY, application_id INT NOT NULL, student_id INT NOT NULL,
    title VARCHAR(200) NOT NULL, content LONGTEXT, file_url VARCHAR(255),
    teacher_score INT, teacher_comment TEXT, status INT DEFAULT 0, submit_time DATETIME,
    is_deleted TINYINT DEFAULT 0, create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_application (application_id), INDEX idx_student (student_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '实习报告表'`],

  ['t_notification', `CREATE TABLE IF NOT EXISTS t_notification (
    id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, title VARCHAR(100) NOT NULL,
    content TEXT NOT NULL, type VARCHAR(30) DEFAULT 'info', is_read TINYINT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id), INDEX idx_is_read (is_read)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '通知表'`],
];

async function run() {
  try {
    for (const [name, sql] of TABLES) {
      await pool.query(sql);
      console.log(`✅ ${name} 就绪`);
    }
    console.log('🎉 基础表补齐完成（未删除任何已有数据）');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
