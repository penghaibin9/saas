/**
 * 迁移：企业库 + 岗位库 商用字段补充。
 *  t_enterprise: credit_code 统一社会信用代码 / nature 企业性质 / scale 规模 /
 *                legal_person 法人 / reg_capital 注册资本 / website 官网 /
 *                license_url 营业执照附件 / coop_status 合作状态(0意向,1合作中,2暂停,3黑名单)
 *  t_position:   intern_type 实习类型(1顶岗,2跟岗,3认知) / major_req 专业要求 /
 *                edu_req 学历要求 / work_time 工作时间 / welfare 福利待遇 /
 *                to_regular 转正机会(0无,1有) / deadline 报名截止
 * 幂等：列存在性判断。运行：node scripts/migrate-ent-pos-commercial.js
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
  if (await columnExists(table, column)) {
    console.log(`· ${table}.${column} 已存在，跳过`);
  } else {
    await pool.query(`ALTER TABLE ${table} ADD COLUMN ${ddl}`);
    console.log(`✅ ${table}.${column} 已添加`);
  }
}

async function run() {
  try {
    // —— 企业库 ——
    await addColumn('t_enterprise', 'credit_code',  "credit_code VARCHAR(50) NULL COMMENT '统一社会信用代码'");
    await addColumn('t_enterprise', 'nature',       "nature VARCHAR(30) NULL COMMENT '企业性质'");
    await addColumn('t_enterprise', 'scale',        "scale VARCHAR(20) NULL COMMENT '企业规模'");
    await addColumn('t_enterprise', 'legal_person', "legal_person VARCHAR(50) NULL COMMENT '法定代表人'");
    await addColumn('t_enterprise', 'reg_capital',  "reg_capital VARCHAR(50) NULL COMMENT '注册资本'");
    await addColumn('t_enterprise', 'website',      "website VARCHAR(120) NULL COMMENT '官网'");
    await addColumn('t_enterprise', 'license_url',  "license_url VARCHAR(255) NULL COMMENT '营业执照附件URL'");
    await addColumn('t_enterprise', 'coop_status',  "coop_status TINYINT DEFAULT 1 COMMENT '合作状态:0意向,1合作中,2暂停,3黑名单'");

    // —— 岗位库 ——
    await addColumn('t_position', 'intern_type', "intern_type TINYINT NULL COMMENT '实习类型:1顶岗,2跟岗,3认知'");
    await addColumn('t_position', 'major_req',   "major_req VARCHAR(200) NULL COMMENT '专业要求'");
    await addColumn('t_position', 'edu_req',     "edu_req VARCHAR(20) NULL COMMENT '学历要求'");
    await addColumn('t_position', 'work_time',   "work_time VARCHAR(60) NULL COMMENT '工作时间'");
    await addColumn('t_position', 'welfare',     "welfare VARCHAR(255) NULL COMMENT '福利待遇'");
    await addColumn('t_position', 'to_regular',  "to_regular TINYINT DEFAULT 0 COMMENT '转正机会:0无,1有'");
    await addColumn('t_position', 'deadline',    "deadline DATE NULL COMMENT '报名截止日期'");

    console.log('🎉 企业库/岗位库商用字段迁移完成');
  } catch (err) {
    console.error('❌ 迁移失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
