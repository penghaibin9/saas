#!/usr/bin/env node

import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import process from 'node:process'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { normalizeManifestPart } from './manifest-normalizer.mjs'

const TOOL_DIR = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(TOOL_DIR, '..')
const args = process.argv.slice(2)
const concurrency = Math.min(2, Math.max(1, Number(readArg('--concurrency') || 2)))
const timeoutMs = Math.max(5000, Number(readArg('--timeout-ms') || 25000))
const virtualTimeMs = Math.max(1000, Number(readArg('--virtual-time-ms') || 4500))
const retries = Math.max(0, Number(readArg('--retries') || 3))
const smokeCount = Math.max(0, Number(readArg('--smoke') || 0))
const screenshots = args.includes('--screenshots')
const reportRoot = path.resolve(readArg('--report-dir') || path.join(os.tmpdir(), 'teacher-pc-v2-freeze', stamp()))
const viewportList = parseViewports(readArg('--viewports') || '1280x900,1440x1000,1920x1080')

function readArg(name) {
  const inline = args.find((arg) => arg.startsWith(`${name}=`))
  if (inline) return inline.slice(name.length + 1)
  const index = args.indexOf(name)
  return index >= 0 ? args[index + 1] : ''
}

function stamp() {
  return new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').replace('Z', '')
}

function parseViewports(raw) {
  const values = raw.split(',').map((item) => item.trim()).filter(Boolean)
  const parsed = values.map((value) => {
    const match = value.match(/^(\d+)x(\d+)$/i)
    if (!match) throw new Error(`无效分辨率：${value}`)
    return { label: value, width: Number(match[1]), height: Number(match[2]) }
  })
  if (!parsed.length) throw new Error('至少需要一个分辨率')
  return parsed
}

function safeJson(abs) {
  return JSON.parse(fs.readFileSync(abs, 'utf8'))
}

function collectHtml() {
  const manifest = safeJson(path.join(ROOT, 'prototype-manifest.json'))
  const entries = []
  for (const partRef of manifest.aggregation.parts || []) {
    const part = safeJson(path.resolve(ROOT, partRef))
    const normalized = normalizeManifestPart(part)
    for (const row of normalized.entries) entries.push(row)
  }
  const unique = [...new Set(entries.map((entry) => entry.html))].sort()
  const expected = manifest?.coverage?.uniqueHtmlFiles
  if (typeof expected === 'number' && expected !== unique.length) {
    throw new Error(`Manifest 声明 ${expected} 个 HTML，但聚合得到 ${unique.length} 个；先运行一致性检查并修复`)
  }
  return smokeCount ? unique.slice(0, smokeCount) : unique
}

function findChrome() {
  const explicit = process.env.CHROME_PATH || readArg('--chrome')
  const candidates = [
    explicit,
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Google', 'Chrome', 'Application', 'chrome.exe')
  ].filter(Boolean)
  for (const candidate of candidates) {
    if (path.isAbsolute(candidate) && fs.existsSync(candidate)) return candidate
  }
  return explicit || (process.platform === 'win32' ? 'chrome.exe' : 'google-chrome')
}

function mimeType(abs) {
  const ext = path.extname(abs).toLowerCase()
  return ({
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon'
  })[ext] || 'application/octet-stream'
}

const BOOTSTRAP = String.raw`<script id="__freeze_bootstrap__">
(() => {
  const state = window.__teacherPcFreeze = {
    consoleErrors: [], consoleWarnings: [], runtimeErrors: [], resourceErrors: [], promiseErrors: []
  };
  const normalize = (value) => {
    try {
      if (value instanceof Error) return value.stack || value.message;
      if (typeof value === 'string') return value;
      return JSON.stringify(value);
    } catch (_) { return String(value); }
  };
  const originalError = console.error.bind(console);
  const originalWarn = console.warn.bind(console);
  console.error = (...items) => { state.consoleErrors.push(items.map(normalize).join(' ')); originalError(...items); };
  console.warn = (...items) => { state.consoleWarnings.push(items.map(normalize).join(' ')); originalWarn(...items); };
  window.addEventListener('error', (event) => {
    const target = event.target;
    if (target && target !== window) {
      state.resourceErrors.push({ tag: target.tagName || '', src: target.currentSrc || target.src || target.href || '' });
      return;
    }
    state.runtimeErrors.push({ message: event.message || 'script error', source: event.filename || '', line: event.lineno || 0, column: event.colno || 0 });
  }, true);
  window.addEventListener('unhandledrejection', (event) => {
    state.promiseErrors.push(normalize(event.reason));
  });
})();
</script>`

