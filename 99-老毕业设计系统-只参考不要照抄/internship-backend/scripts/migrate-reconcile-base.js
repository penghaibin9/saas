/**
 * 迁移：协调既有基础表(college/major/class)与本项目模型的列差异。
 * 背景：数据库里这几张表来自另一套结构，缺少本项目所需的列。
 * 处理：缺什么列就 ADD 什么列（幂等、非破坏，不删数据）。
 * 运行：node scripts/migrate-reconcile-base.js
 */
require('dotenv').config();
const pool = require('../config/db');

async function colExists(table, column) {
  const [rows] = await pool.query(
    `SELECT 1 FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?`, [table, column]);
  return rows.length > 0;
}
async function tblExists(table) {
  const [rows] = await pool.query(
    `SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?`, [table]);
  return rows.length > 0;
}

// [table, column, ddl]
const COLUMNS = [
  ['t_college', 'status', "ADD COLUMN status TINYINT DEFAULT 1 COMMENT '状态：1启用,0禁用'"],
  ['t_major', 'description', "ADD COLUMN description TEXT COMMENT '专业描述'"],
  ['t_major', 'status', "ADD COLUMN status TINYINT DEFAULT 1 COMMENT '状态：1启用,0禁用'"],
  ['t_class', 'college_id', "ADD COLUMN college_id INT COMMENT '所属学院ID'"],
  ['t_class', 'grade', "ADD COLUMN grade INT COMMENT '年级(如2024)'"],
  ['t_class', 'status', "ADD COLUMN status TINYINT DEFAULT 1 COMMENT '状态：1启用,0禁用'"],
];

async function run() {
  try {
    for (const [table, column, ddl] of COLUMNS) {
      if (!(await tblExists(table))) { console.log(`↩️  ${table} 不存在，跳过`); continue; }
      if (await colExists(table, column)) { console.log(`↩️  ${table}.${column} 已存在`); continue; }
      await pool.query(`ALTER TABLE ${table} ${ddl}`);
      console.log(`✅ ${table} 增加列 ${column}`);
    }
    // 若 t_class 有旧的 year 列而 grade 为空，则用 year 回填 grade，并放开 year 的 NOT NULL 约束
    if (await colExists('t_class', 'year') && await colExists('t_class', 'grade')) {
      await pool.query('UPDATE t_class SET grade = year WHERE grade IS NULL AND year IS NOT NULL');
      await pool.query('ALTER TABLE t_class MODIFY COLUMN year INT NULL');
      console.log('✅ t_class.grade 已回填，year 改为可空');
    }
    // 用 major 的学院回填 class.college_id
    if (await colExists('t_class', 'college_id')) {
      await pool.query(`UPDATE t_class c JOIN t_major m ON c.major_id = m.id
                        SET c.college_id = m.college_id WHERE c.college_id IS NULL`);
      console.log('✅ t_class.college_id 已按专业回填');
    }
    console.log('🎉 基础表列协调完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
