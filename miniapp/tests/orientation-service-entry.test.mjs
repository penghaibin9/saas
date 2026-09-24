import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ROLE, roleConfigs, roleKeyFromBackendRole } from '../src/config/roles.config.js'
import { teacherServices, teacherVisual } from '../src/services/teacherServiceCatalog.mjs'

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const manifest = JSON.parse(read('src/pages.json'))
const routes = new Set(manifest.subPackages.flatMap(pkg => pkg.pages.map(page => `/${pkg.root}/${page.path}`)))

function component(path, dependencies) {
  const script = read(path).match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'return')
  const options = new Function(...Object.keys(dependencies), script)(...Object.values(dependencies))
  const page = { ...options.data(), ...options.methods }
  for (const [key, getter] of Object.entries(options.computed || {})) {
    Object.defineProperty(page, key, { get: () => getter.call(page) })
  }
  return page
}

test('school and affairs role aliases can find and open the existing orientation workspace from service hall', async () => {
  for (const backendRole of ['SCHOOL_ADMIN', 'STUDENT_AFFAIRS_ADMIN', 'STUDENT_AFFAIRS', 'SA_ADMIN']) {
    const currentRole = roleKeyFromBackendRole(backendRole)
    const session = { currentRole, isTeacher: true, roleConfig: roleConfigs[currentRole], applyRealUser() {} }
    const navigated = []
    const page = component('src/pages/teacher/services/index.vue', {
      useSessionStore: () => session, me: async () => ({ currentRole: { roleCode: backendRole } }),
      currentSessionGeneration: () => 1, teacherServices, teacherVisual,
      normalizeError: () => ({ pageState: 'error' }), go: path => navigated.push(path), toast() {},
    })
    await page.load()
    assert.equal(page.state, 'ready')
    page.keyword = '迎新'
    assert.equal(page.groups.length, 1)
    assert.equal(page.groups[0].items.length, 1)
    const entry = page.groups[0].items[0]
    assert.equal(entry.label, '迎新办理')
    assert.equal(entry.path, '/pages/teacher/orientation/dashboard/index')
    assert.ok(routes.has(entry.path))
    page.open(entry)
    assert.deepEqual(navigated, [entry.path])
    assert.deepEqual(session.roleConfig.permissionActions, ['approval.handle'], 'Entry must not grant a business permission')
    session.currentRole = ROLE.EMPLOYMENT
    page.open(entry)
    assert.equal(navigated.length, 1, 'Previous role entry must stop navigating after an identity switch')
  }
})

test('existing orientation dashboard reaches real worklist, onsite verification and green-channel pages', () => {
  const navigated = []
  const dashboard = component('src/pages/teacher/orientation/dashboard/index.vue', {
    uni: { navigateTo: ({ url }) => navigated.push(url) }, teacherApi: {}, normalizeError() {},
  })
  dashboard.d = { batchId: '18', batchName: '迎新批次' }
  dashboard.goWorklist()
  dashboard.goVerify()
  dashboard.goGc()
  assert.deepEqual(navigated, [
    '/pages/teacher/orientation/worklist/index?batchId=18&batchName=' + encodeURIComponent('迎新批次'),
    '/pages/teacher/orientation/verify/index',
    '/pages/teacher/orientation/green-channel/index?batchId=18&batchName=' + encodeURIComponent('迎新批次'),
  ])
  assert.ok(navigated.every(path => routes.has(path.split('?')[0])))
  for (const role of [ROLE.EMPLOYMENT, ROLE.DORM_MANAGER, ROLE.ACADEMIC]) {
    assert.equal(teacherServices(roleConfigs[role], role).some(item => item.key === 'orientationDashboard'), false)
  }
})

test('service hall identity failures do not retain an orientation entry from the previous session', async () => {
  const page = component('src/pages/teacher/services/index.vue', {
    useSessionStore: () => ({ currentRole: ROLE.SCHOOL_ADMIN }),
    me: async () => { throw new Error('登录会话已失效') },
    currentSessionGeneration: () => 1, teacherServices, teacherVisual,
    normalizeError: () => ({ pageState: 'error' }), go() {}, toast() {},
  })
  page.services = teacherServices(roleConfigs[ROLE.SCHOOL_ADMIN], ROLE.SCHOOL_ADMIN)
  await page.load()
  assert.equal(page.state, 'error')
  assert.deepEqual(page.services, [])
})
