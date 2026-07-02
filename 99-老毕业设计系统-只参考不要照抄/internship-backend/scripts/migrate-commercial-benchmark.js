/**
 * 商用对标迁移：习讯云/校友邦/工学云/论无忧能力补齐
 * 运行：node scripts/migrate-commercial-benchmark.js
 */
require('dotenv').config();
const pool = require('../config/db');
const benchmarkModel = require('../models/benchmarkModel');

async function columnExists(table, col) {
  const [rows] = await pool.query(
    `SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?`,
    [table, col]
  );
  return rows.length > 0;
}

async function addColumn(table, col, ddl) {
  if (!(await columnExists(table, col))) {
    await pool.query(`ALTER TABLE ${table} ADD COLUMN ${col} ${ddl}`);
    console.log(`✅ ${table}.${col}`);
  } else console.log(`↩️ ${table}.${col}`);
}

async function main() {
  await benchmarkModel.ensureTables();

  await addColumn('t_gd_achievement', 'doc_type', "VARCHAR(20) DEFAULT 'other' COMMENT 'proposal|midterm|draft|final|other'");
  await addColumn('t_gd_achievement', 'version', 'INT DEFAULT 1');
  await addColumn('t_gd_grade', 'published', 'TINYINT DEFAULT 0');
  await addColumn('t_gd_grade', 'review_teacher_id', 'INT NULL');
  await addColumn('t_gd_grade', 'review_score_2', 'DECIMAL(5,2) NULL COMMENT "双评"');
  await addColumn('t_gd_grade', 'blind_review', 'TINYINT DEFAULT 0');
  await addColumn('t_checkin', 'is_makeup', 'TINYINT DEFAULT 0');
  await addColumn('t_checkin', 'makeup_status', 'TINYINT NULL COMMENT "0待审1通过2驳回"');
  await addColumn('t_checkin', 'makeup_reason', 'VARCHAR(255) NULL');
  await addColumn('t_class', 'head_teacher_id', 'INT NULL COMMENT "班主任"');

  console.log('✅ 商用对标迁移完成');
  process.exit(0);
}

main().catch(e => { console.error(e); process.exit(1); });