const PROBE = String.raw`<script id="__freeze_probe__">
(() => {
  const visible = (element) => {
    if (!element) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) !== 0 && rect.width > 0 && rect.height > 0;
  };
  const selectorOf = (element) => {
    if (!element) return '';
    if (element.id) return '#' + element.id;
    const tag = element.tagName ? element.tagName.toLowerCase() : 'node';
    const cls = String(element.className || '').trim().split(/\s+/).filter(Boolean).slice(0, 2).join('.');
    return cls ? tag + '.' + cls : tag;
  };
  const finish = () => {
    const root = document.documentElement;
    const body = document.body;
    const state = window.__teacherPcFreeze || {};
    const ids = [...document.querySelectorAll('[id]')].map((element) => element.id).filter(Boolean);
    const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
    const duplicateIdDetails = duplicateIds.map((id) => ({
      id,
      nodes: [...document.querySelectorAll('[id]')]
        .filter((element) => element.id === id)
        .map((element) => ({
          tag: String(element.tagName || '').toLowerCase(),
          className: String(element.className || ''),
          role: element.getAttribute('role') || '',
          ariaModal: element.getAttribute('aria-modal') || '',
          hidden: Boolean(element.hidden),
          html: String(element.outerHTML || '').slice(0, 1200)
        }))
    }));
    const focusables = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[contenteditable="true"],[tabindex]:not([tabindex="-1"])')].filter((element) => visible(element) && !element.disabled && element.getAttribute('aria-hidden') !== 'true');
    const focusFailures = [];
    const focusSequence = [];
    for (const element of focusables.slice(0, 80)) {
      try {
        element.focus({ preventScroll: true });
        if (document.activeElement !== element) focusFailures.push(selectorOf(element));
        else focusSequence.push(selectorOf(element));
      } catch (error) {
        focusFailures.push(selectorOf(element) + ':' + String(error && error.message || error));
      }
    }
    const stylesheets = [...document.querySelectorAll('link[rel~="stylesheet"]')];
    const missingStyles = stylesheets.filter((link) => !link.sheet).map((link) => link.href || link.getAttribute('href') || '');
    const brokenImages = [...document.images].filter((image) => !image.complete || image.naturalWidth === 0).map((image) => image.currentSrc || image.src || image.getAttribute('src') || '');
    const dialogs = [...document.querySelectorAll('dialog,[role="dialog"],[aria-modal="true"]')].filter(visible);
    const dialogFocusOutside = dialogs.filter((dialog) => !dialog.contains(document.activeElement)).map(selectorOf);
    const scrollWidth = Math.max(root.scrollWidth, body ? body.scrollWidth : 0);
    const clientWidth = root.clientWidth;
    const text = String(body && body.innerText || '').replace(/\s+/g, ' ').trim();
    const report = {
      url: location.href,
      title: document.title,
      readyState: document.readyState,
      viewport: { width: innerWidth, height: innerHeight, devicePixelRatio },
      blank: !body || (!text && !body.querySelector('svg,canvas,img,video,iframe')),
      bodyTextLength: text.length,
      rootOverflow: scrollWidth > clientWidth + 1,
      scrollWidth,
      clientWidth,
      duplicateIds,
      duplicateIdDetails,
      brokenImages,
      missingStyles,
      interactiveCount: focusables.length,
      focusFailures,
      focusSequence: focusSequence.slice(0, 20),
      positiveTabindex: focusables.filter((element) => Number(element.getAttribute('tabindex')) > 0).map(selectorOf),
      openDialogCount: dialogs.length,
      dialogFocusOutside,
      consoleErrors: state.consoleErrors || [],
      consoleWarnings: state.consoleWarnings || [],
      runtimeErrors: state.runtimeErrors || [],
      promiseErrors: state.promiseErrors || [],
      resourceErrors: state.resourceErrors || []
    };
    const json = JSON.stringify(report);
    const encoded = btoa(unescape(encodeURIComponent(json)));
    const output = document.createElement('script');
    output.id = '__freeze_report__';
    output.type = 'application/octet-stream';
    output.textContent = encoded;
    document.body.appendChild(output);
    root.setAttribute('data-freeze-probe', 'ready');
  };
  const schedule = () => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(finish, 500)));
  if (document.readyState === 'complete') schedule();
  else window.addEventListener('load', schedule, { once: true });
})();
</script>`

