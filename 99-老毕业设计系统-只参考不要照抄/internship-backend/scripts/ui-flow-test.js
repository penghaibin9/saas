/**
 * 交互级·真实流程实走（会真实写库，使用【实走测试】标记数据）。
 * 驱动真实前端完成"提交"动作，验证关键业务流是否真的能跑通；有报错即暴露。
 * 运行：node scripts/ui-flow-test.js   （需后端已启动 + npm run seed:demo）
 */
const { chromium } = require('playwright');
const BASE = 'http://localhost:3000/admin';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const TAG = '【实走测试】';

const results = [];
function rec(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? '✅' : '❌'} ${name}${detail ? ' — ' + detail : ''}`);
}

async function login(page, u, p) {
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 20000 });
  await page.fill('#l-user', u); await page.fill('#l-pass', p); await page.click('#l-btn');
  await page.waitForSelector('.nav-item[data-page]', { timeout: 15000 });
  await sleep(900);
}
async function gotoPage(page, key) {
  await page.evaluate((k) => window.navigate(k), key);
  await sleep(900);
}
function attachErrors(page, bucket) {
  page.on('pageerror', (e) => bucket.push('JS异常: ' + (e.message || e)));
  page.on('response', (res) => {
    const s = res.status();
    if (s >= 400 && res.url().includes('/api/')) bucket.push(`HTTP ${s} ${res.request().method()} ${res.url().replace(/^https?:\/\/[^/]+/, '')}`);
  });
}
// 提交弹窗并捕获目标接口响应
async function submitAndCapture(page, urlPart, methods = ['POST', 'PUT']) {
  const respP = page.waitForResponse(
    (r) => r.url().includes(urlPart) && methods.includes(r.request().method()),
    { timeout: 8000 }
  ).catch(() => null);
  await page.click('#modal-submit');
  const resp = await respP;
  if (!resp) return { ok: false, detail: '未捕获到接口响应（可能前端校验拦截/接口未触发）' };
  let json = null; try { json = await resp.json(); } catch (_) {}
  return { ok: resp.status() < 400 && json && json.success, status: resp.status(), msg: json && json.message };
}

(async () => {
  const browser = await chromium.launch();

  /* ───── 流程1：企业端发布实习岗位 ───── */
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage(); const errs = []; attachErrors(page, errs);
    try {
      await login(page, 'demo_ent', 'demo1234');
      await gotoPage(page, 'entpositions');
      await page.click('button:has-text("发布岗位")'); await sleep(600);
      await page.waitForSelector('#ep-title', { timeout: 5000 });
      await page.fill('#ep-title', TAG + 'Java开发实习生');
      await page.fill('#ep-loc', '长沙市岳麓区麓谷');
      await page.fill('#ep-desc', '参与真实项目开发，导师带教，定期汇报进展。');
      const r = await submitAndCapture(page, '/enterprise-portal/positions');
      rec('企业端·发布岗位', r.ok, r.ok ? '提交成功' : (r.detail || `status=${r.status} ${r.msg || ''}`));
    } catch (e) { rec('企业端·发布岗位', false, '流程异常: ' + e.message); }
    if (errs.length) errs.forEach((x) => console.log('     · ' + x));
    await ctx.close();
  }

  /* ───── 流程2：学生提交请假 ───── */
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage(); const errs = []; attachErrors(page, errs);
    try {
      await login(page, 'demo_stu1', 'demo1234');
      await gotoPage(page, 'leavesadmin');
      await page.click('button:has-text("申请请假")');
      await page.waitForSelector('#lv-reason', { timeout: 5000 });
      await page.fill('#lv-reason', TAG + '家中有事，需请假处理。'); // 日期默认今天
      const r = await submitAndCapture(page, '/leaves');
      rec('学生·提交请假', r.ok, r.ok ? '提交成功' : (r.detail || `status=${r.status} ${r.msg || ''}`));
    } catch (e) { rec('学生·提交请假', false, '流程异常: ' + e.message); }
    if (errs.length) errs.forEach((x) => console.log('     · ' + x));
    await ctx.close();
  }

  /* ───── 流程3：教师新增巡访记录 ───── */
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage(); const errs = []; attachErrors(page, errs);
    try {
      await login(page, 'demo_teacher', 'demo1234');
      await gotoPage(page, 'visits');
      await page.click('button:has-text("新增巡访")');
      await page.waitForSelector('#vs-title', { timeout: 5000 });
      await page.fill('#vs-title', TAG + '走访演示企业实习学生');
      await page.fill('#vs-status', '学生按时在岗，工作态度积极，无异常。');
      const r = await submitAndCapture(page, '/teacher-records');
      rec('教师·新增巡访', r.ok, r.ok ? '提交成功' : (r.detail || `status=${r.status} ${r.msg || ''}`));
    } catch (e) { rec('教师·新增巡访', false, '流程异常: ' + e.message); }
    if (errs.length) errs.forEach((x) => console.log('     · ' + x));
    await ctx.close();
  }

  await browser.close();
  const ok = results.filter((r) => r.ok).length;
  console.log(`\n================ 真实流程：${ok}/${results.length} 通过 ================`);
  process.exit(ok === results.length ? 0 : 1);
})().catch((e) => { console.error('脚本崩溃:', e); process.exit(2); });
