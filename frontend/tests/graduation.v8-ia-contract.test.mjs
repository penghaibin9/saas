import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import process from 'node:process'
import test from 'node:test'
import vm from 'node:vm'

import { GRADUATION_WORKSPACES } from '../src/modules/graduation/config/graduationWorkspaces.js'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('V8 keeps eight workspaces and compresses the primary sidebar to 24 entries', () => {
  assert.equal(GRADUATION_WORKSPACES.length, 8)
  assert.equal(GRADUATION_WORKSPACES.reduce((sum, workspace) => sum + workspace.children.length, 0), 24)
  assert.deepEqual(GRADUATION_WORKSPACES.map((workspace) => workspace.label), [
    '我的工作台', '批次与实施', '题目与选题', '过程指导',
    '开题与成果', '答辩与成绩', '风险与归档', '模板与设置'
  ])
})

test('V8 legacy batch query routes land on the requested batch configuration view', async () => {
  const source = await read('../src/modules/graduation/views/GraduationBatchListView.vue')
  assert.match(source, /query\.batchId/)
  assert.match(source, /panel === 'stages' \|\| panel === 'rules'/)
  assert.match(source, /name: 'graduation-batch-detail'/)
  assert.match(source, /params: \{ id: batchId \}/)
  assert.match(source, /query: \{ tab: panel, batchId \}/,
    'named navigation must preserve both the requested panel and the batch identity')
})

test('V8 student and topic pages expose five primary groups while preserving every legacy panel', async () => {
  const [students, topics] = await Promise.all([
    read('../src/modules/graduation/views/GraduationStudentListView.vue'),
    read('../src/modules/graduation/views/TopicLibListView.vue')
  ])
  for (const label of ['名单', '进度与风险', '关系与资格', '材料与答辩', '收口与归档']) {
    assert.match(students, new RegExp(`label: '${label}'`))
  }
  for (const panel of ['roster', 'progress', 'risk', 'mentor', 'topic', 'eligibility', 'grouping', 'materials', 'defense', 'grad-qual', 'archive']) {
    assert.ok(students.includes(`'${panel}'`), `student legacy panel ${panel} must remain`)
  }
  for (const label of ['题目库', '审核', '质量治理', '容量', '历史']) {
    assert.match(topics, new RegExp(`label: '${label}'`))
  }
  for (const panel of ['list', 'pending', 'teacher-apply', 'enterprise', 'student-proposed', 'category', 'capacity', 'requirements', 'attachments', 'history', 'archive']) {
    assert.ok(topics.includes(`'${panel}'`), `topic legacy panel ${panel} must remain`)
  }
})

test('V6 student ledger keeps the real master, read-only academic mirror and recoverable work context', async () => {
  const source = await read('../src/modules/graduation/views/GraduationStudentListView.vue')

  assert.match(source, /毕业资格是教务只读镜像/)
  assert.match(source, /教务只读镜像/)
  assert.ok(!source.includes('gdStudentApi.setGradQual'), 'graduation UI must not write the academic graduation qualification mirror')

  for (const queryKey of ['batchId', 'panel', 'page', 'keyword', 'returnTo']) {
    assert.ok(source.includes(queryKey), `student work context must preserve ${queryKey}`)
  }
  assert.match(source, /buildListQuery\(overrides = \{\}\)/)
  assert.match(source, /studentReturnQuery\(panel = this\.activePanel\)/)
  assert.match(source, /returnTo: this\.currentListPath\(panel\)/)

  assert.match(source, /loadToken/)
  assert.match(source, /statsToken/)
  assert.match(source, /token !== this\.loadToken/)
  assert.match(source, /token !== this\.statsToken/)
  assert.match(source, /String\(batchId\) !== String\(this\.batchStore\.selectedBatchId\)/)

  assert.match(source, /AppExcelImportDrawer/)
  assert.match(source, /downloadImportTemplate/)
  assert.match(source, /uploadImportXlsx/)
  assert.match(source, /importConfirm\(rows, previewToken\)/)
  assert.match(source, /downloadImportErrors/)
  for (const step of ['下载模板', '上传并预览', '下载错误行', '确认导入并留痕']) {
    assert.match(source, new RegExp(step))
  }
})

