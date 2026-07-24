/**
 * 从前端真实路由定义构建规范化路由索引。
 * 处理：嵌套路径、动态参数（含可选 :id?）、redirect、alias、默认子路由。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '../..')

function walkRouteFiles(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    const st = fs.statSync(full)
    if (st.isDirectory()) {
      if (name === 'node_modules' || name === 'dist') continue
      walkRouteFiles(full, acc)
    } else if (
      name.endsWith('.routes.js')
      || name === 'routes.js'
      || name.endsWith('.route.js')
      || (name === 'index.js' && full.replace(/\\/g, '/').includes('/router/'))
    ) {
      acc.push(full)
    }
  }
  return acc
}

function joinPath(parent, child) {
  if (child === '' || child === undefined) return parent || '/'
  if (String(child).startsWith('/')) return String(child)
  if (!parent || parent === '/') return '/' + String(child).replace(/^\//, '')
  return (parent.replace(/\/$/, '') + '/' + String(child).replace(/^\//, '')).replace(/\/+/g, '/')
}

function normalizeExact(p) {
  return String(p || '')
    .split('?')[0]
    .replace(/\/+/g, '/')
    .replace(/\/$/, '') || '/'
}

function stripParams(p) {
  return normalizeExact(String(p || '').replace(/\/:[^/]+\??/g, ''))
}

/** `/a/:id?` → pattern keys + exact base without optional segment */
function registerPath(exact, patterns, absRaw) {
  const abs = String(absRaw || '').split('#')[0]
  if (!abs) return
  const hasParam = /\/:/.test(abs) || abs.includes('*')
  if (hasParam) {
    patterns.add(abs)
    exact.add(stripParams(abs))
  } else {
    exact.add(normalizeExact(abs))
  }
}

function patternToRegex(pattern) {
  let body = ''
  for (const seg of String(pattern || '').split('/')) {
    if (!seg) continue
    if (seg.startsWith(':') && seg.endsWith('?')) {
      body += '(?:/[^/]+)?'
    } else if (seg.startsWith(':')) {
      body += '/' + '[^/]+'
    } else if (seg === '*') {
      body += '/' + '.*'
    } else {
      body += '/' + seg.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    }
  }
  if (!body) body = '/'
  return new RegExp('^' + body + '$')
}

/**
 * 相对 path 挂到「最近出现的绝对 layout path」下（适配 router/index.js 多根）。
 */
function extractFromFile(file) {
  const text = fs.readFileSync(file, 'utf8')
  const exact = new Set()
  const patterns = new Set()
  const redirects = []
  const aliases = []

  let lastAbsLayout = ''
  const pathRe = /\bpath:\s*['"`]([^'"`]*)['"`]/g
  let m
  while ((m = pathRe.exec(text))) {
    const raw = m[1]
    if (raw.startsWith('/')) {
      // Absolute route: becomes new layout parent when it has no dynamic segments
      registerPath(exact, patterns, raw)
      if (!/\/:/.test(raw) && !raw.includes('*')) {
        lastAbsLayout = normalizeExact(raw)
      } else {
        // dynamic absolute — parent is path without params
        lastAbsLayout = stripParams(raw)
      }
    } else {
      const abs = joinPath(lastAbsLayout, raw)
      registerPath(exact, patterns, abs)
    }
  }

  for (const rm of text.matchAll(/\bredirect:\s*['"`]([^'"`]+)['"`]/g)) {
    const to = normalizeExact(rm[1])
    exact.add(to)
    const idx = rm.index
    const before = text.slice(Math.max(0, idx - 400), idx)
    const pathsBefore = [...before.matchAll(/\bpath:\s*['"`]([^'"`]*)['"`]/g)]
    if (pathsBefore.length) {
      const last = pathsBefore[pathsBefore.length - 1][1]
      const from = normalizeExact(last.startsWith('/') ? last : joinPath(lastAbsLayout, last))
      redirects.push({ from, to })
      exact.add(from)
    }
  }

  for (const am of text.matchAll(/\balias:\s*['"`]([^'"`]+)['"`]/g)) {
    const a = normalizeExact(am[1].startsWith('/') ? am[1] : joinPath(lastAbsLayout, am[1]))
    aliases.push({ from: a, to: lastAbsLayout || a })
    exact.add(a)
  }
  for (const am of text.matchAll(/\balias:\s*\[([^\]]+)\]/g)) {
    for (const x of am[1].matchAll(/['"`]([^'"`]+)['"`]/g)) {
      const a = normalizeExact(x[1].startsWith('/') ? x[1] : joinPath(lastAbsLayout, x[1]))
      aliases.push({ from: a, to: lastAbsLayout || a })
      exact.add(a)
    }
  }

  return { exact, patterns, redirects, aliases }
}

export function buildRouteIndex() {
  const files = [
    path.join(ROOT, 'frontend/src/router/index.js'),
    ...walkRouteFiles(path.join(ROOT, 'frontend/src/modules')),
  ]
  const exact = new Set()
  const patterns = new Set()
  const redirects = []
  const aliases = []
  for (const f of [...new Set(files)]) {
    try {
      const part = extractFromFile(f)
      part.exact.forEach((p) => exact.add(p))
      part.patterns.forEach((p) => patterns.add(p))
      redirects.push(...part.redirects)
      aliases.push(...part.aliases)
    } catch {
      // ignore unreadable route files
    }
  }
  const patternList = [...patterns]
  return {
    exact,
    patterns: patternList,
    redirects,
    aliases,
    patternRegexes: patternList.map((p) => ({ pattern: p, re: patternToRegex(p) })),
  }
}

export function matchRouteExists(index, fullPath) {
  if (!fullPath) return { exists: false, matchType: 'missing' }
  const clean = normalizeExact(String(fullPath).split('?')[0])
  if (index.exact.has(clean)) {
    if ((index.aliases || []).some((a) => a.from === clean)) return { exists: true, matchType: 'alias' }
    if ((index.redirects || []).some((r) => r.from === clean)) return { exists: true, matchType: 'redirect' }
    return { exists: true, matchType: 'exact' }
  }
  for (const { pattern, re } of index.patternRegexes || []) {
    if (re.test(clean)) return { exists: true, matchType: 'param', pattern }
  }
  return { exists: false, matchType: 'missing' }
}

const isMain = process.argv[1]
  && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href

if (isMain) {
  const index = buildRouteIndex()
  const out = {
    generatedAt: new Date().toISOString(),
    exactCount: index.exact.size,
    patternCount: index.patterns.length,
    redirectCount: index.redirects.length,
    aliasCount: index.aliases.length,
    exact: [...index.exact].sort(),
    patterns: index.patterns,
    redirects: index.redirects,
    aliases: index.aliases,
  }
  const dest = path.join(ROOT, 'shared/generated/route-index.json')
  fs.mkdirSync(path.dirname(dest), { recursive: true })
  fs.writeFileSync(dest, JSON.stringify(out, null, 2) + '\n', 'utf8')
  console.log(`OK route-index exact=${out.exactCount} patterns=${out.patternCount}`)
}
