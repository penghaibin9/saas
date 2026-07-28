import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'

const root = new URL('../src/modules/internship/', import.meta.url)
const layoutUrl = new URL('../src/modules/internship/views/AdminInternshipLayout.vue', import.meta.url)
const adapterUrl = new URL('../src/modules/internship/pickerAdapters.js', import.meta.url)

async function vueFiles(dir = root) {
  const entries = await readdir(dir, { withFileTypes: true })
  const nested = await Promise.all(entries.map(async (entry) => {
    const url = new URL(`${entry.name}${entry.isDirectory() ? '/' : ''}`, dir)
    if (entry.isDirectory()) return vueFiles(url)
    return entry.name.endsWith('.vue') ? [url] : []
  }))
  return nested.flat()
}

test('岗位实习布局注入统一 Picker 适配器', async () => {
  const [layout, adapter] = await Promise.all([readFile(layoutUrl, 'utf8'), readFile(adapterUrl, 'utf8')])
  assert.match(layout, /appPickerAdapters:\s*internshipPickerAdapters/)
  for (const key of ['candidateInternshipStudent', 'internshipStudent', 'unassignedInternshipStudent', 'internshipPosition', 'internshipEnterprise', 'internshipAdvisor', 'internshipBatch', 'enterpriseMentor']) {
    assert.match(adapter, new RegExp(`\\b${key}\\b`))
  }
})

test('岗位实习页面不再各自接线远程实体搜索或保留原生实体选择控件', async () => {
  const files = await vueFiles()
  const nativeEntitySelect = /<select\b[^>]*v-model(?:\.[\w]+)*="[^"]*(?:student|enterprise|position|advisor|mentor|batch)[^"]*"/i
  for (const file of files) {
    const source = await readFile(file, 'utf8')
    assert.doesNotMatch(source, /:remote-search=/, file.pathname)
    assert.doesNotMatch(source, /entityPickerAdapters/, file.pathname)
    assert.doesNotMatch(source, nativeEntitySelect, file.pathname)
    assert.doesNotMatch(source, /type="date"/, file.pathname)
  }
})