test('V6 entry guidance lives in business pages without duplicating the module header', async () => {
  const [layout, students] = await Promise.all([
    read('../src/modules/graduation/views/AdminGraduationLayout.vue'),
    read('../src/modules/graduation/views/GraduationStudentListView.vue')
  ])
  const template = layout.match(/<template>([\s\S]*?)<\/template>\s*<script>/)?.[1]
  assert.ok(template, 'the actual module template must be inspected')
  assert.doesNotMatch(template, /gd-page-intro/)
  assert.equal((template.match(/<GraduationBatchStrip\b/g) || []).length, 1, 'retain exactly one canonical batch selector')
  assert.match(template, /class="gd-business-view"/)
  assert.match(template, /v-if="canRenderBusiness"/)
  assert.match(template, /<router-view\b[^>]*:ctx="businessCtx"/)
  assert.match(students, /<ModulePageShell\b/)
  assert.match(students, /:title="pageTitle"/)
  assert.match(students, /:subtitle="pageSubtitle"/)
  assert.match(students, /\{\{ workConclusion \}\}/)
  assert.match(students, /\{\{ workHint \}\}/)
  assert.match(students, /<AppPageGuide guide-key="graduation\.gd-students"/)
})

test('V6 IA evidence identifies actual checkout and rejects runtime source replacement in CI', async (t) => {
  const root = new URL('../../', import.meta.url)
  const paths = [
    'frontend/tests/graduation.v8-ia-contract.test.mjs',
    'frontend/src/modules/graduation/views/AdminGraduationLayout.vue',
    'frontend/src/modules/graduation/views/GraduationStudentListView.vue'
  ]
  const inGithubActions = process.env.GITHUB_ACTIONS === 'true'
  const gitOptions = { cwd: fileURLToPath(root), encoding: 'utf8', timeout: 10000, maxBuffer: 4 * 1024 * 1024 }
  const checkout = inGithubActions ? execFileSync('git', ['rev-parse', 'HEAD'], gitOptions).trim() : 'local-worktree'
  for (const path of paths) {
    const actual = await readFile(new URL(path, root), 'utf8')
    t.diagnostic(JSON.stringify({ contract: 'V6-IA-checkout-v1', checkout, eventSha: process.env.GITHUB_SHA || null, path, sha256: createHash('sha256').update(actual).digest('hex') }))
    if (inGithubActions) {
      const committed = execFileSync('git', ['show', `HEAD:${path}`], gitOptions)
      assert.equal(actual, committed, `${path} changed after checkout; do not attribute this run to unchanged HEAD source`)
    }
  }
})

