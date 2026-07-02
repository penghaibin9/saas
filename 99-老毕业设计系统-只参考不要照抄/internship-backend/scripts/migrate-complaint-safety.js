/**
 * 迁移：投诉/异常上报 + 紧急联系人（实习安全合规闭环）。
 *  - 新建 t_complaint（投诉/异常/安全事件上报与处理）
 *  - t_user 增加 emergency_name / emergency_phone / emergency_relation（学生紧急联系人）
 * 幂等：CREATE TABLE IF NOT EXISTS + 列存在性判断。
 * 运行：node scripts/migrate-complaint-safety.js
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
async function addColumn(table, column, ddl) {
  if (await columnExists(table, column)) console.log(`· ${table}.${column} 已存在，跳过`);
  else { await pool.query(`ALTER TABLE ${table} ADD COLUMN ${ddl}`); console.log(`✅ ${table}.${column} 已添加`); }
}

async function run() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS t_complaint (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        category      VARCHAR(20) DEFAULT 'complaint' COMMENT '类型:complaint投诉,incident异常,safety安全',
        title         VARCHAR(200) NOT NULL COMMENT '标题',
        content       TEXT COMMENT '详情',
        student_id    INT COMMENT '关联学生',
        reporter_id   INT COMMENT '上报人(可匿名为空)',
        reporter_role TINYINT COMMENT '上报人角色',
        contact_phone VARCHAR(30) COMMENT '联系电话',
        college_id    INT COMMENT '所属学院(用于分院隔离)',
        urgency       TINYINT DEFAULT 1 COMMENT '紧急度:0一般,1较急,2紧急',
        status        TINYINT DEFAULT 0 COMMENT '0待处理,1处理中,2已处理,3已关闭',
        handler_id    INT COMMENT '处理人',
        handle_remark TEXT COMMENT '处理意见',
        handle_time   DATETIME COMMENT '处理时间',
        is_deleted    TINYINT DEFAULT 0,
        create_time   DATETIME DEFAULT CURRENT_TIMESTAMP,
        update_time   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_status (status),
        INDEX idx_college (college_id),
        INDEX idx_student (student_id),
        INDEX idx_category (category)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '投诉/异常/安全上报表'
    `);
    console.log('✅ t_complaint 就绪');

    await addColumn('t_user', 'emergency_name', "emergency_name VARCHAR(50) NULL COMMENT '紧急联系人姓名'");
    await addColumn('t_user', 'emergency_phone', "emergency_phone VARCHAR(30) NULL COMMENT '紧急联系人电话'");
    await addColumn('t_user', 'emergency_relation', "emergency_relation VARCHAR(30) NULL COMMENT '与学生关系'");

    console.log('🎉 投诉/安全 + 紧急联系人迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
