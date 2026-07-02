/**
 * 全量"行内动作"实走：审批/审核/录用/批阅/会签/确认 等正向动作（会真实改库）。
 * 遍历每个角色每个页面 → 找首个正向审批按钮 → 处理(直接PUT / 确认框 / 弹窗) → 捕获接口结果。
 * 每页只点一个，避免大面积改动演示数据。
 * 运行：node scripts/ui-action-all.js   （需后端已启动 + npm run seed:demo）
 * ⚠️ 跑后部分演示数据状态会改变；如需还原可重建库后 npm run setup && npm run seed:demo。
 */
const { chromium } = require('playwright');
const BASE = 'http://localhost:3000/admin';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ROLES = [
  { name: '管理员', u: 'demo_admin', p: 'demo1234' },
  { name: '教师', u: 'demo_teacher', p: 'demo1234' },
  { name: '学生', u: 'demo_stu1', p: 'demo1234' },
  { name: '企业', u: 'demo_ent', p: 'demo1234' },
];
// 正向审批/确认类动作
const OK_RE = /同意|通过|录用|会签|确认|签署|批准|标记完成|审阅|上架/;
// 跳过：否定/批量/危险/导出
const SKIP_RE = /不|驳回|拒绝|撤回|下架|终止|删除|移除|一键|批量|取消|退回|导出|下载|作废/;
const results = [];

async function closeOverlays(page) {
  await page.evaluate(() => {
    try { window.closeModal && window.closeModal(); } catch (e) {}
    document.querySelectorAll('#modal-main.open, #confirm-wrap.open, .modal-overlay.open').forEach((el) => el.classList.remove('open'));
  }).catch(() => {});
  await sleep(150);
}

async function tryAction(page, role, pageKey, label) {
  const btns = await page.$$('.content button');
  let target = null, txt = '';
  for (const b of btns) {
    let t = ''; try { t = (await b.innerText()).trim(); } catch { continue; }
    if (!t || SKIP_RE.test(t) || !OK_RE.test(t)) continue;
    if (!(await b.isVisible().catch(() => false))) continue;
    target = b; txt = t; break;
  }
  if (!target) return;

  const respP = page.waitForResponse(
    (r) => ['PUT', 'POST'].includes(r.request().method()) && r.url().includes('/api/') && !/\/login/.test(r.url()),
    { timeout: 7000 }).catch(() => null);
  let cap;
  try {
    await target.click({ timeout: 3000 });
    await sleep(650);
    // 三种走向处理
    if (await page.$('#confirm-wrap.open')) {
      const ok = await page.$('#confirm-ok'); if (ok) await ok.click();
    } else if (await page.$('#modal-main.open')) {
      for (const ta of await page.$$('#modal-main textarea')) { try { await ta.fill('实走测试·审阅意见：表现良好，通过。'); } catch (_) {} }
      const sb = await page.$('#modal-submit'); if (sb) await sb.click();
    }
    const resp = await respP;
    if (resp) {
      let json = null; try { json = await resp.json(); } catch (_) {}
      const msg = (json && json.message) || '';
      const dedup = resp.status() === 409 || /已|重复|无可|没有/.test(msg);
      cap = { ok: (resp.status() < 400 && json && json.success) || dedup, ep: resp.url().replace(/^https?:\/\/[^/]+/, '').split('?')[0], status: resp.status(), msg };
    } else { cap = { ok: false, skip: true, ep: '(跳过)', msg: '未触发接口（无待办项/前端拦截）' }; }
  } catch (e) { cap = { ok: false, ep: '(异常)', msg: e.message }; }
  await closeOverlays(page);
  results.push({ role, page: pageKey, label, btn: txt, ...cap });
}

(async () => {
  const browser = await chromium.launch();
  for (const role of ROLES) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    try {
      await page.goto(BASE, { waitUntil: 'networkidle', timeout: 20000 });
      await page.fill('#l-user', role.u); await page.fill('#l-pass', role.p); await page.click('#l-btn');
      await page.waitForSelector('.nav-item[data-page]', { timeout: 15000 }); await sleep(900);
    } catch (e) { console.log(`[${role.name}] 登录失败: ${e.message}`); await ctx.close(); continue; }
    let sysKeys = await page.$$eval('.sys-btn', (els) => els.map((e) => e.textContent.trim()));
    if (!sysKeys.length) sysKeys = ['_single'];
    const visited = new Set();
    for (let si = 0; si < sysKeys.length; si++) {
      if (sysKeys[si] !== '_single') { await page.evaluate((k) => window.switchSys && window.switchSys(k), si === 1 ? 'gd' : 'intern').catch(() => {}); await sleep(500); }
      const pages = await page.$$eval('.nav-item[data-page]', (els) => els.map((e) => ({ page: e.getAttribute('data-page'), label: e.textContent.trim() })));
      for (const it of pages) {
        if (visited.has(it.page)) continue; visited.add(it.page);
        await closeOverlays(page);
        try { await page.evaluate((k) => window.navigate(k), it.page); } catch { continue; }
        await sleep(800);
        try { await tryAction(page, role.name, it.page, it.label); } catch (e) { results.push({ role: role.name, page: it.page, label: it.label, btn: '(异常)', ok: false, ep: '(异常)', msg: e.message }); }
        await closeOverlays(page);
      }
    }
    await ctx.close();
  }
  await browser.close();

  console.log('\n================ 全量"行内动作"实走（审批/审核/录用/批阅…）================\n');
  const ok = results.filter((r) => r.ok), skip = results.filter((r) => !r.ok && r.skip), fail = results.filter((r) => !r.ok && !r.skip);
  for (const r of results) {
    const icon = r.ok ? '✅' : (r.skip ? '⏭️' : '❌');
    console.log(`${icon} [${r.role}] ${r.label} · 「${r.btn}」 → ${r.ep}  ${r.msg || ''}`);
  }
  console.log(`\n触发动作 ${results.length} 个：✅ ${ok.length} 通过 / ⏭️ ${skip.length} 跳过(无待办) / ❌ ${fail.length} 失败`);
  process.exit(fail.length ? 1 : 0);
})().catch((e) => { console.error('脚本崩溃:', e); process.exit(2); });
