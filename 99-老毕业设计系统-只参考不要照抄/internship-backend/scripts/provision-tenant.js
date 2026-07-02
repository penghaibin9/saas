/**
 * 开通一所学校（SaaS 租户）
 * ───────────────────────────────────────────────────────────
 * 做三件事：1) 建该校独立数据库  2) 在其中跑全部迁移建表
 *           3) 在 master 注册表登记 code→db 映射，并种入该校管理员
 *
 * 用法：
 *   node scripts/provision-tenant.js <code> "<学校名称>" [adminUser] [adminPass]
 * 例：
 *   node scripts/provision-tenant.js hnyz "湖南某职业学院" admin Admin@123
 *
 * 说明：迁移脚本通过 DB_NAME 环境变量指向新库后逐个执行，复用现有 migrate:* 全集。
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const mysql = require('mysql2/promise');
require('dotenv').config();

const MIGRATIONS = [
  'migrate-base-tables', 'migrate-reconcile-base', 'migrate-add-must-change-password',
  'migrate-intern-core', 'migrate-intern-logs', 'migrate-gd-core', 'migrate-gd-thesis',
  'migrate-gd-quality', 'migrate-province', 'migrate-insurance', 'migrate-gd-guidance',
  'migrate-teacher-record', 'migrate-satisfaction', 'migrate-audit', 'migrate-enterprise-portal',
  'migrate-complaint-safety', 'migrate-commercial-wave2', 'migrate-sales-phase1',
  'migrate-commercial-benchmark', 'migrate-ent-pos-commercial', 'migrate-commercial-wave-ai',
];

async function main() {
  const [code, name, adminUser = 'admin', adminPass = '123456'] = process.argv.slice(2);
  if (!code || !name) {
    console.error('用法: node scripts/provision-tenant.js <code> "<学校名称>" [adminUser] [adminPass]');
    process.exit(1);
  }
  if (!/^[a-z0-9][a-z0-9_-]{1,62}$/.test(code)) {
    console.error('code 仅允许小写字母/数字/下划线/连字符（用作子域名），且以字母数字开头');
    process.exit(1);
  }

  const dbName = `internship_${code}`;
  const cfg = {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    multipleStatements: true,
  };

  // 1) 建库
  const admin = await mysql.createConnection(cfg);
  await admin.query(`CREATE DATABASE IF NOT EXISTS \`${dbName}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`);
  console.log(`✅ 数据库已就绪：${dbName}`);
  await admin.end();

  // 1.5) 建核心表（init-db.sql 剥离 CREATE DATABASE / USE 后对新库执行；含 t_user 等基础表）
  {
    const sqlPath = path.join(__dirname, 'init-db.sql');
    let sql = fs.readFileSync(sqlPath, 'utf8')
      .split('\n')
      .filter((line) => !/^\s*CREATE\s+DATABASE/i.test(line) && !/^\s*USE\s+/i.test(line))
      .join('\n');
    const conn = await mysql.createConnection({ ...cfg, database: dbName });
    await conn.query(sql);
    await conn.end();
    console.log('✅ 核心表已建（含 t_user 基础结构）');
  }

  // 2) 跑迁移（让迁移脚本指向新库）
  console.log('⏳ 正在该校库执行迁移建表 ...');
  for (const m of MIGRATIONS) {
    const file = path.join(__dirname, `${m}.js`);
    try {
      execSync(`node "${file}"`, { stdio: 'pipe', env: { ...process.env, DB_NAME: dbName } });
      process.stdout.write('·');
    } catch (e) {
      console.error(`\n⚠️  迁移 ${m} 出错（可能已存在，继续）：`, (e.stderr || e.stdout || e.message || '').toString().slice(0, 200));
    }
  }
  console.log('\n✅ 建表完成');

  // 3) 种管理员
  const pwdHash = require('../utils/password');
  const t = await mysql.createConnection({ ...cfg, database: dbName });
  const [exist] = await t.query('SELECT id FROM t_user WHERE username = ? LIMIT 1', [adminUser]);
  if (!exist.length) {
    const hash = await pwdHash.hash(adminPass);
    await t.query(
      'INSERT INTO t_user (username, password, real_name, role, status, must_change_password) VALUES (?,?,?,1,1,1)',
      [adminUser, hash, name + '管理员']
    );
    console.log(`✅ 已创建管理员：${adminUser} / ${adminPass}（首登需改密）`);
  } else {
    console.log(`ℹ️  管理员 ${adminUser} 已存在，跳过`);
  }
  await t.end();

  // 4) 登记到 master 注册表
  const masterDb = process.env.MASTER_DB_NAME || process.env.DB_NAME || 'internship_management';
  const master = await mysql.createConnection({ ...cfg, database: masterDb });
  const tenantModel = require('../models/tenantModel');
  await tenantModel.ensureTable();
  const [has] = await master.query('SELECT id FROM t_tenant WHERE code = ?', [code]);
  if (!has.length) {
    await master.query(
      'INSERT INTO t_tenant (code, name, db_name, status) VALUES (?,?,?,1)',
      [code, name, dbName]
    );
    console.log(`✅ 已登记租户：${code} → ${dbName}`);
  } else {
    console.log(`ℹ️  租户 ${code} 已登记，跳过`);
  }
  await master.end();

  console.log(`\n🎉 学校开通完成：code=${code}  库=${dbName}`);
  console.log(`   SaaS 访问：以子域名 ${code}.<你的域名> 或登录时携带 X-Tenant: ${code}`);
  process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
