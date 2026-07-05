#!/usr/bin/env node
// ==========================================================
//  冒烟自检：检查 PC 前端 / 小程序 H5 / 后端 是否能访问
//  用法（在项目根目录执行）：node scripts/check/smoke-check.mjs
//  只读检查，不改任何东西。服务没启动也不会报崩。
// ==========================================================

const TIMEOUT_MS = 3000;

// 页面标题特征，用来区分同为 vite 的两个前端
const PC_TITLE_HINT = '职校学生全生命周期平台';      // frontend/index.html 的 <title>
const MINIAPP_TITLE_HINT = '高校学生全生命周期管理平台'; // miniapp/index.html 的 <title>

async function tryFetch(url) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS), redirect: 'follow' });
    let text = '';
    try { text = await res.text(); } catch { /* 忽略 */ }
    const m = text.match(/<title>([^<]*)<\/title>/i);
    return { ok: res.status < 500, status: res.status, title: m ? m[1].trim() : '' };
  } catch {
    return { ok: false, status: 0, title: '' };
  }
}

// 在候选端口里找某个前端；先按标题精确匹配，找不到再退回"有响应即算"
async function findFrontend(name, ports, titleHint, results) {
  const responses = [];
  for (const port of ports) {
    const url = `http://localhost:${port}/`;
    const r = results[port] ?? (results[port] = await tryFetch(url));
    if (r.ok) responses.push({ port, url, ...r });
  }
  // 1) 标题能对上的优先
  const exact = responses.find((r) => r.title.includes(titleHint));
  if (exact) return { found: true, exact: true, ...exact };
  // 2) 标题对不上但端口有服务
  if (responses.length > 0) return { found: true, exact: false, ...responses[0] };
  return { found: false };
}

function line(tag, color, msg) {
  const colors = { green: '\x1b[32m', yellow: '\x1b[33m', red: '\x1b[31m', reset: '\x1b[0m' };
  console.log(`${colors[color]}${tag}${colors.reset} ${msg}`);
}

console.log('');
console.log('=============== 冒烟自检 smoke-check ===============');
console.log('（提示：服务刚启动时要等编译完成，太快跑自检会误报）');
console.log('');

const results = {}; // 端口 → fetch 结果缓存，避免重复请求
let okCount = 0;

// ---------- 1. PC 前端：优先 5173，再试 5174、5188 ----------
{
  const r = await findFrontend('PC 前端', [5173, 5174, 5188], PC_TITLE_HINT, results);
  if (r.found && r.exact) {
    okCount++;
    line('[OK]', 'green', `PC 前端    可访问：${r.url}（页面标题：${r.title}）`);
  } else if (r.found) {
    line('[?] ', 'yellow', `PC 前端    ${r.url} 有服务在响应，但页面标题是「${r.title}」，可能是别的服务占了端口`);
  } else {
    line('[--]', 'yellow', 'PC 前端    未启动（5173/5174/5188 都不通）→ 运行 scripts\\dev\\start-pc.ps1');
  }
}

// ---------- 2. 小程序 H5：优先 5188，再试 5173、5174 ----------
{
  const r = await findFrontend('小程序 H5', [5188, 5173, 5174], MINIAPP_TITLE_HINT, results);
  if (r.found && r.exact) {
    okCount++;
    line('[OK]', 'green', `小程序 H5  可访问：${r.url}（页面标题：${r.title}）`);
  } else if (r.found) {
    line('[?] ', 'yellow', `小程序 H5  ${r.url} 有服务在响应，但页面标题是「${r.title}」，可能不是小程序`);
  } else {
    line('[--]', 'yellow', '小程序 H5  未启动（5188/5173/5174 都不通）→ 运行 scripts\\dev\\start-miniapp.ps1');
  }
}

// ---------- 3. 后端：8000/health、8000/docs（规范预留），以及 3000/health（当前 Express 默认） ----------
{
  const candidates = [
    'http://localhost:8000/health',
    'http://localhost:8000/docs',
    'http://localhost:3000/health',
    'http://localhost:3000/',
  ];
  let hit = null;
  for (const url of candidates) {
    const r = await tryFetch(url);
    if (r.ok) { hit = { url, ...r }; break; }
  }
  if (hit) {
    okCount++;
    line('[OK]', 'green', `后端 API   可访问：${hit.url}（HTTP ${hit.status}）`);
  } else {
    line('[--]', 'yellow', '后端 API   未启动/未创建（8000 和 3000 都不通）。目前后端只是底座，没有入口，属正常，可忽略。');
  }
}

// ---------- 汇总 ----------
console.log('');
console.log(`汇总：${okCount}/3 个服务在线。`);
if (okCount === 0) {
  console.log('一个都没在跑。想启动全部：powershell -ExecutionPolicy Bypass -File scripts\\dev\\start-all.ps1');
}
console.log('====================================================');
console.log('');
process.exit(0); // 自检只报告，不报崩
