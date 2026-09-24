import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, ref, reactive, watch, nextTick, effectScope } from 'vue'
import {
  activeWorkspacePage,
  workspaceRouteOwner
} from '../src/components/workspace/workspaceRouting.js'
import { workspacePages } from '../src/components/workspace/teacherWorkspace.js'
import { getVisibleNavPlan } from '../src/config/navPlan.js'

const tree = () => [
  {
    id: '90071992547409931',
    type: 'COLLEGE',
    name: '甲学院',
    children: [
      {
        id: '90071992547409931',
        type: 'MAJOR',
        name: '软件技术',
        children: Array.from({ length: 18 }, (_, i) => ({
          id: String(i + 1),
          type: 'CLASS',
          name: `软件${i + 1}班`,
          code: `C${i + 1}`
        }))
      }
    ]
  },
  { id: '2', type: 'COLLEGE', name: '乙学院', children: [] }
]
const allowed = () => ({
  code: 0,
  data: {
    canDisable: true,
    previewToken: 'signed-test-preview',
    nodeVersion: 7,
    previewExpiresIn: 300,
    affectedMajors: 0,
    affectedClasses: 0,
    affectedStudents: 0,
    affectedAssignments: 0
  }
})
const deferred = () => {
  let resolve, reject
  const promise = new Promise((a, b) => {
    resolve = a
    reject = b
  })
  return { promise, resolve, reject }
}
function workspace(
  t,
  {
    read = async () => allowed(),
    write = async () => ({}),
    org = 'COLLEGE:2',
    permission = true
  } = {}
) {
  const props = reactive({
    tree: tree(),
    refreshing: false,
    ctx: {
      ctxKey: 'school-admin',
      permissionActions: { deprecateOrg: { visible: true, allowed: permission } }
    }
  })
  const route = reactive({ query: { org } }),
    writes = [],
    events = []
  let clock = 1000000,
    tick
  const scope = effectScope()
  const sandbox = {
    computed,
    ref,
    watch,
    defineProps: () => props,
    defineEmits: () => (name) => events.push(name),
    useRoute: () => route,
    useRouter: () => ({
      replace: async ({ query }) => {
        route.query = query
        await nextTick()
      },
      push: async ({ query }) => {
        route.query = query
        await nextTick()
      }
    }),
    onBeforeUnmount: () => {},
    setInterval: (cb) => {
      tick = cb
      return 1
    },
    clearInterval: () => {},
    Date: { now: () => clock },
    systemApi: { getOrgNodeImpact: read },
    systemP1ClosureApi: {
      deprecateOrgNodeWithPreview: async (...args) => {
        writes.push(args)
        return write(...args)
      }
    }
  }
  const source = readFileSync(
    new URL('../src/modules/system/components/SystemOrgWorkspace.vue', import.meta.url),
    'utf8'
  )
    .match(/<script setup>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?$/gm, '')
  scope.run(() =>
    vm.runInNewContext(
      source +
        '\n result={nodes,selected,visibleNodes,search,childSearch,children,page,pageRows,selectedKey,selectNode,startImpact,canConfirm,impact,impactOpen,impactError,confirmOpen,deprecate,completed}',
      sandbox
    )
  )
  t.after(() => scope.stop())
  return {
    ...sandbox.result,
    props,
    route,
    writes,
    events,
    advance: (ms) => {
      clock += ms
      tick()
    }
  }
}

