/**
 * 真卖路线 Phase1 冒烟测试
 * 运行：node scripts/test-sales-phase1.js
 */
require('dotenv').config();
const BASE = `http://localhost:${process.env.PORT || 3000}/api`;
let pass = 0, fail = 0;

function check(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓', name); }
  else { fail++; console.log('  ✗', name, extra || ''); }
}

async function api(method, path, { token, body } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let json; try { json = await res.json(); } catch { json = null; }
  return { status: res.status, json };
}

(async () => {
  console.log('== 真卖 Phase1 冒烟 ==', BASE);
  try {
    let login = await api('POST', '/users/login', { body: { username: 'admin', password: 'admin123' } });
    let token = login.json?.data?.token;
    if (!token) {
      login = await api('POST', '/users/login', { body: { username: 'demo_admin', password: 'demo1234' } });
      token = login.json?.data?.token;
    }
    check('管理员登录', !!token, login.json?.message);
    if (!token) process.exit(1);

    const ch = await api('GET', '/system-config/channels', { token });
    check('GET /system-config/channels', ch.status === 200 && ch.json?.success);

    const list = await api('GET', '/assignment-changes?page_size=5', { token });
    check('GET /assignment-changes', list.status === 200 && list.json?.success);

    const casDemo = await api('POST', '/integration/cas/login', {
      body: { username: login.json?.data?.user?.username || 'demo_admin' }
    });
    check('POST /integration/cas/login (需启用 CAS)', casDemo.status === 200 || casDemo.status === 403, casDemo.json?.message);

    const integ = await api('GET', '/integration/info', { token });
    check('GET /integration/info 含 channels', integ.status === 200 && integ.json?.data?.channels);

    const casRedir = await fetch(BASE + '/integration/cas/redirect?returnTo=/', { redirect: 'manual' });
    check('GET /integration/cas/redirect', casRedir.status === 302 || casRedir.status === 403);

    console.log('\n结果:', pass, '通过,', fail, '失败');
    process.exit(fail ? 1 : 0);
  } catch (e) {
    console.error('测试异常:', e.message);
    process.exit(1);
  }
})();
