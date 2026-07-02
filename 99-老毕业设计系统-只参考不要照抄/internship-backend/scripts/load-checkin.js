/**
 * 打卡接口并发测试。
 * 默认 read：并发读取“我的打卡”，不产生数据。
 * write：需 LOAD_ACCOUNTS_FILE 指向 JSON 账号数组，每个账号只提交一次真实打卡。
 */
const fs = require('fs');
const { performance } = require('perf_hooks');
const BASE = (process.env.API_BASE || 'http://localhost:3000/api').replace(/\/$/, '');
const MODE = process.env.LOAD_MODE || 'read';
const TOTAL = Math.max(1, Number(process.env.LOAD_TOTAL || 200));
const CONCURRENCY = Math.max(1, Number(process.env.LOAD_CONCURRENCY || 20));

async function login(username, password) {
  const r = await fetch(BASE + '/users/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
  const j = await r.json();
  if (!r.ok || !j.success) throw new Error(`账号 ${username} 登录失败`);
  return j.data.token;
}

async function main() {
  let accounts;
  if (MODE === 'write') {
    if (!process.env.LOAD_ACCOUNTS_FILE) throw new Error('写入测试必须设置 LOAD_ACCOUNTS_FILE');
    accounts = JSON.parse(fs.readFileSync(process.env.LOAD_ACCOUNTS_FILE, 'utf8'));
    if (!Array.isArray(accounts) || !accounts.length) throw new Error('账号文件必须是非空 JSON 数组');
  } else {
    accounts = [{ username: process.env.TEST_STUDENT_USER || 'demo_stu1', password: process.env.TEST_STUDENT_PASS || 'demo1234' }];
  }
  const tokens = [];
  for (const a of accounts) tokens.push(await login(a.username, a.password));
  const count = MODE === 'write' ? Math.min(TOTAL, accounts.length) : TOTAL;
  let cursor = 0, ok = 0, failed = 0;
  const latencies = [];
  const started = performance.now();
  async function worker() {
    while (true) {
      const i = cursor++;
      if (i >= count) return;
      const token = tokens[i % tokens.length];
      const t = performance.now();
      try {
        const options = { headers: { Authorization: 'Bearer ' + token } };
        let url = BASE + '/checkins/mine';
        if (MODE === 'write') {
          url = BASE + '/checkins'; options.method = 'POST';
          options.headers['Content-Type'] = 'application/json';
          options.body = JSON.stringify({ latitude: accounts[i].latitude, longitude: accounts[i].longitude, address: '并发验收测试', slot: accounts[i].slot || 'day' });
        }
        const r = await fetch(url, options);
        if (!r.ok) throw new Error(String(r.status));
        ok++;
      } catch (_) { failed++; }
      latencies.push(performance.now() - t);
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, count) }, worker));
  latencies.sort((a, b) => a - b);
  const elapsed = (performance.now() - started) / 1000;
  const pct = (p) => Math.round(latencies[Math.min(latencies.length - 1, Math.floor(latencies.length * p))] || 0);
  console.log(JSON.stringify({ mode: MODE, total: count, ok, failed, seconds: Number(elapsed.toFixed(2)), requestsPerSecond: Number((count / elapsed).toFixed(1)), p50Ms: pct(.5), p95Ms: pct(.95), p99Ms: pct(.99) }, null, 2));
  if (failed) process.exitCode = 1;
}

main().catch((e) => { console.error('❌', e.message); process.exit(1); });
