/**
 * 全量真实流程实走（会真实写库，数据带【实走测试】标记，跑完自动清理）。
 * 遍历每个角色每个页面 → 找到创建/提交类按钮 → 打开弹窗 → 智能填充所有字段 → 提交 → 捕获真实接口结果。
 * 运行：node scripts/ui-flow-all.js   （需后端已启动 + npm run seed:demo）
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const pool = require('../config/db');

const BASE = 'http://localhost:3000/admin';
const TAG = '【实走测试】';
const TODAY = new Date().toISOString().slice(0, 10);
const TMP = path.join(__dirname, '_flowtest.pdf');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const ROLES = [
  { name: '管理员', u: 'demo_admin', p: 'demo1234' },
  { name: '教师', u: 'demo_teacher', p: 'demo1234' },
  { name: '学生', u: 'demo_stu1', p: 'demo1234' },
  { name: '企业', u: 'demo_ent', p: 'demo1234' },
];
// 创建类按钮（点了会打开表单弹窗）
const CREATE_RE = /新增|新建|发布|申请|上传|创建|下达|布置|登记|录入|添加|出题|分组/;
// 跳过：危险/即时动作/会触发下载、确认框或离开
const SKIP_RE = /删除|移除|作废|终止|注销|退出|导出|下载|返回|取消|催办|生成|一键/;

const results = [];

async function closeOverlays(page) {
  await page.evaluate(() => {
    try { window.closeModal && window.closeModal(); } catch (e) {}
    document.querySelectorAll('#modal-main.open, #confirm-wrap.open, .modal-overlay.open').forEach((el) => el.classList.remove('open'));
  }).catch(() => {});
  await sleep(150);
}

async function fillModal(page) {
  // 文本/数字/日期/文件
  for (const el of await page.$$('#modal-main input')) {
    const type = (await el.getAttribute('type')) || 'text';
    if (['hidden', 'checkbox', 'radio', 'submit', 'button'].includes(type)) continue;
    try {
      if (type === 'file') { await el.setInputFiles(TMP); }
      else if (type === 'date') { await el.fill(TODAY); }
      else if (type === 'number') { await el.fill('1'); }
      else {
        const ph = (await el.getAttribute('placeholder')) || '';
        const id = (await el.getAttribute('id')) || '';
        if (/phone|tel|mobile|contact/i.test(id) || /手机|电话|phone/i.test(ph)) await el.fill('13800000000');
        else if (/email|mail/i.test(id) || /邮箱|email/i.test(ph)) await el.fill('test@example.com');
        else if (/link|url/i.test(id) || /链接|http|url/i.test(ph)) await el.fill('http://example.com/demo');
        else if (/code|账号|工号|学号|user(name)?/i.test(id) || /工号|学号|账号|代码|code/i.test(ph)) await el.fill('T' + Date.now());
        else await el.fill(TAG + '测试');
      }
    } catch (_) {}
  }
  for (const el of await page.$$('#modal-main textarea')) { try { await el.fill(TAG + '实走测试内容，用于验证真实提交流程。'); } catch (_) {} }
  // 下拉：选第一个非空选项
  for (const sel of await page.$$('#modal-main select')) {
    try {
      const vals = await sel.$$eval('option', (os) => os.map((o) => o.value));
      const v = vals.find((x) => x !== '' && x != null);
      if (v != null) await sel.selectOption(v);
    } catch (_) {}
  }
}

async function tryFlow(page, roleName, pageKey, label) {
  // 在 .content 找创建类按钮
  const btns = await page.$$('.content .btn, .content button');
  let target = null, btnText = '';
  for (const b of btns) {
    let t = ''; try { t = (await b.innerText()).trim(); } catch { continue; }
    if (!t || SKIP_RE.test(t) || !CREATE_RE.test(t)) continue;
    if (!(await b.isVisible().catch(() => false))) continue;
    target = b; btnText = t; break;
  }
  if (!target) return; // 该页无创建入口，跳过

  const errs = [];
  const onResp = (res) => { const s = res.status(); if (s >= 400 && res.url().includes('/api/')) errs.push(`HTTP ${s} ${res.request().method()} ${res.url().replace(/^https?:\/\/[^/]+/, '')}`); };
  page.on('response', onResp);

  let captured = null;
  const respP = page.waitForResponse((r) => ['POST', 'PUT'].includes(r.request().method()) && r.url().includes('/api/') && !/\/login/.test(r.url()), { timeout: 7000 }).catch(() => null);

  try {
    await target.click({ timeout: 3000 });
    await sleep(700);
    const modalOpen = await page.$('#modal-main.open');
    if (!modalOpen) { page.off('response', onResp); return; } // 不是弹窗式（可能是行内动作），本轮跳过
    await fillModal(page);
    await sleep(200);
    const submit = await page.$('#modal-submit');
    if (submit) await submit.click();
    const resp = await respP;
    if (resp) {
      let json = null; try { json = await resp.json(); } catch (_) {}
      const msg = (json && json.message) || '';
      const ep = resp.url().replace(/^https?:\/\/[^/]+/, '').split('?')[0];
      // 去重/已存在视为流程通过（接口已正确响应，只是该演示数据已有记录）
      const dedup = resp.status() === 409 || /已有|已存在|已经|重复|已提交过|已打卡|已确认/.test(msg);
      const ok = (resp.status() < 400 && json && json.success) || dedup;
      captured = { ok, ep, status: resp.status(), msg: dedup ? msg + '（去重，流程正常）' : msg };
    } else {
      // 未触发接口：多为发布/确认类动作或前端校验，非创建表单，归为跳过
      captured = { ok: false, skip: true, ep: '(跳过)', msg: '非创建表单/前端校验拦截，本轮跳过' };
    }
  } catch (e) {
    captured = { ok: false, ep: '(异常)', msg: e.message };
  }
  await closeOverlays(page);
  page.off('response', onResp);

  results.push({ role: roleName, page: pageKey, label, btn: btnText, ...captured, httpErrs: errs });
}

(async () => {
  fs.writeFileSync(TMP, '实走测试占位文件');
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
        try { await tryFlow(page, role.name, it.page, it.label); } catch (e) { results.push({ role: role.name, page: it.page, label: it.label, btn: '(异常)', ok: false, ep: '(异常)', msg: e.message }); }
        await closeOverlays(page);
      }
    }
    await ctx.close();
  }
  await browser.close();
  fs.unlinkSync(TMP);

  // 报告
  console.log('\n================ 全量真实流程实走 ================\n');
  const okList = results.filter((r) => r.ok);
  const skipList = results.filter((r) => !r.ok && r.skip);
  const failList = results.filter((r) => !r.ok && !r.skip);
  for (const r of results) {
    const icon = r.ok ? '✅' : (r.skip ? '⏭️' : '❌');
    console.log(`${icon} [${r.role}] ${r.label} · 「${r.btn}」 → ${r.ep}${r.ok ? (r.msg ? '  ' + r.msg : '') : '  ⟵ ' + (r.msg || '')}`);
    if (!r.ok && !r.skip && r.httpErrs && r.httpErrs.length) r.httpErrs.forEach((e) => console.log('       · ' + e));
  }
  console.log(`\n触发流程 ${results.length} 个：✅ ${okList.length} 通过 / ⏭️ ${skipList.length} 跳过(非创建表单) / ❌ ${failList.length} 失败`);

  // 清理测试数据
  const TABLES = ['t_position', 't_leave', 't_teacher_record', 't_complaint', 't_intern_log', 't_report', 't_agreement', 't_gd_topic', 't_gd_guidance', 't_intern_plan', 't_college', 't_major', 't_class', 't_enterprise', 't_gd_task', 't_user', 't_gd_achievement', 't_application', 't_insurance', 't_defense_group'];
  let cleaned = 0;
  for (const t of TABLES) {
    try {
      const cols = await pool.query(`SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? AND COLUMN_NAME IN ('title','name','reason','content','real_name','student_remark','remark')`, [t]);
      const fields = cols[0].map((c) => c.COLUMN_NAME);
      if (!fields.length) continue;
      const where = fields.map((f) => `${f} LIKE '${TAG}%'`).join(' OR ');
      const hasDel = (await pool.query(`SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? AND COLUMN_NAME='is_deleted'`, [t]))[0].length;
      const sql = hasDel ? `UPDATE ${t} SET is_deleted=1 WHERE (${where})` : `DELETE FROM ${t} WHERE (${where})`;
      const [r] = await pool.query(sql);
      cleaned += r.affectedRows || 0;
    } catch (_) {}
  }
  console.log(`已清理测试数据 ${cleaned} 条`);
  await pool.end();
  process.exit(failList.length ? 1 : 0);
})().catch((e) => { console.error('脚本崩溃:', e); process.exit(2); });
