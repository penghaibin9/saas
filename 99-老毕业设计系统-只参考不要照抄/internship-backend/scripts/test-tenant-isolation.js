/**
 * 多租户隔离验证（需 multi 模式启动 + 已开通 schoola/schoolb）
 * 验证：schoola 建的数据，schoolb 完全看不到（物理库隔离）。
 */
const BASE = process.env.API_BASE || 'http://localhost:3000/api';

async function api(tenant, token, path, method = 'GET', body) {
  const headers = { 'Content-Type': 'application/json' };
  if (tenant) headers['X-Tenant'] = tenant;
  if (token) headers.Authorization = 'Bearer ' + token;
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await res.json(); } catch (_) {}
  return { status: res.status, json, ok: res.ok && json && json.success };
}

async function login(tenant, username, password) {
  const r = await api(tenant, null, '/users/login', 'POST', { username, password });
  if (!r.ok) throw new Error(`[${tenant}] 登录失败：${r.json && r.json.message}`);
  return r.json.data.token;
}

let pass = 0, fail = 0;
function check(name, cond, detail) {
  console.log(`${cond ? '✅' : '❌'} ${name}${detail ? ' — ' + detail : ''}`);
  cond ? pass++ : fail++;
}

(async () => {
  console.log('==== 多租户隔离验证 ====\n');

  const tokenA = await login('schoola', 'admin', 'Admin@123');
  const tokenB = await login('schoolb', 'admin', 'Admin@123');
  check('两校管理员分别登录成功', !!tokenA && !!tokenB);

  // 令牌应携带 tid（解析自登录时的租户）
  const decode = (t) => JSON.parse(Buffer.from(t.split('.')[1], 'base64').toString());
  check('A 令牌 tid=schoola', decode(tokenA).tid === 'schoola', 'tid=' + decode(tokenA).tid);
  check('B 令牌 tid=schoolb', decode(tokenB).tid === 'schoolb', 'tid=' + decode(tokenB).tid);

  // 在 schoola 建一条专属学院
  const marker = 'ONLY_IN_A_' + Date.now();
  const created = await api('schoola', tokenA, '/colleges', 'POST', { name: marker, code: 'OIA' + (Date.now() % 100000) });
  check('schoola 创建专属学院', created.ok, created.json && created.json.message);

  // schoola 自己能看到
  const listA = await api('schoola', tokenA, '/colleges?pageSize=100');
  const inA = JSON.stringify(listA.json && listA.json.data || []).includes(marker);
  check('schoola 能看到自己建的学院', inA);

  // schoolb 用自己令牌看 —— 必须看不到（即便不带 header，tid 也会把它路由到 schoolb 库）
  const listB = await api('schoolb', tokenB, '/colleges?pageSize=100');
  const inB = JSON.stringify(listB.json && listB.json.data || []).includes(marker);
  check('schoolb 看不到 schoola 的学院（物理隔离）', !inB);

  // 跨租户越权：拿 A 的令牌强行带 schoolb 头访问 —— 应被 403 直接拒绝（令牌与学校不匹配）
  const cross = await api('schoolb', tokenA, '/colleges?pageSize=100');
  check('带 A 令牌+schoolb 头：被 403 拒绝', cross.status === 403, 'status=' + cross.status + ' code=' + (cross.json && cross.json.code));

  console.log(`\n==== 结果：通过 ${pass}，失败 ${fail} ====`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('❌', e.message); process.exit(1); });
