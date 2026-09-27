import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'

function view(file, bindings = {}) {
  const path = new URL(`../src/modules/graduation/views/${file}.vue`, import.meta.url)
  const { descriptor, errors } = parse(fs.readFileSync(path, 'utf8'))
  assert.deepEqual(errors, [])
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: file }).errors, [])
  const script = descriptor.script.content
    .replace(/^import[\s\S]*?from\s*['"][^'"]+['"]\s*$/gm, '')
    .replace(/components:\s*\{[^}]*\},/, 'components: {},')
    .replace('export default', 'return')
  return new Function(...Object.keys(bindings), script)(...Object.values(bindings))
}

function bind(options, extra) {
  const state = { ...options.data(), ...extra }
  for (const [key, method] of Object.entries(options.methods)) state[key] = method.bind(state)
  for (const [key, getter] of Object.entries(options.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return state
}

test('毕设学生名单保留毕业审核的学号筛选和安全返回，详情只在成功读取后显示返回', async () => {
  const returnTo = '/admin/academic-affairs/graduation/audit-console?termId=54&batchId=13&tab=thesis&resultId=77'
  const listOptions = view('GraduationStudentListView', { useGraduationBatchStore: () => ({ selectedBatchId: '53' }), gdStudentApi: {} })
  const list = bind(listOptions, { $route: { query: { panel: 'roster', keyword: 'V52023001', returnTo } }, $router: {} })
  list.applyInitialRouteState(list.$route.query)
  assert.equal(list.filters.keyword, 'V52023001')
  assert.equal(list.graduationReturnTo, returnTo)
  list.$route.query.returnTo = 'https://outside.invalid/'
  assert.equal(list.graduationReturnTo, '')

  const detailOptions = view('GraduationStudentDetailView', { graduationMaterialStageLabel: value => value, graduationPlagiarismStatusLabel: value => value })
  const pushes = []
  const detail = bind(detailOptions, { $route: { query: { returnTo } }, $router: { push: target => pushes.push(target) } })
  assert.equal(detail.graduationReturnTo, '')
  detail.detail = { id: '91', stage: 'GUIDING', topicId: '10', advisorName: '虚构导师' }
  assert.ok(detail.toolbarActions.some(action => action.key === 'backAcademic'))
  await detail.onToolbar('backAcademic')
  assert.equal(pushes[0], returnTo)
  detail.$route.query.returnTo = '//outside.invalid/'
  assert.equal(detail.graduationReturnTo, '')
})
