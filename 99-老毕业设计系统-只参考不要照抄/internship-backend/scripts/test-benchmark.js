/**
 * 商用对标 API 冒烟测试
 * node scripts/test-benchmark.js
 */
require('dotenv').config();
const API = process.env.API_BASE || 'http://localhost:3000/api';

async function api(method, path, { token, body } = {}) {
  const headers = {};
  if (token) headers.Authorization = 'Bearer ' + token;
  if (body) headers['Content-Type'] = 'application/json';
  const res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const json = await res.json().catch(() => null);
  return { status: res.status, json };
}

async function login(username, password) {
  const r = await api('POST', '/users/login', { body: { username, password } });
  if (!(r.json && r.json.success)) throw new Error('登录失败: ' + username);
  return r.json.data.token;
}

async function main() {
  const admin = await login('demo_admin', 'demo1234');
  const student = await login('demo_stu1', 'demo1234');
  const teacher = await login('demo_teacher', 'demo1234');

  const checks = [
    ['GET /benchmark/doc-types', () => api('GET', '/benchmark/doc-types', { token: student })],
    ['GET /benchmark/urge-list', () => api('GET', '/benchmark/urge-list', { token: admin })],
    ['GET /benchmark/topic-rounds', () => api('GET', '/benchmark/topic-rounds', { token: admin })],
    ['GET /benchmark/intern-score-config', () => api('GET', '/benchmark/intern-score-config', { token: admin })],
    ['GET /benchmark/defense/mine', () => api('GET', '/benchmark/defense/mine', { token: student })],
    ['GET /benchmark/class-teacher/dashboard', () => api('GET', '/benchmark/class-teacher/dashboard', { token: teacher })],
  ];

  let pass = 0;
  for (const [name, fn] of checks) {
    try {
      const r = await fn();
      const ok = r.json && r.json.success;
      console.log(ok ? '✅' : '❌', name, ok ? '' : (r.json && r.json.message));
      if (ok) pass++;
    } catch (e) {
      console.log('❌', name, e.message);
    }
  }
  console.log(`\n${pass}/${checks.length} 通过`);
  process.exit(pass === checks.length ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(1); });
