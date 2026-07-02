/**
 * MySQL 恢复脚本（生产交付 / 迁校）
 * 用法：node scripts/restore-db.js <备份文件.sql> [目标库名] [--yes]
 */
require('dotenv').config();
const { spawnSync } = require('child_process');
const fs = require('fs');
const readline = require('readline');

const host = process.env.DB_HOST || 'localhost';
const user = process.env.DB_USER || 'root';
const password = process.env.DB_PASSWORD || '';
const args = process.argv.slice(2).filter((a) => a !== '--yes');
const skipConfirm = process.argv.includes('--yes');
const file = args[0];
const database = args[1] || process.env.DB_NAME || 'internship_management';
const mysqlEnv = Object.assign({}, process.env, password ? { MYSQL_PWD: password } : {});
const mysqlBin = process.env.MYSQL_BIN || 'mysql';

if (!file) {
  console.error('用法：node scripts/restore-db.js <备份文件.sql> [目标库名] [--yes]');
  process.exit(1);
}
if (!fs.existsSync(file)) {
  console.error('❌ 备份文件不存在：', file);
  process.exit(1);
}
if (!/^[A-Za-z0-9_]+$/.test(database)) {
  console.error('❌ 目标库名只能包含字母、数字和下划线');
  process.exit(1);
}

function mysql(mysqlArgs, options) {
  const result = spawnSync(mysqlBin, ['-h', host, '-u', user].concat(mysqlArgs), Object.assign({
    stdio: 'inherit', env: mysqlEnv, maxBuffer: 256 * 1024 * 1024
  }, options || {}));
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`mysql 退出码 ${result.status}`);
}

function run() {
  try {
    mysql(['-e', `CREATE DATABASE IF NOT EXISTS \`${database}\` DEFAULT CHARACTER SET utf8mb4`]);
    console.log(`⏳ 正在恢复到库 [${database}] …`);
    mysql([database], { input: fs.readFileSync(file), stdio: ['pipe', 'inherit', 'inherit'] });
    console.log('✅ 恢复完成。建议随后运行：npm run migrate:up（补齐结构）');
  } catch (e) {
    console.error('❌ 恢复失败:', e.message);
    console.error('请确认 mysql 客户端已安装、.env 配置正确、备份文件完整');
    process.exit(1);
  }
}

if (skipConfirm) return run();
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
rl.question(`⚠️  将把备份导入库 [${database}]（覆盖同名表数据），确认？输入 yes 继续：`, (ans) => {
  rl.close();
  if (ans.trim().toLowerCase() === 'yes') run();
  else { console.log('已取消'); process.exit(0); }
});
