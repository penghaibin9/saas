import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const srcRoot = path.join(root, 'src')
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))

const declared = new Set([
  ...Object.keys(pkg.dependencies || {}),
  ...Object.keys(pkg.devDependencies || {})
])
const codeExt = new Set(['.js', '.mjs', '.vue'])
const resolutionExt = ['', '.js', '.mjs', '.vue', '.json', '.css']
const forbiddenDomainTokens = [
  '/modules/academicAffairs/',
  '/modules/studentAffairs/',
  '/modules/graduation/',
  '/modules/orientation/',
  '/modules/employment/',
  '/modules/platform/'
]

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    const stat = fs.statSync(full)
    if (stat.isDirectory()) walk(full, out)
    else out.push(full)
  }
  return out
}

function cleanSpecifier(value) {
  return String(value || '').split('?')[0].split('#')[0]
}

function packageName(specifier) {
  if (specifier.startsWith('@')) return specifier.split('/').slice(0, 2).join('/')
  return specifier.split('/')[0]
}

function resolveLocal(fromFile, specifier) {
  const clean = cleanSpecifier(specifier)
  let base
  if (clean.startsWith('@/')) base = path.join(srcRoot, clean.slice(2))
  else if (clean.startsWith('./') || clean.startsWith('../')) {
    base = path.resolve(path.dirname(fromFile), clean)
  } else {
    return null
  }

  const relative = path.relative(srcRoot, base)
  if (relative === '..' || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
    return { outside: true, base }
  }

  const candidates = []
  for (const ext of resolutionExt) candidates.push(base + ext)
  for (const ext of resolutionExt.filter(Boolean)) candidates.push(path.join(base, 'index' + ext))
  return { outside: false, base, found: candidates.some((candidate) => fs.existsSync(candidate)) }
}

const files = walk(srcRoot).filter((file) => codeExt.has(path.extname(file)))
const importRe = /(?:import\s+(?:[^'"]*?\s+from\s+)?|export\s+[^'"]*?\s+from\s+|import\s*\()\s*['"]([^'"]+)['"]/g
const missing = []
const outside = []
const undeclared = new Set()
const crossDomain = []

for (const file of files) {
  const source = fs.readFileSync(file, 'utf8')
  const rel = path.relative(srcRoot, file).replaceAll(path.sep, '/')
  let match
  while ((match = importRe.exec(source))) {
    const specifier = match[1]
    const local = resolveLocal(file, specifier)
    if (local) {
      if (local.outside) outside.push(`${rel} -> ${specifier}`)
      else if (!local.found) missing.push(`${rel} -> ${specifier}`)
      const normalized = cleanSpecifier(specifier).replaceAll('\\', '/')
      if (forbiddenDomainTokens.some((token) => normalized.includes(token))) {
        crossDomain.push(`${rel} -> ${specifier}`)
      }
      continue
    }
    if (specifier.startsWith('node:')) continue
    if (specifier.startsWith('/') || specifier.startsWith('file:')) {
      outside.push(`${rel} -> ${specifier}`)
      continue
    }
    const dependency = packageName(specifier)
    if (dependency && !declared.has(dependency)) undeclared.add(`${dependency} (from ${rel})`)
  }
}

const errors = []
if (missing.length) errors.push('Missing local imports:\n' + missing.map((x) => '  - ' + x).join('\n'))
if (outside.length) errors.push('Imports escaping standalone src:\n' + outside.map((x) => '  - ' + x).join('\n'))
if (crossDomain.length) errors.push('Forbidden cross-domain imports:\n' + crossDomain.map((x) => '  - ' + x).join('\n'))
if (undeclared.size) errors.push('Undeclared npm dependencies:\n' + [...undeclared].sort().map((x) => '  - ' + x).join('\n'))

if (errors.length) {
  throw new Error('Standalone admin import closure failed\n\n' + errors.join('\n\n'))
}

console.log(`Standalone admin import closure: OK (${files.length} source files)`)
