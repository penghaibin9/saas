import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('student affairs workbench links statistics and archive to their real workspaces', () => {
  const source = read('src/modules/workbench/components/StudentAffairsPriorityPanel.vue')
  assert.match(source, /label: '学工统计', path: '\/admin\/student-affairs\/stats', permission: 'studentAffairs\.stats\.view'/)
  assert.match(source, /label: '学工归档', path: '\/admin\/student-affairs\/archive', permission: 'studentAffairs\.archive\.view'/)
  assert.doesNotMatch(source, /label: '统计与档案'[\s\S]{0,120}material-operations/)
})

test('archive batch and package ledger preserve the same deep-link context', () => {
  const archive = read('src/modules/studentAffairs/views/ArchiveManageView.vue')
  const packages = read('src/modules/studentAffairs/views/StudentArchivePackageView.vue')
  assert.match(archive, /'\$route\.query\.batchId'/)
  assert.match(archive, /path: '\/admin\/student-affairs\/archive\/packages', query: \{ batchId:/)
  assert.match(packages, /String\(this\.\$route\?\.query\?\.batchId \|\| ''\)/)
  assert.match(packages, /changeBatch\(\)/)
  assert.match(packages, /delete query\.batchId/)
  assert.match(packages, /this\.\$router\.replace\(\{ query \}\)/)
})