function instrumentHtml(content) {
  let output = content
  if (/<head(?:\s[^>]*)?>/i.test(output)) output = output.replace(/<head(?:\s[^>]*)?>/i, (match) => `${match}\n${BOOTSTRAP}`)
  else output = `${BOOTSTRAP}\n${output}`
  if (/<\/body>/i.test(output)) output = output.replace(/<\/body>/i, `${PROBE}\n</body>`)
  else output += PROBE
  return output
}

function safeResolveUrlPath(urlPath) {
  const decoded = decodeURIComponent(urlPath.split('?')[0])
  const normalized = path.posix.normalize(decoded).replace(/^\/+/, '')
  const abs = path.resolve(ROOT, normalized || 'index.html')
  const relative = path.relative(ROOT, abs)
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) return null
  return abs
}

async function startServer() {
  const server = http.createServer((req, res) => {
    const abs = safeResolveUrlPath(req.url || '/')
    if (!abs || !fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
      res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' })
      res.end('Not Found')
      return
    }
    try {
      const type = mimeType(abs)
      res.writeHead(200, {
        'content-type': type,
        'cache-control': 'no-store, max-age=0',
        'access-control-allow-origin': '*'
      })
      if (path.extname(abs).toLowerCase() === '.html') res.end(instrumentHtml(fs.readFileSync(abs, 'utf8')))
      else fs.createReadStream(abs).pipe(res)
    } catch (error) {
      res.writeHead(500, { 'content-type': 'text/plain; charset=utf-8' })
      res.end(error.stack || error.message)
    }
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  const address = server.address()
  return { server, origin: `http://127.0.0.1:${address.port}` }
}

function runProcess(command, processArgs, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, processArgs, { cwd: ROOT, windowsHide: true, ...options })
    let stdout = ''
    let stderr = ''
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      child.kill('SIGKILL')
    }, timeoutMs)
    child.stdout?.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr?.on('data', (chunk) => { stderr += chunk.toString() })
    child.on('error', (error) => {
      clearTimeout(timer)
      resolve({ code: -1, stdout, stderr: `${stderr}\n${error.stack || error.message}`, timedOut })
    })
    child.on('close', (code) => {
      clearTimeout(timer)
      resolve({ code: code ?? -1, stdout, stderr, timedOut })
    })
  })
}

