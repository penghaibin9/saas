import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'

const root = new URL('../src/modules/studentAffairs/', import.meta.url)
const layoutUrl = new URL('../src/modules/studentAffairs/views/AdminStudentAffairsLayout.vue', import.meta.url)
const adapterUrl = new URL('../src/modules/studentAffairs/pickerAdapters.js', import.meta.url)

async function vueFiles(dir = root) {
  const entries = await readdir(dir, { withFileTypes: true })
  const nested = await Promise.all(entries.map(async (entry) => {
    const url = new URL(`${entry.name}${entry.isDirectory() ? '/' : ''}`, dir)
    if (entry.isDirectory()) return vueFiles(url)
    return entry.name.endsWith('.vue') ? [url] : []
  }))
  return nested.flat()
}

test('学工布局注入统一 Picker 适配器', async () => {
  const [layout, adapter] = await Promise.all([readFile(layoutUrl, 'utf8'), readFile(adapterUrl, 'utf8')])

  assert.match(layout, /appPickerAdapters:\s*studentAffairsPickerAdapters/)
  for (const key of ['student', 'riskOwner', 'aidBatch', 'fundingProject', 'fundingBatch', 'studentArchiveBatch', 'dormBuilding', 'dormRoom', 'dormBed']) {
    assert.match(adapter, new RegExp(`\\b${key}\\b`))
  }
})

test('学工页面不再各自注入学生或风险责任人 remote-search', async () => {
  const files = await vueFiles()
  const sources = await Promise.all(files.map((file) => readFile(file, 'utf8')))
  const joined = sources.join('\n')

  assert.doesNotMatch(joined, /:remote-search=/)
  assert.doesNotMatch(joined, /searchStudents\(keyword\)/)
  assert.doesNotMatch(joined, /searchRiskOwners\(keyword\)/)
})
