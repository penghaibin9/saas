/**
 * 一键安装（私有化部署）：建库 → 按序迁移所有表 → 创建初始管理员。
 * 非破坏性、可重复执行（建库 IF NOT EXISTS、迁移 IF NOT EXISTS、管理员已存在则跳过）。
 * 不会清空已有数据，区别于会 DROP 重建的 scripts/init-db.sql。
 *
 * 用法：npm run setup     （等价于 node scripts/install.js）
 * 前提：MySQL 已启动；.env 已配置 DB_HOST/DB_USER/DB_PASSWORD/DB_NAME/JWT_SECRET
 */
require('dotenv').config();
const path = require('path');
const { execSync } = require('child_process');
const mysql = require('mysql2/promise');

const ROOT = path.join(__dirname, '..');
const DB_NAME = process.env.DB_NAME || 'internship_management';

function step(n, msg) { console.log(`\n\x1b[36m[${n}]\x1b[0m ${msg}`); }
function run(cmd) { execSync(cmd, { stdio: 'inherit', cwd: ROOT }); }

(async () => {
  console.log('======== 一键安装 · 私有化部署 ========');

  // 0. 前置检查
  step(0, '检查环境变量');
  const miss = ['DB_HOST', 'DB_USER', 'DB_NAME', 'JWT_SECRET'].filter((k) => !process.env[k]);
  if (miss.length) {
    console.error(`\x1b[31m✗ .env 缺少：${miss.join(', ')}。请先 cp .env.example .env 并填写。\x1b[0m`);
    process.exit(1);
  }
  if (!process.env.JWT_SECRET || process.env.JWT_SECRET.length < 16) {
    console.warn('\x1b[33m⚠ JWT_SECRET 过短，生产环境请改为 ≥32 位随机串。\x1b[0m');
  }

  // 1. 建库（非破坏性）
  step(1, `创建数据库 ${DB_NAME}（若不存在）`);
  try {
    const conn = await mysql.createConnection({
      host: process.env.DB_HOST || 'localhost',
      port: Number(process.env.DB_PORT) || 3306,
      user: process.env.DB_USER || 'root',
      password: process.env.DB_PASSWORD || '',
      charset: 'utf8mb4',
    });
    await conn.query(`CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`);
    await conn.end();
    console.log(`  ✓ 数据库就绪`);
  } catch (e) {
    console.error(`\x1b[31m✗ 连接/建库失败：${e.message}\x1b[0m`);
    console.error('  请确认 MySQL 已启动、.env 中账号密码正确、账号有 CREATE 权限。');
    process.exit(1);
  }

  // 2. 迁移所有表
  step(2, '按序迁移所有数据表（migrate:all）');
  run('npm run migrate:all');

  // 3. 初始管理员
  step(3, '创建初始管理员（已存在则跳过）');
  run('node scripts/seed-admin.js');

  console.log('\n\x1b[32m======== ✅ 安装完成 ========\x1b[0m');
  console.log('  初始管理员：admin / 123456  （首次登录请立即修改密码）');
  console.log('  启动服务：  npm start        然后访问 http://服务器IP:3000/admin');
  console.log('  可选演示数据：npm run seed:demo（仅用于演示/答辩，正式上线前清理）');
  process.exit(0);
})().catch((e) => { console.error('\x1b[31m安装失败：\x1b[0m', e.message); process.exit(1); });