function parseProbe(dom) {
  const match = dom.match(/<script[^>]*id=["']__freeze_report__["'][^>]*>([A-Za-z0-9+/=]+)<\/script>/i)
  if (!match) return null
  try {
    return JSON.parse(Buffer.from(match[1], 'base64').toString('utf8'))
  } catch {
    return null
  }
}

function classify(result) {
  const issues = []
  const report = result.probe
  if (result.timedOut) issues.push({ severity: 'error', code: 'TIMEOUT', message: `超过 ${timeoutMs}ms` })
  if (result.exitCode !== 0) issues.push({ severity: 'error', code: 'CHROME_EXIT', message: `Chrome 退出码 ${result.exitCode}` })
  if (!report) {
    issues.push({ severity: 'error', code: 'NO_PROBE', message: '未取得浏览器探针结果' })
    return issues
  }
  if (report.readyState !== 'complete') issues.push({ severity: 'error', code: 'NOT_COMPLETE', message: `readyState=${report.readyState}` })
  if (report.blank) issues.push({ severity: 'error', code: 'BLANK_PAGE', message: '页面为空' })
  if (report.rootOverflow) issues.push({ severity: 'error', code: 'ROOT_HORIZONTAL_OVERFLOW', message: `${report.scrollWidth} > ${report.clientWidth}` })
  if (report.runtimeErrors.length) issues.push({ severity: 'error', code: 'RUNTIME_ERROR', message: `${report.runtimeErrors.length} 个运行时错误` })
  if (report.promiseErrors.length) issues.push({ severity: 'error', code: 'UNHANDLED_REJECTION', message: `${report.promiseErrors.length} 个未处理 Promise` })
  if (report.consoleErrors.length) issues.push({ severity: 'error', code: 'CONSOLE_ERROR', message: `${report.consoleErrors.length} 个 console.error` })
  if (report.resourceErrors.length) issues.push({ severity: 'error', code: 'RESOURCE_ERROR', message: `${report.resourceErrors.length} 个资源加载错误` })
  if (report.missingStyles.length) issues.push({ severity: 'error', code: 'MISSING_STYLESHEET', message: `${report.missingStyles.length} 个样式表未加载` })
  if (report.brokenImages.length) issues.push({ severity: 'error', code: 'BROKEN_IMAGE', message: `${report.brokenImages.length} 张图片加载失败` })
  if (report.duplicateIds.length) issues.push({ severity: 'error', code: 'DUPLICATE_ID', message: `${report.duplicateIds.length} 个重复 id：${report.duplicateIds.join(', ')}` })
  if (report.focusFailures.length) issues.push({ severity: 'error', code: 'FOCUS_FAILURE', message: `${report.focusFailures.length} 个可交互元素无法获得焦点` })
  if (report.dialogFocusOutside.length) issues.push({ severity: 'error', code: 'DIALOG_FOCUS_OUTSIDE', message: `${report.dialogFocusOutside.length} 个已打开对话框焦点在外部` })
  if (report.positiveTabindex.length) issues.push({ severity: 'warning', code: 'POSITIVE_TABINDEX', message: `${report.positiveTabindex.length} 个正 tabindex` })
  if (!report.interactiveCount) issues.push({ severity: 'warning', code: 'NO_INTERACTIVE_ELEMENT', message: '页面没有可聚焦交互元素' })
  if (report.consoleWarnings.length) issues.push({ severity: 'warning', code: 'CONSOLE_WARNING', message: `${report.consoleWarnings.length} 个 console.warn` })
  return issues
}

async function renderAttempt(chrome, origin, html, viewport) {
  const url = `${origin}/${html.split('/').map(encodeURIComponent).join('/')}`
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'teacher-pc-v2-chrome-'))
  const chromeArgs = [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-extensions',
    '--disable-background-networking',
    '--disable-component-update',
    '--disable-default-apps',
    '--disable-sync',
    '--metrics-recording-only',
    '--no-first-run',
    '--hide-scrollbars',
    '--force-device-scale-factor=1',
    `--user-data-dir=${profileDir}`,
    `--window-size=${viewport.width},${viewport.height}`,
    `--virtual-time-budget=${virtualTimeMs}`,
    '--dump-dom',
    url
  ]
  const execution = await runProcess(chrome, chromeArgs)
  let screenshotPath = ''
  if (screenshots && execution.code === 0) {
    screenshotPath = path.join(reportRoot, 'screenshots', viewport.label, html.replace(/\.html$/i, '.png'))
    fs.mkdirSync(path.dirname(screenshotPath), { recursive: true })
    const shotProfile = fs.mkdtempSync(path.join(os.tmpdir(), 'teacher-pc-v2-shot-'))
    await runProcess(chrome, [
      '--headless=new', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage', '--hide-scrollbars',
      '--force-device-scale-factor=1', `--user-data-dir=${shotProfile}`,
      `--window-size=${viewport.width},${viewport.height}`, `--virtual-time-budget=${virtualTimeMs}`,
      `--screenshot=${screenshotPath}`, url
    ])
    fs.rmSync(shotProfile, { recursive: true, force: true })
  }
  fs.rmSync(profileDir, { recursive: true, force: true })
  const result = {
    html,
    viewport: viewport.label,
    url,
    exitCode: execution.code,
    timedOut: execution.timedOut,
    stderr: execution.stderr.slice(-4000),
    probe: parseProbe(execution.stdout),
    screenshotPath
  }
  result.issues = classify(result)
  result.status = result.issues.some((issue) => issue.severity === 'error') ? 'FAIL' : 'PASS'
  return result
}

const transientIssueCodes = new Set(['NO_PROBE', 'TIMEOUT', 'CHROME_EXIT'])

