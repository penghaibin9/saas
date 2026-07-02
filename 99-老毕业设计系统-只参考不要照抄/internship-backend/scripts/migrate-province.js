/**
 * 迁移：省厅毕业生名单 (t_province_student)，用于名单获取/校验/成果上传。
 * 幂等：CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-province.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_province_student (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL COMMENT '姓名',
        gender VARCHAR(10) COMMENT '性别',
        id_card VARCHAR(30) COMMENT '身份证号',
        eeid VARCHAR(50) COMMENT '学号(用于匹配)',
        cert_no VARCHAR(50) COMMENT '毕业证书编号',
        edu_system VARCHAR(20) COMMENT '学制',
        major_code VARCHAR(50) COMMENT '专业编号',
        major_name VARCHAR(100) COMMENT '专业名称',
        batch_year INT COMMENT '届别年份',
        matched TINYINT DEFAULT 0 COMMENT '是否匹配到本校学生',
        local_student_id INT COMMENT '匹配到的本校学生ID',
        achievement_link VARCHAR(500) COMMENT '已上传的毕业设计成果链接',
        uploaded TINYINT DEFAULT 0 COMMENT '成果是否已上传省平台',
        upload_time DATETIME COMMENT '上传时间',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_eeid (eeid),
        INDEX idx_matched (matched)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '省厅毕业生名单表'
    `);
    console.log('✅ t_province_student 就绪');
    console.log('🎉 省厅名单表迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
