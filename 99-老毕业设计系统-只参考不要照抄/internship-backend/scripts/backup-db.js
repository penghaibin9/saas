/**
 * MySQL 备份脚本（生产交付）
 * 用法：node scripts/backup-db.js [输出目录]
 * 需安装 mysqldump 并在 PATH 中可用
 */
require('dotenv').config();
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const host = process.env.DB_HOST || 'localhost';
const user = process.env.DB_USER || 'root';
const password = process.env.DB_PASSWORD || '';
const database = process.env.DB_NAME || 'internship_management';
const outDir = process.argv[2] || path.join(__dirname, '..', 'backups');
const mysqldumpBin = process.env.MYSQLDUMP_BIN || 'mysqldump';

if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const file = path.join(outDir, `backup-${database}-${stamp}.sql`);

try {
  const args = ['-h', host, '-u', user, '--single-transaction', '--routines', '--triggers', '--hex-blob', database];
  const result = spawnSync(mysqldumpBin, args, {
    encoding: 'buffer', maxBuffer: 256 * 1024 * 1024,
    env: Object.assign({}, process.env, password ? { MYSQL_PWD: password } : {})
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(String(result.stderr || `mysqldump 退出码 ${result.status}`));
  if (!result.stdout || result.stdout.length < 100) throw new Error('备份输出为空或异常短');
  fs.writeFileSync(file, result.stdout);
  console.log('✅ 备份完成:', file);
  console.log('   大小:', result.stdout.length, 'bytes');
} catch (e) {
  console.error('❌ 备份失败:', e.message);
  console.error('请确认 mysqldump 已安装且 .env 数据库配置正确');
  process.exit(1);
}
