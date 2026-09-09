import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const srcRoot = new URL('../src/', import.meta.url)
const businessRoots = [
  'modules/academicAffairs',
  'modules/studentAffairs',
  'modules/system',
  'modules/internship',
  'modules/graduation',
  'modules/messageCenter',
  'views/admin/employment',
  'views/admin/orientation'
]

function vueFiles(directory) {
  const files = []
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) files.push(...vueFiles(path))
    else if (extname(entry.name) === '.vue') files.push(path)
  }
  return files
}

test('电脑端枚举标签不再以原始英文值作为字典兜底', () => {
  const unsafeFallback = /return[^\r\n]*(?:\]|\?\.label|\.label)\s*\|\|\s*(?:value|status|type|level|state|method|mode|source|role|code|raw|key|s|v|t)\b/
  const offenders = []
  for (const root of businessRoots) {
    for (const file of vueFiles(fileURLToPath(new URL(root, srcRoot)))) {
      const source = readFileSync(file, 'utf8')
      if (unsafeFallback.test(source)) offenders.push(file)
    }
  }
  assert.deepEqual(offenders, [])
})

test('重点页面不再展示后端状态码和英文技术说明', () => {
  const checks = [
    ['modules/academicAffairs/views/ArchivePrecheckView.vue', /BLOCKED 是|UNKNOWN 是|PASS 表示|NOT_APPLICABLE 表示/],
    ['modules/academicAffairs/views/AaScheduleMaintainView.vue', />\s*READY 教学任务|['"]READY 教学任务/],
    ['modules/academicAffairs/views/AaSelectionConsoleView.vue', /['"]READY 教学任务/],
    ['modules/system/views/SystemPlatformIntegrityView.vue', />\s*(?:Critical|High|Medium|Today New|7d Unresolved)\s*</],
    ['modules/studentAffairs/views/MaterialOperationsView.vue', /Manifest ID|>versionId<|站内材料 Reader/]
  ]
  for (const [relative, pattern] of checks) {
    assert.doesNotMatch(readFileSync(new URL(relative, srcRoot), 'utf8'), pattern, relative)
  }
})
