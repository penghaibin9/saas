/** 生产就绪检查：只读，不修改数据库或文件。 */
require('dotenv').config();
const fs = require('fs');
const path = require('path');
const pool = require('../config/db');

const root = path.resolve(__dirname, '..', '..');
const checks = [];
const add = (name, ok, detail) => checks.push({ name, ok: !!ok, detail });

async function main() {
  const jwt = process.env.JWT_SECRET || '';
  const initialPassword = process.env.INITIAL_ADMIN_PASSWORD || '';
  add('NODE_ENV=production', process.env.NODE_ENV === 'production', process.env.NODE_ENV || '未设置');
  const jwtOk = jwt.length >= 32 && !/your_|secret|123456/i.test(jwt);
  add('JWT_SECRET 强度', jwtOk, jwtOk ? '通过' : '至少32位，且不能使用示例或常见弱值');
  add('生产管理员初始密码', initialPassword.length >= 12 && initialPassword !== '123456', '至少12位且不能使用默认值');
  add('对外 HTTPS 地址', /^https:\/\//i.test(process.env.APP_PUBLIC_URL || ''), process.env.APP_PUBLIC_URL || '未设置');
  add('CORS 白名单', !!process.env.CORS_ORIGIN && process.env.CORS_ORIGIN !== '*', process.env.CORS_ORIGIN || '未设置');
  add('微信 AppID', !!process.env.WX_MP_APPID, process.env.WX_MP_APPID ? '已设置' : '未设置');
  add('微信 AppSecret', !!process.env.WX_MP_SECRET, process.env.WX_MP_SECRET ? '已设置（已隐藏）' : '未设置');

  const project = JSON.parse(fs.readFileSync(path.join(root, 'miniprogram', 'project.config.json'), 'utf8'));
  const mpConfig = fs.readFileSync(path.join(root, 'miniprogram', 'config.js'), 'utf8');
  add('小程序正式 AppID', project.appid && project.appid !== 'touristappid', project.appid === 'touristappid' ? '仍为游客 AppID' : '已设置');
  add('小程序正式 API', !/api\.example\.com/i.test(mpConfig), /api\.example\.com/i.test(mpConfig) ? '仍有示例域名' : '已替换');

  try {
    const [users] = await pool.query(`SELECT
      SUM(username LIKE 'demo\\_%' OR username LIKE 'smoke\\_%' OR username LIKE 'crud\\_%') AS test_users,
      SUM(username='admin' AND must_change_password=1) AS admin_must_change
      FROM t_user WHERE is_deleted=0`);
    add('演示/测试账号已清理', Number(users[0].test_users || 0) === 0, `发现 ${Number(users[0].test_users || 0)} 个`);
    add('管理员已完成首次改密', Number(users[0].admin_must_change || 0) === 0, Number(users[0].admin_must_change || 0) ? 'admin 仍需改密' : '通过');
    add('数据库连接', true, '正常');
  } catch (e) {
    add('数据库连接', false, e.message);
  }

  for (const c of checks) console.log(`${c.ok ? '✅' : '❌'} ${c.name}：${c.detail}`);
  const failed = checks.filter((c) => !c.ok).length;
  console.log(`\n结果：${checks.length - failed}/${checks.length} 项通过，${failed} 项待处理。`);
  process.exitCode = failed ? 1 : 0;
}

main().finally(() => pool.end()).catch((e) => { console.error(e); process.exitCode = 1; });
