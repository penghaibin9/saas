/** 新增改进项接口自检：就业大盘/周报模板/批量批阅/版本历史/批注/双时段打卡 */
const BASE = process.env.API_BASE || 'http://localhost:3000/api';
let pass = 0, fail = 0;
const log = (n, ok, d) => { console.log(`${ok ? '✅' : '❌'} ${n}${d ? ' — ' + d : ''}`); ok ? pass++ : fail++; };
async function api(token, path, method = 'GET', body) {
  const r = await fetch(BASE + path, { method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) }, body: body ? JSON.stringify(body) : undefined });
  let j = null; try { j = await r.json(); } catch (_) {}
  return { status: r.status, j, ok: r.ok && j && j.success };
}
async function login(u, p) { const r = await api(null, '/users/login', 'POST', { username: u, password: p }); return { token: r.j.data.token, user: r.j.data.user }; }
(async () => {
  const admin = await login('demo_admin', 'demo1234');
  const teacher = await login('demo_teacher', 'demo1234');
  const stu = await login('demo_stu1', 'demo1234');

  let r = await api(admin.token, '/benchmark/employment/stats');
  log('#3 就业大盘 stats', r.ok, r.ok ? `落实率=${r.j.data.rate}% 已登记=${r.j.data.filled}/${r.j.data.total}` : r.j && r.j.message);

  r = await api(stu.token, '/intern-logs/template?type=weekly');
  log('#2 周报模板读取', r.ok && r.j.data.template, r.ok ? '模板长度=' + r.j.data.template.length : '');

  r = await api(admin.token, '/intern-logs/template', 'PUT', { type: 'weekly', template: '一、本周\n二、计划' });
  log('#2 周报模板保存(管理员)', r.ok, r.j && r.j.message);

  r = await api(teacher.token, '/intern-logs/batch-review', 'PUT', { ids: [], agree: true });
  log('#2 批量批阅(空校验)', r.status === 400, '应拒绝空选择 → ' + (r.j && r.j.message));

  r = await api(stu.token, '/gd-achievements/versions?doc_type=proposal');
  log('#6 版本历史', r.ok, r.ok ? '版本数=' + r.j.data.list.length : r.j && r.j.message);

  // 双时段打卡：上班(am) + 下班(pm) 各一次
  const am = await api(stu.token, '/checkins', 'POST', { latitude: 28.2, longitude: 112.9, address: '自检上班', slot: 'am' });
  const pm = await api(stu.token, '/checkins', 'POST', { latitude: 28.2, longitude: 112.9, address: '自检下班', slot: 'pm' });
  const amOk = am.ok || /已经打过/.test((am.j && am.j.message) || '');
  const pmOk = pm.ok || /已经打过/.test((pm.j && pm.j.message) || '');
  log('#1 双时段打卡(am/pm 互不冲突)', amOk && pmOk, `am:${(am.j && am.j.message) || am.status} | pm:${(pm.j && pm.j.message) || pm.status}`);

  console.log(`\n== ${pass}/${pass + fail} 通过 ==`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