// Load the real Options API methods without mounting Vue. Component imports are
// inert bindings; no lifecycle hooks or network requests are run by the harness.
async function studentNavigationHarness({ writeEnabled = true, panel = 'roster' } = {}) {
  const source = await read('../src/modules/graduation/views/GraduationStudentListView.vue')
  const script = source.match(/<script\b[^>]*>([\s\S]*?)<\/script>/)?.[1]
  assert.ok(script, 'student ledger must expose its actual Options API script')
  const body = script.replace(/^import\s+[\s\S]*?\s+from\s+(['"])[^'"]+\1[^\S\n]*;?[^\S\n]*$/gm, '')
    .replace(/export\s+default\s+/, 'globalThis.studentOptions = ')
  const sandbox = Object.fromEntries([
    'ModulePageShell', 'ModuleToolbar', 'AdvancedFilter', 'DataTable',
    'StatusTag', 'RiskTag', 'LoadingState', 'ErrorState', 'EmptyState',
    'AppConfirmDialog', 'AppSensitiveText', 'AppExportButton', 'AppPageGuide',
    'AppExcelImportDrawer'
  ].map((name) => [name, {}]))
  vm.runInNewContext(body, sandbox, { timeout: 1000 })
  assert.ok(sandbox.studentOptions?.methods)

  const pushes = []
  const query = { panel, batchId: 'batch-a', source: 'dashboard' }
  const context = {
    writeEnabled,
    activePanel: panel,
    page: 3,
    filters: { keyword: '  张老师  ' },
    batchStore: { selectedBatchId: 'batch-a' },
    selectedIds: ['student-1', 'student-2'],
    importVisible: false,
    $route: { query },
    $router: {
      push(target) { pushes.push(target); return Promise.resolve() },
      resolve({ path, query: routeQuery }) {
        const params = new URLSearchParams()
        for (const [key, value] of Object.entries(routeQuery || {})) {
          if (value != null) params.set(key, String(value))
        }
        return { fullPath: `${path}?${params.toString()}` }
      }
    }
  }
  for (const [name, method] of Object.entries(sandbox.studentOptions.methods)) {
    context[name] = method.bind(context)
  }
  return { context, pushes, query }
}

function assertStudentReturnContext(target, panel = 'roster') {
  assert.equal(target.query.batchId, 'batch-a')
  assert.equal(target.query.returnPanel, panel)
  const returnUrl = new URL(target.query.returnTo, 'https://example.test')
  assert.equal(returnUrl.pathname, '/admin/graduation/students')
  assert.equal(returnUrl.searchParams.get('batchId'), 'batch-a')
  assert.equal(returnUrl.searchParams.get('panel'), panel)
  assert.equal(returnUrl.searchParams.get('page'), '3')
  assert.equal(returnUrl.searchParams.get('keyword'), '张老师')
  assert.equal(returnUrl.searchParams.get('source'), 'dashboard')
}

test('V6 student creation uses the canonical route and preserves batch and list return context', async () => {
  const { context, pushes, query } = await studentNavigationHarness()
  context.onToolbar('create')
  assert.equal(pushes.length, 1)
  assert.equal(pushes[0].path, '/admin/graduation/students/create')
  assertStudentReturnContext(pushes[0])
  assert.deepEqual(query, { panel: 'roster', batchId: 'batch-a', source: 'dashboard' }, 'navigation must not mutate the router query')
})

test('V6 read-only student context cannot initiate creation, import, grouping or archiving', async () => {
  const { context, pushes } = await studentNavigationHarness({ writeEnabled: false })
  let archiveCalls = 0
  context.askBatchArchive = () => { archiveCalls += 1 }
  for (const action of ['create', 'import', 'batchGroup', 'batchArchive']) context.onToolbar(action)
  assert.equal(pushes.length, 0)
  assert.equal(context.importVisible, false)
  assert.equal(archiveCalls, 0)
})

test('V6 student detail and assignment links keep their canonical object and source queue', async () => {
  const { context, pushes } = await studentNavigationHarness({ panel: 'topic' })
  const row = { id: 'student-17' }
  context.openDetail(row)
  context.openAssignTopic(row)
  context.openAdvisor(row)
  context.openGroup(row)
  context.openDefense(row)
  assert.deepEqual(pushes.map((target) => target.path), [
    '/admin/graduation/students/student-17',
    '/admin/graduation/students/student-17/assign-topic',
    '/admin/graduation/mentors/assign/student-17',
    '/admin/graduation/students/student-17/group',
    '/admin/graduation/students/student-17/defense-group'
  ])
  for (const target of pushes) assertStudentReturnContext(target, 'topic')
})

test('V6 batch grouping retains selected IDs and grouping return context', async () => {
  const { context, pushes } = await studentNavigationHarness({ panel: 'grouping' })
  context.onToolbar('batchGroup')
  assert.equal(pushes.length, 1)
  assert.equal(pushes[0].path, '/admin/graduation/students/_batch/group')
  assert.equal(pushes[0].query.ids, 'student-1,student-2')
  assertStudentReturnContext(pushes[0], 'grouping')
})

test('V6 import opens the existing import flow without creating an alternate route', async () => {
  const { context, pushes } = await studentNavigationHarness()
  context.onToolbar('import')
  assert.equal(context.importVisible, true)
  assert.equal(pushes.length, 0)
})
