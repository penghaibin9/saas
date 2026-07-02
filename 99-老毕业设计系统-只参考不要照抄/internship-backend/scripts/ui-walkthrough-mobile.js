/**
 * 移动端 H5 全页面实走（web/m/index.html）
 * 学生 / 教师登录 → 枚举首页宫格里出现的 render 目标 → 逐个切页
 * 捕获：JS 异常(pageerror) / console.error / HTTP 4xx-5xx
 *
 * 运行：node scripts/ui-walkthrough-mobile.js   （需后端已启动 + npm run seed:demo）
 */
const { chromium } = require('playwright');

const BASE = process.env.M_BASE || 'http://localhost:3000/m/index.html';
const ROLES = [
  { name: '学生', u: 'demo_stu1', p: 'demo1234' },
  { name: '教师', u: 'demo_teacher', p: 'demo1234' },
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dedupe = (a) => [...new Set(a)];

async function run() {
  const browser = await chromium.launch({ headless: true });
  const report = [];

  for (const role of ROLES) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 }, // iPhone 12 尺寸
      isMobile: true, hasTouch: true,
    });
    const page = await ctx.newPage();
    const bucket = { pageerror: [], console: [], http: [] };
    page.on('pageerror', (e) => bucket.pageerror.push(String(e.message || e)));
    page.on('console', (m) => { if (m.type() === 'error') bucket.console.push(m.text()); });
    page.on('response', (res) => {
      const s = res.status();
      if (s >= 400) bucket.http.push(`${s} ${res.request().method()} ${res.url().replace(/^https?:\/\/[^/]+/, '')}`);
    });

    const roleReport = { role: role.name, login: 'ok', visited: 0, pages: [] };
    try {
      await page.goto(BASE, { waitUntil: 'networkidle', timeout: 20000 });
      await page.fill('#u', role.u);
      await page.fill('#p', role.p);
      await page.click('button:has-text("登 录")');
      await sleep(1800); // 首页宫格渲染
    } catch (e) {
      roleReport.login = 'FAIL: ' + e.message;
      report.push(roleReport); await ctx.close(); continue;
    }

    // 枚举首页 DOM 里实际出现的 render('xxx') 目标（即该角色可见的功能）
    const keys = await page.evaluate(() => {
      const set = new Set();
      document.querySelectorAll('[onclick]').forEach((el) => {
        const m = (el.getAttribute('onclick') || '').match(/render\('([a-zA-Z0-9_-]+)'/);
        if (m && m[1] !== 'home') set.add(m[1]);
      });
      return [...set];
    });

    for (const key of keys) {
      roleReport.visited++;
      const before = { pe: bucket.pageerror.length, ce: bucket.console.length, ht: bucket.http.length };
      try {
        await page.evaluate((k) => window.render(k), key);
      } catch (e) {
        roleReport.pages.push({ page: key, navFail: e.message }); continue;
      }
      await sleep(900);
      const pe = bucket.pageerror.slice(before.pe);
      const ce = bucket.console.slice(before.ce);
      const ht = bucket.http.slice(before.ht);
      if (pe.length || ht.length || ce.length) {
        roleReport.pages.push({ page: key, pageerror: pe, http: dedupe(ht), console: dedupe(ce).slice(0, 5) });
      }
      await page.evaluate(() => window.render('home')).catch(() => {});
      await sleep(300);
    }

    report.push(roleReport);
    await ctx.close();
  }

  await browser.close();

  console.log('\n================ 移动端 H5 实走报告 ================\n');
  let total = 0, bad = 0, js = 0, http = 0;
  for (const r of report) {
    console.log(`\n【${r.role}】登录: ${r.login} ｜ 实走功能 ${r.visited} 个`);
    total += r.visited;
    if (r.login !== 'ok') continue;
    if (!r.pages.length) { console.log('  ✅ 全部功能无 JS 异常 / 无 4xx-5xx'); continue; }
    for (const p of r.pages) {
      bad++;
      console.log(`  ⚠ [${p.page}]`);
      if (p.navFail) console.log(`     · 切页失败: ${p.navFail}`);
      (p.pageerror || []).forEach((e) => { js++; console.log(`     · JS异常: ${e}`); });
      (p.http || []).forEach((e) => { http++; console.log(`     · HTTP: ${e}`); });
      (p.console || []).forEach((e) => console.log(`     · console: ${e.slice(0, 160)}`));
    }
  }
  console.log(`\n================ 汇总：实走功能 ${total}，问题页 ${bad}，JS异常 ${js}，HTTP错误 ${http} ================`);
}

run().catch((e) => { console.error(e); process.exit(1); });
