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

/** Read literal route properties in their enclosing object, without executing router code. */
export function extractRouteSource(text) {
  const exact = new Set(), patterns = new Set(), redirects = [], aliases = []
  // Keep strings as single tokens so braces in lazy imports, comments and path parameters
  // cannot change the parent route. Absolute siblings must never become layout parents.
  const tokens = [...text.matchAll(/\/\*[\s\S]*?\*\/|\/\/[^\n]*|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|[{}\[\]:,]/g)]
    .map(match => match[0]).filter(token => !token.startsWith('//') && !token.startsWith('/*'))
  const stack = [], objects = []
  const literal = token => token && /^["'`]/.test(token) && !token.includes('${') ? token.slice(1, -1) : null
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i]
    if (token === '{') {
      const object = { parent: stack.at(-1), path: null, redirect: null, aliases: [] }
      objects.push(object); stack.push(object)
    } else if (token === '}') stack.pop()
    else if (stack.length && tokens[i + 1] === ':') {
      const object = stack.at(-1), key = literal(token) ?? token
      if (key === 'path' || key === 'redirect') object[key] = literal(tokens[i + 2])
      else if (key === 'alias') {
        if (tokens[i + 2] === '[') {
          for (let j = i + 3; j < tokens.length && tokens[j] !== ']'; j++) {
            const value = literal(tokens[j]); if (value !== null) object.aliases.push(value)
          }
        } else { const value = literal(tokens[i + 2]); if (value !== null) object.aliases.push(value) }
      }
    }
  }
  function parentRoute(object) {
    let parent = object.parent
    while (parent && parent.path === null) parent = parent.parent
    return parent
  }
  function absolute(object) { return joinPath(parentRoute(object) ? absolute(parentRoute(object)) : '', object.path) }
  for (const object of objects) {
    if (object.path === null) continue
    const from = absolute(object)
    registerPath(exact, patterns, from)
    if (object.redirect !== null) {
      const to = normalizeExact(object.redirect)
      redirects.push({ from: normalizeExact(from), to })
    }
    for (const alias of object.aliases) {
      const aliasPath = joinPath(parentRoute(object) ? absolute(parentRoute(object)) : '', alias)
      registerPath(exact, patterns, aliasPath)
      aliases.push({ from: normalizeExact(aliasPath), to: normalizeExact(from) })
    }
  }
  return { exact, patterns, redirects, aliases }
}

function extractFromFile(file) { return extractRouteSource(fs.readFileSync(file, 'utf8')) }

export function buildRouteIndex() {
  const files = [
    ...walkRouteFiles(path.join(ROOT, 'frontend/src/router')),
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
  // Redirect/alias sources may themselves be parameterized route declarations.
  if ((index.aliases || []).some((a) => a.from === clean)) return { exists: true, matchType: 'alias' }
  if ((index.redirects || []).some((r) => r.from === clean)) return { exists: true, matchType: 'redirect' }
  if (index.exact.has(clean)) {
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
