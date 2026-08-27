import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, extname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')
const graduationRoot = resolve(repoRoot, 'frontend', 'src', 'modules', 'graduation')
const backendCatalogPath = resolve(repoRoot, 'backend', 'app', 'core', 'graduation_permissions.py')
const CODE_RE = /graduationDesign\.[A-Za-z][A-Za-z0-9_.]*/g
const SOURCE_EXTS = new Set(['.js', '.vue', '.ts'])

function walk(dir) {
  const out = []
  for (const name of readdirSync(dir)) {
    const path = resolve(dir, name)
    const st = statSync(path)
    if (st.isDirectory()) out.push(...walk(path))
    else if (SOURCE_EXTS.has(extname(path))) out.push(path)
  }
  return out
}

function codesIn(text) {
  return new Set(text.match(CODE_RE) || [])
}

test('all graduation frontend permission codes exist in backend canonical catalog', () => {
  const canonical = codesIn(readFileSync(backendCatalogPath, 'utf8'))
  assert.ok(canonical.size > 20, 'backend graduation permission catalog unexpectedly small')

  const unknown = []
  for (const file of walk(graduationRoot)) {
    const text = readFileSync(file, 'utf8')
    for (const code of codesIn(text)) {
      if (!canonical.has(code)) {
        unknown.push(`${file.slice(repoRoot.length + 1)} -> ${code}`)
      }
    }
  }

  assert.deepEqual(unknown.sort(), [], `frontend graduation permission codes missing from backend catalog:\n${unknown.sort().join('\n')}`)
})

test('retired graduation aggregate aliases cannot return to production frontend', () => {
  const retired = [
    'graduationDesign.stats.view',
    'graduationDesign.riskArchive.manage',
    'graduationDesign.topic.lib',
    'graduationDesign.topic.round',
    'graduationDesign.topic.manage',
    'graduationDesign.topic.change',
    'graduationDesign.mentor.manage'
  ]

  const violations = []
  for (const file of walk(graduationRoot)) {
    const text = readFileSync(file, 'utf8')
    for (const code of retired) {
      if (text.includes(code)) violations.push(`${file.slice(repoRoot.length + 1)} -> ${code}`)
    }
  }
  assert.deepEqual(violations.sort(), [])
})
