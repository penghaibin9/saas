/**
 * 商业级改造 · Tier1 迁移
 *  - t_checkin 增加 photo_url（拍照打卡存证）
 *  - 新建 t_agreement（电子实习协议三方签署）
 * 幂等：列存在性判断 + CREATE TABLE IF NOT EXISTS。
 * 运行：node scripts/migrate-commercial-t1.js
 */
require('dotenv').config();
const pool = require('../config/db');

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
    // 1) 打卡照片
    if (!(await columnExists('t_checkin', 'photo_url'))) {
      await pool.query(`ALTER TABLE t_checkin ADD COLUMN photo_url VARCHAR(255) NULL COMMENT '打卡照片(防代打卡)' AFTER address`);
      console.log('✅ t_checkin.photo_url 已添加');
    } else {
      console.log('· t_checkin.photo_url 已存在，跳过');
    }

    // 2) 电子实习协议
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_agreement (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL COMMENT '学生',
        application_id INT COMMENT '关联录用申请',
        enterprise_id INT COMMENT '企业',
        position_id INT COMMENT '岗位',
        teacher_id INT COMMENT '校内指导教师',
        college_id INT COMMENT '学院',
        title VARCHAR(200) NOT NULL COMMENT '协议标题',
        content LONGTEXT COMMENT '协议正文/条款',
        start_date DATE COMMENT '实习开始',
        end_date DATE COMMENT '实习结束',
        student_signed TINYINT DEFAULT 0 COMMENT '学生是否签署',
        student_sign_name VARCHAR(100) COMMENT '学生签名',
        student_sign_time DATETIME COMMENT '学生签署时间',
        teacher_signed TINYINT DEFAULT 0 COMMENT '教师是否签署',
        teacher_sign_time DATETIME COMMENT '教师签署时间',
        school_signed TINYINT DEFAULT 0 COMMENT '校方是否盖章',
        school_sign_time DATETIME COMMENT '校方盖章时间',
        file_url VARCHAR(255) COMMENT '协议附件(可选)',
        status TINYINT DEFAULT 0 COMMENT '0待签署,1签署中,2已生效,3已作废',
        is_deleted TINYINT DEFAULT 0,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_student (student_id),
        INDEX idx_teacher (teacher_id),
        INDEX idx_college (college_id),
        INDEX idx_status (status)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '电子实习协议表'
    `);
    console.log('✅ t_agreement 就绪');

    console.log('🎉 Tier1 迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
