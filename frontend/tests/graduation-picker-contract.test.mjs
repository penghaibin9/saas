import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'

const root = new URL('../src/modules/graduation/', import.meta.url)
const layoutUrl = new URL('../src/modules/graduation/views/AdminGraduationLayout.vue', import.meta.url)
const adapterUrl = new URL('../src/modules/graduation/pickerAdapters.js', import.meta.url)

async function vueFiles(dir = root) {
  const entries = await readdir(dir, { withFileTypes: true })
  const nested = await Promise.all(entries.map(async (entry) => {
    const url = new URL(`${entry.name}${entry.isDirectory() ? '/' : ''}`, dir)
    if (entry.isDirectory()) return vueFiles(url)
    return entry.name.endsWith('.vue') ? [url] : []
  }))
  return nested.flat()
}

test('毕业设计布局注入统一 Picker 适配器', async () => {
  const [layout, adapter] = await Promise.all([readFile(layoutUrl, 'utf8'), readFile(adapterUrl, 'utf8')])

  assert.match(layout, /appPickerAdapters:\s*graduationPickerAdapters/)
  for (const key of ['candidateStudent', 'graduationStudent', 'graduationMentor', 'availableMentor', 'graduationBatch', 'graduationTopic', 'defenseGroup']) {
    assert.match(adapter, new RegExp(`\\b${key}\\b`))
  }
})

test('毕业设计页面不再各自实现 Picker 远程搜索或通用题目、答辩组下拉', async () => {
  const files = await vueFiles()
  const sources = await Promise.all(files.map((file) => readFile(file, 'utf8')))
  const joined = sources.join('\n')

  assert.doesNotMatch(joined, /:remote-search=/)
  assert.doesNotMatch(joined, /search(?:Teachers|Mentors|Reviewers|Students)\(keyword\)/)
  assert.doesNotMatch(joined, /<AppRemoteSelect/)
})