function shouldRetry(result) {
  const errors = result.issues.filter((issue) => issue.severity === 'error')
  return errors.length > 0 && errors.every((issue) => transientIssueCodes.has(issue.code))
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function renderOne(chrome, origin, html, viewport) {
  const attempts = []
  let result
  for (let attempt = 1; attempt <= retries + 1; attempt += 1) {
    result = await renderAttempt(chrome, origin, html, viewport)
    attempts.push({
      attempt,
      status: result.status,
      issueCodes: result.issues.map((issue) => issue.code),
      exitCode: result.exitCode,
      timedOut: result.timedOut,
      probeCaptured: Boolean(result.probe)
    })
    if (!shouldRetry(result) || attempt > retries) break
    await wait(300 * (2 ** (attempt - 1)))
  }
  result.attempts = attempts
  return result
}

async function pool(items, limit, worker) {
  const results = new Array(items.length)
  let cursor = 0
  async function run() {
    while (true) {
      const index = cursor++
      if (index >= items.length) return
      results[index] = await worker(items[index], index)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, run))
  return results
}

function markdown(summary, failures, warnings) {
  const lines = [
    '# Teacher PC V2 浏览器冻结回归',
    '',
    `- 生成时间：${summary.generatedAt}`,
    `- Chrome：\`${summary.chrome}\``,
    `- HTML：**${summary.htmlCount}**`,
    `- 分辨率：**${summary.viewportCount}**`,
    `- 计划渲染：**${summary.expectedRenders}**`,
    `- 实际渲染：**${summary.actualRenders}**`,
    `- 通过：**${summary.passed}**`,
    `- 失败：**${summary.failed}**`,
    `- 警告：**${summary.warningRenders}**`,
    `- 重试上限：**${summary.retryLimit}**`,
    `- 发生重试的渲染：**${summary.retriedRenders}**`,
    `- 瞬态失败重试后恢复：**${summary.recoveredTransientFailures}**`,
    `- 最终状态：**${summary.status}**`,
    ''
  ]
  if (failures.length) {
    lines.push('## 失败', '')
    for (const result of failures) lines.push(`- \`${result.viewport}\` \`${result.html}\`：${result.issues.filter((issue) => issue.severity === 'error').map((issue) => `${issue.code} ${issue.message}`).join('；')}`)
    lines.push('')
  }
  if (warnings.length) {
    lines.push('## 警告', '')
    for (const result of warnings.slice(0, 200)) lines.push(`- \`${result.viewport}\` \`${result.html}\`：${result.issues.filter((issue) => issue.severity === 'warning').map((issue) => `${issue.code} ${issue.message}`).join('；')}`)
    lines.push('')
  }
  return `${lines.join('\n')}\n`
}

async function main() {
  fs.mkdirSync(reportRoot, { recursive: true })
  const htmlFiles = collectHtml()
  const chrome = findChrome()
  const { server, origin } = await startServer()
  const jobs = []
  for (const viewport of viewportList) for (const html of htmlFiles) jobs.push({ html, viewport })
  const startedAt = Date.now()
  console.log(`开始回归：${htmlFiles.length} HTML × ${viewportList.length} 分辨率 = ${jobs.length} 次渲染`)
  console.log(`Chrome: ${chrome}`)
  console.log(`并发: ${concurrency}，瞬态重试: ${retries}，报告目录: ${reportRoot}`)
  let completed = 0
  let results
  try {
    results = await pool(jobs, concurrency, async ({ html, viewport }) => {
      const result = await renderOne(chrome, origin, html, viewport)
      completed += 1
      const marker = result.status === 'PASS' ? 'PASS' : 'FAIL'
      console.log(`[${completed}/${jobs.length}] ${marker} ${viewport.label} ${html}`)
      return result
    })
  } finally {
    await new Promise((resolve) => server.close(resolve))
  }

  const failures = results.filter((result) => result.status === 'FAIL')
  const warnings = results.filter((result) => result.status === 'PASS' && result.issues.some((issue) => issue.severity === 'warning'))
  const summary = {
    generatedAt: new Date().toISOString(),
    chrome,
    root: ROOT,
    reportRoot,
    htmlCount: htmlFiles.length,
    viewportCount: viewportList.length,
    viewports: viewportList,
    expectedRenders: htmlFiles.length * viewportList.length,
    actualRenders: results.length,
    passed: results.length - failures.length,
    failed: failures.length,
    warningRenders: warnings.length,
    retryLimit: retries,
    retriedRenders: results.filter((result) => (result.attempts || []).length > 1).length,
    recoveredTransientFailures: results.filter((result) => result.status === 'PASS' && (result.attempts || []).length > 1).length,
    durationSeconds: Math.round((Date.now() - startedAt) / 1000),
    status: !failures.length && results.length === htmlFiles.length * viewportList.length ? 'PASS' : 'FAIL'
  }
  fs.writeFileSync(path.join(reportRoot, 'browser-regression.json'), `${JSON.stringify({ summary, results }, null, 2)}\n`)
  fs.writeFileSync(path.join(reportRoot, 'browser-regression.md'), markdown(summary, failures, warnings))
  console.log(JSON.stringify(summary, null, 2))
  if (summary.status !== 'PASS') process.exit(1)
}

main().catch((error) => {
  console.error(error.stack || error.message)
  process.exit(2)
})
