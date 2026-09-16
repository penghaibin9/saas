import { readFileSync, writeFileSync, readdirSync, mkdirSync, unlinkSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const TEXT = new Set(['.js', '.json', '.wxml', '.wxss', '.wxs'])
const QUOTED_PATH = /(['"])([./][^'"\r\n]*?)\1/g
const SCOPE = /\bdata-v-[0-9a-f]{8}\b/g
function walk(dir, prefix = '') {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory()
    ? walk(path.join(dir, e.name), prefix + e.name + '/') : [prefix + e.name])
}
// Relocate only artifacts reached exclusively from one subpackage. Shared files stay in main.
// All literal dependency references are rewritten, never business URLs, permissions or state.
export function optimizeWeixin(output) {
  const names = walk(output), files = new Map(names.map(n => [n, readFileSync(path.join(output, n))]))
  const sources = new Map(names.filter(n => TEXT.has(path.extname(n))).map(n => [n, files.get(n).toString('utf8')]))
  const app = JSON.parse(sources.get('app.json'))
  const packs = app.subPackages || app.subpackages || []
  const rootOf = n => packs.find(p => n.startsWith(p.root + '/'))?.root || 'main'
  const family = n => ['.js', '.json', '.wxml', '.wxss'].map(e => n + e).filter(n => files.has(n))
  function target(from, literal) {
    const full = path.posix.normalize(literal.startsWith('/') ? literal.slice(1) : path.posix.join(path.posix.dirname(from), literal))
    if (files.has(full)) return { name: full, extension: '' }
    const name = family(full)[0]
    // Navigation URLs are not imports; only absolute component IDs may omit an extension.
    if (name && literal.startsWith('/')) {
      const config = sources.get(full + '.json')
      if (!config || JSON.parse(config).component !== true) return null
    }
    return name ? { name, extension: path.posix.extname(name) } : null
  }
  const edges = new Map(names.map(n => [n, new Set(family(n.replace(/\.(js|json|wxml|wxss)$/, '')))]))
  for (const [name, source] of sources) for (const m of source.matchAll(QUOTED_PATH)) {
    const found = target(name, m[2]); if (found) edges.get(name).add(found.name)
  }
  const owners = new Map(names.map(n => [n, new Set()]))
  const entries = [['main', ['app', ...(app.pages || [])]], ...packs.map(p => [p.root, p.pages.map(n => p.root + '/' + n)])]
  for (const [owner, pages] of entries) {
    const stack = pages.flatMap(family), visited = new Set()
    while (stack.length) {
      const n = stack.pop(); if (visited.has(n)) continue
      visited.add(n); owners.get(n).add(owner); stack.push(...edges.get(n))
    }
  }
  const moves = new Map()
  for (const [n, set] of owners) if (rootOf(n) === 'main' && set.size === 1 && !set.has('main') && !set.has('pages/student') && /^(components|services|modules|utils)\//.test(n)) {
    const dest = [...set][0] + '/_shared/' + n
    if (files.has(dest)) throw Error('Refusing to overwrite existing package artifact: ' + dest)
    moves.set(n, dest)
  }
  // The emitted WeChat runtime treats scope strings as opaque classes. Preserve a collision-free
  // bijection across every JS/WXML/WXSS file, without stripping style isolation.
  const ids = [...new Set([...sources.values()].flatMap(s => [...s.matchAll(SCOPE)].map(m => m[0])))].sort()
  const aliases = new Map(ids.map((s, i) => [s, 'yk' + i.toString(36)]))
  for (const alias of aliases.values()) if ([...sources.values()].some(s => new RegExp('\\b' + alias + '\\b').test(s))) throw Error('Scope alias collision')
  const rewritten = new Map()
  for (const [n, bytes] of files) {
    const dest = moves.get(n) || n
    if (!sources.has(n)) { rewritten.set(dest, bytes); continue }
    let source = sources.get(n).replace(QUOTED_PATH, (whole, quote, literal) => {
      const found = target(n, literal); if (!found) return whole
      const to = moves.get(found.name) || found.name
      let next = literal.startsWith('/') ? '/' + to : path.posix.relative(path.posix.dirname(dest), to)
      if (found.extension) next = next.slice(0, -found.extension.length)
      if (!literal.startsWith('/') && !next.startsWith('.')) next = './' + next
      return quote + next + quote
    }).replace(SCOPE, s => aliases.get(s))
    if (path.extname(n) === '.json') source = JSON.stringify(JSON.parse(source))
    rewritten.set(dest, Buffer.from(source))
  }
  // Check every known reference before changing output; a relocated dependency must remain reachable.
  for (const [n, source] of sources) for (const m of source.matchAll(QUOTED_PATH)) {
    const found = target(n, m[2]); if (!found) continue
    const from = moves.get(n) || n, to = moves.get(found.name) || found.name
    if (!rewritten.has(to)) throw Error('Lost dependency: ' + to)
    if (rootOf(from) === 'main' && rootOf(to) !== 'main') throw Error('Main cannot depend on a subpackage: ' + to)
    if (rootOf(from) !== 'main' && rootOf(to) !== 'main' && rootOf(from) !== rootOf(to)) throw Error('Cross-subpackage dependency: ' + to)
  }
  for (const [name, bytes] of rewritten) {
    const full = path.join(output, name); mkdirSync(path.dirname(full), { recursive: true }); writeFileSync(full, bytes)
  }
  for (const old of moves.keys()) unlinkSync(path.join(output, old))
  return { movedFiles: Object.fromEntries(moves), scopeCount: ids.length,
    beforeBytes: [...files.values()].reduce((n, b) => n + b.length, 0),
    afterBytes: [...rewritten.values()].reduce((n, b) => n + b.length, 0) }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const output = fileURLToPath(new URL('../dist/build/mp-weixin/', import.meta.url))
  const result = optimizeWeixin(output)
  console.log('[mp optimization]', JSON.stringify({ moved: Object.keys(result.movedFiles).length,
    scopes: result.scopeCount, savedBytes: result.beforeBytes - result.afterBytes }))
}
