/**
 * 交互级实走（PC 管理端）：在每个页面点开"安全交互"——新增/编辑/查看/详情/筛选/审核(打开弹窗)，
 * 验证弹窗打开 + 详情接口加载是否报错。只点开、不提交，点完即关弹窗，不污染演示数据。
 *
 * 运行：node scripts/ui-interaction.js   （需后端已启动 + npm run seed:demo）
 */
const { chromium } = require('playwright');

const BASE = process.env.UI_BASE || 'http://localhost:3000/admin';
const ROLES = [
  { name: '院校管理员', u: 'demo_admin', p: 'demo1234' },
  { name: '指导教师', u: 'demo_teacher', p: 'demo1234' },
  { name: '学生', u: 'demo_stu1', p: 'demo1234' },
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dedupe = (a) => [...new Set(a)];

// 可安全点开（多为打开弹窗/筛选）
const OPEN_RE = /新增|添加|创建|新建|编辑|查看|详情|明细|筛选|批阅|审阅|审核|处理|指派|分配|评分|登记|催办预览/;
// 立即生效/写库/下载 的动作，跳过，避免污染数据或触发下载
const SKIP_RE = /删除|移除|作废|终止|注销|退出|登出|通过|同意|拒绝|驳回|确认|保存|提交|发送|发布|录用|启用|禁用|重置|导出|下载|清除|全部已读|生成|同步|一键/;

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
      if (s >= 400) bucket.http.push(`${s} ${res.request().method()} ${res.url().replace(/^https?:\/\/[^/]+/, '')}`);
    });

    const roleReport = { role: role.name, login: 'ok', clicks: 0, pagesTested: 0, issues: [] };
    try {
      await page.goto(BASE, { waitUntil: 'networkidle', timeout: 20000 });
      await page.fill('#l-user', role.u);
      await page.fill('#l-pass', role.p);
      await page.click('#l-btn');
      await page.waitForSelector('.nav-item[data-page]', { timeout: 15000 });
      await sleep(1000);
    } catch (e) {
      roleReport.login = 'FAIL: ' + e.message;
      report.push(roleReport); await ctx.close(); continue;
    }

    let sysKeys = await page.$$eval('.sys-btn', (els) => els.map((e) => e.textContent.trim()));
    if (!sysKeys.length) sysKeys = ['_single'];

    const visited = new Set();
    for (let si = 0; si < sysKeys.length; si++) {
      if (sysKeys[si] !== '_single') {
        const btns = await page.$$('.sys-btn');
        if (btns[si]) { await btns[si].click(); await sleep(500); }
      }
      const pages = await page.$$eval('.nav-item[data-page]', (els) =>
        els.map((e) => ({ page: e.getAttribute('data-page'), label: e.textContent.trim() })));

      for (const item of pages) {
        if (visited.has(item.page)) continue;
        visited.add(item.page);
        try { await page.click(`.nav-item[data-page="${item.page}"]`, { timeout: 5000 }); } catch { continue; }
        await sleep(800);
        roleReport.pagesTested++;

        // 收集 .content 内可见、文本符合白名单且不在黑名单的按钮
        const handles = await page.$$('.content .btn, .content button');
        const targets = [];
        for (const h of handles) {
          let txt = '';
          try { txt = (await h.innerText()).trim(); } catch { continue; }
          if (!txt) continue;
          if (SKIP_RE.test(txt)) continue;
          if (!OPEN_RE.test(txt)) continue;
          const vis = await h.isVisible().catch(() => false);
          if (vis) targets.push({ h, txt });
          if (targets.length >= 5) break; // 每页最多点 5 个，控制耗时
        }

        for (const t of targets) {
          const before = { pe: bucket.pageerror.length, ce: bucket.console.length, ht: bucket.http.length };
          try {
            await t.h.click({ timeout: 3000 });
          } catch (e) { continue; }
          await sleep(700);
          const pe = bucket.pageerror.slice(before.pe);
          const ce = bucket.console.slice(before.ce);
          const ht = bucket.http.slice(before.ht);
          roleReport.clicks++;
          if (pe.length || ht.length || ce.length) {
            roleReport.issues.push({ page: item.page, label: item.label, btn: t.txt, pageerror: pe, http: dedupe(ht), console: dedupe(ce).slice(0, 3) });
          }
          // 关弹窗，回到列表
          await page.evaluate(() => { try { window.closeModal && window.closeModal(); } catch (e) {} });
          await page.keyboard.press('Escape').catch(() => {});
          await sleep(300);
        }
      }
    }
    report.push(roleReport);
    await ctx.close();
  }

  await browser.close();

  console.log('\n================ 交互级实走报告（PC 管理端）================\n');
  let totalClicks = 0, totalIssues = 0, js = 0, http = 0;
  for (const r of report) {
    console.log(`\n【${r.role}】登录: ${r.login} ｜ 实走页面 ${r.pagesTested} ｜ 点开交互 ${r.clicks} 次`);
    totalClicks += r.clicks;
    if (r.login !== 'ok') continue;
    if (!r.issues.length) { console.log('  ✅ 全部交互无 JS 异常 / 无 4xx-5xx'); continue; }
    for (const is of r.issues) {
      totalIssues++;
      console.log(`  ⚠ [${is.page}] ${is.label} → 按钮「${is.btn}」`);
      (is.pageerror || []).forEach((e) => { js++; console.log(`     · JS异常: ${e}`); });
      (is.http || []).forEach((e) => { http++; console.log(`     · HTTP: ${e}`); });
      (is.console || []).forEach((e) => console.log(`     · console: ${e.slice(0, 160)}`));
    }
  }
  console.log(`\n================ 汇总：点开交互 ${totalClicks} 次，问题 ${totalIssues}，JS异常 ${js}，HTTP错误 ${http} ================`);
}

run().catch((e) => { console.error(e); process.exit(1); });
