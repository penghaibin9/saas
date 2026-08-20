import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8')

test('T7 employment quick actions must resolve to the real recommendation and verification workspace', () => {
  const workbench = read('src/pages/teacher/workbench/index.vue')
  const page = read('src/pages/teacher/employment-follow/index.vue')
  assert.match(workbench, /recommend:\s*'\/pages\/teacher\/employment-follow\/index\?tab=unemployed'/)
  assert.match(workbench, /verify:\s*'\/pages\/teacher\/employment-follow\/index\?tab=verify'/)
  assert.match(page, /const TAB_KEYS = new Set\(\['unemployed', 'following', 'verify', 'done'\]\)/)
  assert.match(page, /const requestedTab = String\(\(q && q\.tab\) \|\| ''\)\.trim\(\)/)
  assert.match(page, /if \(TAB_KEYS\.has\(requestedTab\)\) this\.tab = requestedTab/)
})
