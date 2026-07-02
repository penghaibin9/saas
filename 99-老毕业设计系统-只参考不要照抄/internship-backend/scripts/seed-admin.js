/**
 * 创建测试管理员账号（仅开发环境使用）
 * 运行: node scripts/seed-admin.js
 */
require('dotenv').config();
const pwdHash = require('../utils/password');
const pool = require('../config/db');

async function seedAdmin() {
  const username = 'admin';
  // 初始密码可由环境变量覆盖（生产部署应传入随机强密码）；无论何值都强制首次登录改密
  const isProduction = process.env.NODE_ENV === 'production';
  const configuredPassword = process.env.INITIAL_ADMIN_PASSWORD || '';
  if (isProduction && (!configuredPassword || configuredPassword === '123456' || configuredPassword.length < 12)) {
    throw new Error('生产环境必须设置至少 12 位且不能为 123456 的 INITIAL_ADMIN_PASSWORD');
  }
  const password = configuredPassword || '123456';
  const realName = '系统管理员';

  const [existing] = await pool.query(
    'SELECT id FROM t_user WHERE username = ? AND is_deleted = 0',
    [username]
  );

  if (existing.length) {
    console.log('测试账号已存在，跳过创建');
    console.log('用户名: admin');
    console.log('管理员账号已存在；脚本不会显示或重置现有密码');
    process.exit(0);
  }

  const hashed = await pwdHash.hash(password);
  // must_change_password=1：与 README/守卫一致，强制首次登录改密，避免默认弱口令长期有效
  await pool.query(
    `INSERT INTO t_user (username, password, real_name, role, status, must_change_password)
     VALUES (?, ?, ?, 1, 1, 1)`,
    [username, hashed, realName]
  );

  console.log('✅ 测试管理员创建成功');
  console.log('用户名: admin');
  console.log(isProduction ? '初始密码已按环境变量设置（不在日志中显示）' : `密码: ${password}`);
  console.log('⚠️  首次登录将强制修改密码');
  process.exit(0);
}

seedAdmin().catch((err) => {
  console.error('创建失败:', err.message);
  process.exit(1);
});
