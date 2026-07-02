/**
 * 商业化能力 API 冒烟测试
 * 运行：node scripts/test-commercial-wave2.js
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
  console.log('== 商业化 Wave2 冒烟 ==', BASE);
  try {
    const login = await api('POST', '/users/login', { body: { username: 'admin', password: 'admin123' } });
    let token = login.json?.data?.token;
    if (!token) {
      const demo = await api('POST', '/users/login', { body: { username: 'demo_admin', password: 'demo1234' } });
      token = demo.json?.data?.token;
    }
    check('管理员登录', !!token, login.json?.message);
    if (!token) process.exit(1);

    const pub = await api('GET', '/system-config/public');
    check('GET /system-config/public', pub.status === 200 && pub.json?.success);

    const cfg = await api('GET', '/system-config', { token });
    check('GET /system-config (auth)', cfg.status === 200 && cfg.json?.success, cfg.json?.message);

    const wf = await api('GET', '/workflow-config', { token });
    check('GET /workflow-config', wf.status === 200 && (wf.json?.data?.modules?.length > 0), wf.json?.message);

    const fo = await api('GET', '/filings/overview', { token });
    check('GET /filings/overview', fo.status === 200 && fo.json?.success);

    const fl = await api('GET', '/filings?page_size=5', { token });
    check('GET /filings', fl.status === 200 && fl.json?.success);

    const gen = await api('POST', '/filings/generate', { token, body: {} });
    check('POST /filings/generate', gen.status === 200 && gen.json?.success, gen.json?.message);

    const co = await api('GET', '/complaints/overview', { token });
    check('GET /complaints/overview', co.status === 200 && co.json?.success);

    const al = await api('GET', '/audit-logs/overview?days=7', { token });
    check('GET /audit-logs/overview', al.status === 200 && al.json?.success);

    const iw = await api('GET', '/insurances/warnings?days=30', { token });
    check('GET /insurances/warnings', iw.status === 200 && iw.json?.success);

    const ep = await api('GET', '/enterprises/pending?page_size=5', { token });
    check('GET /enterprises/pending', ep.status === 200 && ep.json?.success);

    const pp = await api('GET', '/positions/pending?page_size=5', { token });
    check('GET /positions/pending', pp.status === 200 && pp.json?.success);

    const integ = await api('GET', '/integration/info', { token });
    check('GET /integration/info', integ.status === 200 && integ.json?.success);

    const prof = await api('PUT', '/users/profile', {
      token, body: { real_name: '测试', emergency_name: '张三', emergency_phone: '13800138000', emergency_relation: '父亲' }
    });
    check('PUT /users/profile emergency', prof.status === 200 && prof.json?.success, prof.json?.message);

    console.log('\n结果:', pass, '通过,', fail, '失败');
    process.exit(fail ? 1 : 0);
  } catch (e) {
    console.error('测试异常:', e.message);
    process.exit(1);
  }
})();