test('tree keys preserve large IDs and distinguish college/major with identical IDs', (t) => {
  const w = workspace(t, { org: 'MAJOR:90071992547409931' })
  assert.equal(w.selected.value.name, '软件技术')
  assert.equal(w.children.value.length, 18)
  assert.equal(w.pageRows.value.length, 10)
  w.page.value = 2
  assert.equal(w.pageRows.value.length, 8)
  w.search.value = '软件18班'
  assert.deepEqual(
    Array.from(w.visibleNodes.value, (n) => n.name),
    ['甲学院', '软件技术', '软件18班']
  )
})
test('category list scopes to requested type, then selected object scopes to direct children', async (t) => {
  const w = workspace(t, { org: '' })
  w.route.query = { tab: 'major' }
  await nextTick()
  assert.equal(w.children.value.length, 1)
  assert.equal(w.children.value[0].name, '软件技术')
  w.selectNode(w.children.value[0])
  await nextTick()
  assert.equal(w.children.value.length, 18)
})
test('blocked impact and read-only permissions cannot submit', async (t) => {
  const w = workspace(t, {
    read: async () => ({
      code: 0,
      data: { ...allowed().data, canDisable: false, affectedStudents: 942 }
    })
  })
  await w.startImpact()
  await w.deprecate({ reason: '不得提交' })
  assert.equal(w.canConfirm.value, false)
  assert.equal(w.writes.length, 0)
  const view = workspace(t, { permission: false })
  await view.startImpact()
  assert.ok(view.impact.value)
  assert.equal(view.canConfirm.value, false)
})
test('selection drops a late impact response and clears confirmation', async (t) => {
  const request = deferred()
  const w = workspace(t, { read: () => request.promise })
  const pending = w.startImpact()
  w.selectNode(w.nodes.value[0])
  await nextTick()
  request.resolve(allowed())
  await pending
  assert.equal(w.impact.value, null)
  assert.equal(w.canConfirm.value, false)
  assert.equal(w.impactOpen.value, false)
})
test('expiry, data refresh and role replacement each invalidate the preview', async (t) => {
  const w = workspace(t)
  await w.startImpact()
  assert.equal(w.canConfirm.value, true)
  w.advance(300000)
  assert.equal(w.canConfirm.value, false)
  await w.startImpact()
  w.props.refreshing = true
  await nextTick()
  assert.equal(w.impact.value, null)
  w.props.refreshing = false
  await nextTick()
  await w.startImpact()
  w.props.ctx = { ctxKey: 'another-school', permissionActions: {} }
  await nextTick()
  assert.equal(w.impact.value, null)
  assert.equal(w.selectedKey.value, '')
})
test('a zero TTL or incomplete preview never permits the write', async (t) => {
  for (const data of [
    { ...allowed().data, previewExpiresIn: 0 },
    { ...allowed().data, previewToken: '' },
    { ...allowed().data, nodeVersion: null }
  ]) {
    const w = workspace(t, { read: async () => ({ code: 0, data }) })
    await w.startImpact()
    assert.equal(w.canConfirm.value, false)
  }
})
test('duplicate submit consumes signed preview once and waits for real completion', async (t) => {
  const request = deferred()
  const w = workspace(t, { write: () => request.promise })
  await w.startImpact()
  const pending = w.deprecate({ reason: '隔离测试组织已完成验收' })
  await w.deprecate({ reason: '重复提交' })
  assert.equal(w.writes.length, 1)
  assert.equal(w.writes[0][0], '2')
  assert.equal(w.writes[0][1].expectedVersion, 7)
  assert.equal(w.writes[0][1].previewToken, 'signed-test-preview')
  assert.equal(w.completed.value, '')
  request.resolve({ id: '2', status: 'DISABLED' })
  await pending
  assert.match(w.completed.value, /乙学院.*已作废/)
  assert.ok(w.events.includes('refresh'))
})
test('conflict preserves explicit failure and cannot automatically retry a consumed preview', async (t) => {
  const w = workspace(t, {
    write: async () => {
      throw new Error('组织版本已变化，请重新检查')
    }
  })
  await w.startImpact()
  await w.deprecate({ reason: '测试冲突原因' })
  await w.deprecate({ reason: '不可自动重试' })
  assert.equal(w.writes.length, 1)
  assert.match(w.impactError.value, /版本已变化/)
  assert.equal(w.completed.value, '')
  assert.equal(w.canConfirm.value, false)
})
test('organization root and object deep links retain menu ownership without permission widening', () => {
  const modules = getVisibleNavPlan({ permissionPatterns: ['systemAdmin.org.view'] }).find(
    (g) => g.key === 'system'
  ).children
  const pages = workspacePages(modules)
  for (const path of [
    '/admin/system/org',
    '/admin/system/org?tab=major&org=MAJOR%3A42',
    '/admin/system/org?tab=versions'
  ]) {
    const route = {
      path: '/admin/system/org',
      fullPath: path,
      query: Object.fromEntries(new URL(path, 'http://localhost').searchParams)
    }
    assert.equal(workspaceRouteOwner(route.path, path).modKey, 'sys-org')
    assert.ok(activeWorkspacePage(pages, route, 'sys-org'))
  }
})
