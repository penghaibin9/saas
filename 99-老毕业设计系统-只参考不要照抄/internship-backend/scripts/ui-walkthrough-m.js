/**
 * 全页面浏览器实走测试（移动端 H5 /m）
 * 学生 / 教师 登录 → 采集该角色可见的所有 render('x') 入口 → 逐个导航
 * 捕获：JS 异常 / console.error / HTTP 4xx-5xx
 *
 * 运行：node scripts/ui-walkthrough-m.js   （需后端已启动 + npm run seed:demo）
 */
const { chromium } = require('playwright');

const BASE = process.env.UI_BASE_M || 'http://localhost:3000/m/index.html';
const ROLES = [
  { name: '学生(H5)', u: 'demo_stu1', p: 'demo1234' },
  { name: '教师(H5)', u: 'demo_teacher', p: 'demo1234' },
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dedupe = (a) => [...new Set(a)];

async function run() {
  const browser = await chromium.launch({ headless: true });
  const report = [];

  for (const role of ROLES) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 }, isMobile: true,
      // 给定位 API 一个落在演示企业范围内的坐标，避免打卡页因拒绝定位报错
      geolocation: { latitude: 28.2001, longitude: 112.9001 }, permissions: ['geolocation'],
    });
    const page = await ctx.newPage();
    const bucket = { pageerror: [], console: [], http: [] };
    page.on('pageerror', (e) => bucket.pageerror.push(String(e.message || e)));
    page.on('console', (m) => { if (m.type() === 'error') bucket.console.push(m.text()); });
    page.on('response', (res) => {
      if (res.status() >= 400) {
        const u = res.url().replace(/^https?:\/\/[^/]+/, '');
        bucket.http.push(`${res.status()} ${res.request().method()} ${u}`);
      }
    });

    const rr = { role: role.name, login: 'ok', pages: [], visited: 0 };
    try {
      await page.goto(BASE, { waitUntil: 'networkidle', timeout: 20000 });
      await page.fill('#u', role.u);
      await page.fill('#p', role.p);
      await page.click('#login button');
      await page.waitForSelector('#tabbar a, #tabbar button, .fgrid a', { timeout: 15000 });
      await sleep(1200);
    } catch (e) {
      rr.login = 'FAIL: ' + e.message;
      report.push(rr); await ctx.close(); continue;
    }

    // 从首页采集该角色可见的 render('x') 入口
    const keys = dedupe(await page.$$eval('[onclick]', (els) =>
      els.map((e) => e.getAttribute('onclick'))
        .filter((o) => o && /render\('/.test(o))
        .map((o) => (o.match(/render\('([^']+)'/) || [])[1])
        .filter(Boolean)));

    for (const key of keys) {
      const before = { pe: bucket.pageerror.length, ce: bucket.console.length, ht: bucket.http.length };
      try {
        await page.evaluate((k) => window.render(k), key);
      } catch (e) {
        rr.pages.push({ page: key, navFail: e.message }); continue;
      }
      rr.visited++;
      await sleep(900);
      const pe = bucket.pageerror.slice(before.pe);
      const ce = bucket.console.slice(before.ce);
      const ht = bucket.http.slice(before.ht);
      if (pe.length || ht.length || ce.length) {
        rr.pages.push({ page: key, pageerror: pe, http: dedupe(ht), console: dedupe(ce).slice(0, 5) });
      }
      // 回首页，避免页面间状态串扰
      try { await page.evaluate(() => window.render('home')); await sleep(300); } catch (_) {}
    }
    report.push(rr);
    await ctx.close();
  }
  await browser.close();
  print(report);
}

function print(report) {
  console.log('\n================ 全页面实走报告（移动端 H5）================\n');
  let total = 0, bad = 0, http = 0, js = 0;
  for (const r of report) {
    console.log(`\n【${r.role}】 登录: ${r.login} ｜ 实走页面 ${r.visited} 个`);
    total += r.visited;
    if (r.login !== 'ok') continue;
    if (!r.pages.length) { console.log('  ✅ 全部页面无 JS 异常 / 无 4xx-5xx'); continue; }
    for (const p of r.pages) {
      bad++;
      console.log(`  ⚠ [${p.page}]`);
      if (p.navFail) console.log(`     · 导航失败: ${p.navFail}`);
      (p.pageerror || []).forEach((e) => { js++; console.log(`     · JS异常: ${e}`); });
      (p.http || []).forEach((e) => { http++; console.log(`     · HTTP: ${e}`); });
      (p.console || []).forEach((e) => console.log(`     · console: ${e.slice(0, 160)}`));
    }
  }
  console.log(`\n================ 汇总：实走页面合计 ${total}，问题页 ${bad}，JS异常 ${js}，HTTP错误 ${http} ================`);
}

run().catch((e) => { console.error(e); process.exit(1); });
