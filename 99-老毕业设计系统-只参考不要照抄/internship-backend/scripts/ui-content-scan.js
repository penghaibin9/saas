/**
 * 内容质量扫描：逐角色逐页检查渲染后可见文本里是否出现
 * undefined / [object Object] / NaN / 裸 null —— 典型的数据绑定 bug，演示时最掉价。
 * 运行：node scripts/ui-content-scan.js   （需后端已启动 + npm run seed:demo）
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
const BAD = /undefined|\[object Object\]|\bNaN\b|：\s*null\b|>\s*null\s*</;

async function run() {
  const browser = await chromium.launch({ headless: true });
  const findings = [];
  for (const role of ROLES) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    try {
      await page.goto(BASE, { waitUntil: 'networkidle', timeout: 20000 });
      await page.fill('#l-user', role.u); await page.fill('#l-pass', role.p); await page.click('#l-btn');
      await page.waitForSelector('.nav-item[data-page]', { timeout: 15000 }); await sleep(1000);
    } catch (e) { findings.push({ role: role.name, page: '(登录)', sample: 'FAIL ' + e.message }); await ctx.close(); continue; }

    let sysKeys = await page.$$eval('.sys-btn', (els) => els.map((e) => e.textContent.trim()));
    if (!sysKeys.length) sysKeys = ['_single'];
    const visited = new Set();
    for (let si = 0; si < sysKeys.length; si++) {
      if (sysKeys[si] !== '_single') { const b = await page.$$('.sys-btn'); if (b[si]) { await b[si].click(); await sleep(500); } }
      const pages = await page.$$eval('.nav-item[data-page]', (els) => els.map((e) => ({ page: e.getAttribute('data-page'), label: e.textContent.trim() })));
      for (const it of pages) {
        if (visited.has(it.page)) continue; visited.add(it.page);
        try { await page.click(`.nav-item[data-page="${it.page}"]`, { timeout: 5000 }); } catch { continue; }
        await sleep(800);
        const txt = await page.$eval('.content', (el) => el.innerText).catch(() => '');
        const m = txt.match(BAD);
        if (m) {
          const idx = txt.indexOf(m[0]);
          const sample = txt.slice(Math.max(0, idx - 40), idx + 40).replace(/\s+/g, ' ').trim();
          findings.push({ role: role.name, page: it.page, label: it.label, token: m[0], sample });
        }
      }
    }
    await ctx.close();
  }
  await browser.close();

  console.log('\n================ 内容质量扫描 ================\n');
  if (!findings.length) { console.log('✅ 所有页面未发现 undefined / [object Object] / NaN / 裸 null'); }
  else for (const f of findings) console.log(`⚠ [${f.role}] ${f.label||''}(${f.page}) → 「${f.token}」｜ …${f.sample}…`);
  console.log(`\n================ 共 ${findings.length} 处 ================`);
}
run().catch((e) => { console.error(e); process.exit(1); });
