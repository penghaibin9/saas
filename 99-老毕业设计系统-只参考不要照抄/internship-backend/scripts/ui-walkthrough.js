/**
 * 全页面浏览器实走测试（PC 管理端）
 * 四角色登录 → 切换业务系统 → 逐个点遍每个菜单
 * 捕获：JS 异常(pageerror) / console.error / HTTP 4xx-5xx 请求
 *
 * 运行：node scripts/ui-walkthrough.js   （需后端已启动 + npm run seed:demo）
 */
const { chromium } = require('playwright');

const BASE = process.env.UI_BASE || 'http://localhost:3000/admin';
const ROLES = [
  { name: '院校管理员', u: 'demo_admin', p: 'demo1234' },
  { name: '指导教师', u: 'demo_teacher', p: 'demo1234' },
  { name: '学生', u: 'demo_stu1', p: 'demo1234' },
  { name: '企业', u: 'demo_ent', p: 'demo1234' },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run() {
  const browser = await chromium.launch({ headless: true });
  const report = [];

  for (const role of ROLES) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();

    const bucket = { pageerror: [], console: [], http: [] };
    page.on('pageerror', (e) => bucket.pageerror.push(String(e.message || e)));
    page.on('console', (m) => { if (m.type() === 'error') bucket.console.push(m.text()); });
    page.on('response', (res) => {
      const s = res.status();
      if (s >= 400) {
        const u = res.url().replace(/^https?:\/\/[^/]+/, '');
        bucket.http.push(`${s} ${res.request().method()} ${u}`);
      }
    });

    const roleReport = { role: role.name, login: 'ok', pages: [], visited: 0 };
    try {
      await page.goto(BASE, { waitUntil: 'networkidle', timeout: 20000 });
      await page.fill('#l-user', role.u);
      await page.fill('#l-pass', role.p);
      await page.click('#l-btn');
      await page.waitForSelector('.nav-item[data-page]', { timeout: 15000 });
      await sleep(1200); // 首屏 dashboard 加载
    } catch (e) {
      roleReport.login = 'FAIL: ' + e.message;
      report.push(roleReport);
      await ctx.close();
      continue;
    }

    // 业务系统切换按钮（岗位实习 / 毕业设计等），无则单系统
    let sysKeys = await page.$$eval('.sys-btn', (els) => els.map((e) => e.textContent.trim()));
    if (!sysKeys.length) sysKeys = ['_single'];

    const visited = new Set();
    for (let si = 0; si < sysKeys.length; si++) {
      if (sysKeys[si] !== '_single') {
        const btns = await page.$$('.sys-btn');
        if (btns[si]) { await btns[si].click(); await sleep(600); }
      }
      const pages = await page.$$eval('.nav-item[data-page]', (els) =>
        els.map((e) => ({ page: e.getAttribute('data-page'), label: e.textContent.trim() })));

      for (const item of pages) {
        const key = sysKeys[si] + '/' + item.page;
        if (visited.has(key)) continue;
        visited.add(key);
        roleReport.visited++;

        const before = { pe: bucket.pageerror.length, ce: bucket.console.length, ht: bucket.http.length };
        try {
          await page.click(`.nav-item[data-page="${item.page}"]`, { timeout: 5000 });
        } catch (e) {
          roleReport.pages.push({ page: item.page, label: item.label, clickFail: e.message });
          continue;
        }
        await sleep(900);

        const pe = bucket.pageerror.slice(before.pe);
        const ce = bucket.console.slice(before.ce);
        const ht = bucket.http.slice(before.ht);
        if (pe.length || ht.length || ce.length) {
          roleReport.pages.push({
            page: item.page, label: item.label,
            pageerror: pe, http: dedupe(ht), console: dedupe(ce).slice(0, 5),
          });
        }
      }
    }
    report.push(roleReport);
    await ctx.close();
  }

  await browser.close();
  printReport(report);
}

function dedupe(arr) { return [...new Set(arr)]; }

function printReport(report) {
  console.log('\n================ 全页面实走报告（PC 管理端）================\n');
  let totalPages = 0, badPages = 0, httpErrs = 0, jsErrs = 0;
  for (const r of report) {
    console.log(`\n【${r.role}】 登录: ${r.login} ｜ 实走菜单 ${r.visited} 个`);
    totalPages += r.visited;
    if (r.login !== 'ok') continue;
    if (!r.pages.length) { console.log('  ✅ 全部菜单无 JS 异常 / 无 4xx-5xx'); continue; }
    for (const p of r.pages) {
      badPages++;
      console.log(`  ⚠ [${p.page}] ${p.label}`);
      if (p.clickFail) console.log(`     · 点击失败: ${p.clickFail}`);
      (p.pageerror || []).forEach((e) => { jsErrs++; console.log(`     · JS异常: ${e}`); });
      (p.http || []).forEach((e) => { httpErrs++; console.log(`     · HTTP: ${e}`); });
      (p.console || []).forEach((e) => console.log(`     · console: ${e.slice(0, 160)}`));
    }
  }
  console.log(`\n================ 汇总：实走菜单合计 ${totalPages}，问题页 ${badPages}，JS异常 ${jsErrs}，HTTP错误 ${httpErrs} ================`);
}

run().catch((e) => { console.error(e); process.exit(1); });
