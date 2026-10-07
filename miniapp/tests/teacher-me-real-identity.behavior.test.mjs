import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../src/pages/teacher/me/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*$/gm, '')
  .replace('export default', 'module.exports =')

function mount({ response, session, generation = () => 1 }) {
  const context = {
    module: { exports: {} },
    ENV: { useMock: false },
    currentSessionGeneration: generation,
    useSessionStore: () => session,
    me: response,
    normalizeError: () => ({ pageState: 'error' }),
    go() {}, relaunch() {}, toast() {},
  }
  vm.runInNewContext(script, context)
  const options = context.module.exports
  const page = { ...options.data() }
  for (const [name, method] of Object.entries(options.methods)) page[name] = method.bind(page)
  return { page, options }
}

function teacherSession() {
  return {
    isTeacher: true,
    mockUser: { name: '', tenantName: '' },
    roleConfig: { label: '教务老师' },
    dataScopeText: '本学院范围',
    applyRealUser(identity) {
      this.mockUser = { name: identity.realName, tenantName: '测试学校' }
    },
  }
}

test('我的页只展示本次服务端核验的真实岗位与范围', async () => {
  const identity = {
    realName: '李老师',
    currentRole: { roleCode: 'ACADEMIC_TEACHER', roleName: '任课教师', dataScope: 'ASSIGNED', scopeLabel: '本人教学任务' },
    contexts: [{ contextId: 'teacher' }, { contextId: 'mentor' }],
  }
  const { page } = mount({ response: async () => identity, session: teacherSession() })
  await page.load()
  assert.equal(page.state, 'ready')
  assert.equal(page.user.name, '李老师')
  assert.equal(page.roleName, '任课教师')
  assert.equal(page.dataScopeText, '本人教学任务')
  assert.equal(page.identityCount, 2)
  assert.match(source, /\{\{ roleName \}\}/)
  assert.doesNotMatch(source, /\{\{ roleConfig\.label \}\}|session\.dataScopeText/)
})

test('后端未提供中文说明时，不把角色编码或静态学院范围冒充真实授权', async () => {
  const { page } = mount({
    response: async () => ({ realName: '李老师', currentRole: { roleCode: 'ACADEMIC_TEACHER', roleName: 'ACADEMIC_TEACHER', dataScope: 'ASSIGNED' } }),
    session: teacherSession(),
  })
  await page.load()
  assert.equal(page.roleName, '当前教师身份')
  assert.equal(page.dataScopeText, '')
  assert.match(source, /dataScopeText \|\| '以当前业务授权范围为准'/)
})

test('重新核验期间清掉旧账号内容，失败时不显示旧岗位和范围', async () => {
  let rejectRequest
  const session = teacherSession()
  let calls = 0
  const { page } = mount({
    session,
    response: () => ++calls === 1
      ? Promise.resolve({ realName: '甲老师', currentRole: { roleName: '任课教师', scopeLabel: '本人教学任务' } })
      : new Promise((_, reject) => { rejectRequest = reject }),
  })
  await page.load()
  const pending = page.load()
  assert.equal(page.state, 'loading')
  assert.equal(page.roleName, '')
  assert.equal(page.dataScopeText, '')
  assert.equal(page.user.name, undefined)
  rejectRequest(new Error('网络失败'))
  await pending
  assert.equal(page.state, 'error')
  assert.equal(page.roleName, '')
})

test('切换身份后迟到的旧核验结果不能替换当前真实说明', async () => {
  const pending = []
  let generation = 1
  const { page } = mount({
    session: teacherSession(),
    generation: () => generation,
    response: () => new Promise(resolve => pending.push(resolve)),
  })
  const oldLoad = page.load()
  generation = 2
  const newLoad = page.load()
  pending[1]({ realName: '乙老师', currentRole: { roleName: '辅导员', scopeLabel: '本人所带班级学生' } })
  await newLoad
  pending[0]({ realName: '甲老师', currentRole: { roleName: '任课教师', scopeLabel: '本人教学任务' } })
  await oldLoad
  assert.equal(page.user.name, '乙老师')
  assert.equal(page.roleName, '辅导员')
  assert.equal(page.dataScopeText, '本人所带班级学生')
})

const studentSource = readFileSync(new URL('../src/pages/student/me/index.vue', import.meta.url), 'utf8')
const studentScript = studentSource.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*$/gm, '').replace('export default', 'module.exports =')
const studentIdentity = (name = '验收学生') => ({
  tenantId: '1000000000000000007', userId: 'db-9007199254740993123', activeContextId: 'student-context',
  realName: name, currentRole: { roleCode: 'STUDENT' },
})
const studentProfile = () => ({
  _real: true, _empty: false, base: { name: '验收学生', studentNo: '2026091201', idCard: '不应投影' },
  org: { className: '验收班' }, contact: { phone: '不应投影' },
  _identity: { studentId: '9007199254740993999', studentNo: '2026091201', name: '验收学生' },
})
// 直接执行现有会话回填方法，避免以测试替身假装资料已同步。
const sessionSource = readFileSync(new URL('../src/stores/session.js', import.meta.url), 'utf8')
const studentHydration = vm.runInNewContext(`({${sessionSource.slice(
  sessionSource.indexOf('    setStudentIdentity(p) {'), sessionSource.indexOf('    async switchRole(roleKey) {'),
)}})`)
function mountStudent({ response, generation = () => 1, profile = async () => studentProfile(), forceGate = () => false }) {
  const session = {
    realUser: null, currentRole: 'student', identity: {}, mockUser: {}, persistedIdentityVerified: false,
    ...studentHydration, persist() {},
    applyCount: 0, mustChangePassword: false,
    applyRealUser(identity) {
      this.applyCount++; this.realUser = identity; this.persistedIdentityVerified = true
      this.currentRole = identity.currentRole.roleCode === 'STUDENT' ? 'student' : 'academic'
      this.mockUser = { name: identity.realName }
      this.identity = {}
      this.mustChangePassword = !!identity.user?.mustChangePassword
    },
  }
  const redirects = [], profileCalls = []
  const context = {
    module: { exports: {} }, ENV: { useMock: false }, useSessionStore: () => session,
    currentSessionGeneration: generation, me: response, getStatusBarHeight: () => 20,
    normalizeError: error => ({ pageState: error.pageState || 'error' }),
    FORCE_PASSWORD_CHANGE_ROUTE: '/pages/common/change-password/index?forced=1',
    forcePasswordChangeRequired: forceGate,
    relaunch: route => redirects.push(route), go() {}, toast() {},
    studentApi: { getProfile: () => { profileCalls.push(1); return profile() } },
  }
  vm.runInNewContext(studentScript, context)
  const options = context.module.exports, page = { ...options.data() }
  for (const [name, method] of Object.entries(options.methods)) page[name] = method.bind(page)
  return { page, options, session, redirects, profileCalls, show: () => options.onShow.call(page) }
}

test('学生我的冷刷新先核验本人，再显示真实姓名和学号', async () => {
  let resolve, calls = 0
  const mounted = mountStudent({ response: () => { calls++; return new Promise(done => { resolve = done }) } })
  const loading = mounted.show()
  assert.equal(calls, 1)
  assert.equal(mounted.page.state, 'loading')
  assert.equal(mounted.page.user.name, undefined)
  resolve(studentIdentity()); await loading
  assert.equal(mounted.page.state, 'ready')
  assert.equal(mounted.page.user.name, '验收学生')
  assert.equal(mounted.page.user.studentNo, '2026091201')
  assert.equal(mounted.page.user.className, '验收班')
  assert.equal(mounted.page.user.contact, undefined)
  assert.equal(mounted.page.user.idCard, undefined)
  assert.equal(mounted.session.realUser.userId, 'db-9007199254740993123')
  assert.equal(mounted.session.identity.studentId, '9007199254740993999')
  assert.equal(mounted.session.identity.studentNo, '2026091201')
  assert.equal(mounted.session.mockUser.className, '验收班')
  assert.equal(mounted.session.mockUser.contact, undefined)
  assert.equal(mounted.session.mockUser.idCard, undefined)
})

test('学生我的不完整身份不能进入个人成功页', async () => {
  const identity = studentIdentity(); delete identity.activeContextId
  const mounted = mountStudent({ response: async () => identity })
  await mounted.show()
  assert.equal(mounted.page.state, 'error')
  assert.equal(mounted.session.applyCount, 0)
  assert.equal(mounted.profileCalls.length, 0)
  assert.equal(mounted.page.user.name, undefined)
})

test('教师身份进入学生我的页被拒绝，不应用教师私有投影', async () => {
  const identity = studentIdentity('教师'); identity.currentRole.roleCode = 'ACADEMIC_TEACHER'
  const mounted = mountStudent({ response: async () => identity })
  await mounted.show()
  assert.equal(mounted.page.state, 'forbidden')
  assert.equal(mounted.session.applyCount, 0)
  assert.equal(mounted.profileCalls.length, 0)
  assert.equal(mounted.page.user.name, undefined)
})

test('学生我的核验失败清旧姓名，正常重试恢复；失效和无权保留对应状态', async () => {
  let response = studentIdentity()
  const mounted = mountStudent({ response: async () => { if (response instanceof Error) throw response; return response } })
  await mounted.show()
  for (const state of ['error', 'unauthorized', 'forbidden']) {
    response = Object.assign(new Error('核验失败'), { pageState: state })
    await mounted.page.load()
    assert.equal(mounted.page.state, state)
    assert.equal(mounted.page.user.name, undefined)
  }
  response = studentIdentity('重试学生'); await mounted.page.load()
  assert.equal(mounted.page.state, 'ready')
  assert.equal(mounted.page.user.name, '重试学生')
  const empty = mountStudent({ response: async () => studentIdentity(), profile: async () => ({ _real: false, _empty: true, _identity: null }) })
  await empty.show()
  assert.equal(empty.page.state, 'error')
  assert.equal(empty.page.user.name, undefined)
})

test('学生我的隐藏和卸载清私有投影，旧请求不能复活', async () => {
  const pending = []
  const mounted = mountStudent({ response: () => new Promise(resolve => pending.push(resolve)) })
  const first = mounted.show(); pending[0](studentIdentity()); await first
  mounted.options.onHide.call(mounted.page)
  assert.equal(mounted.page.user.name, undefined)
  const late = mounted.show(); mounted.options.onUnload.call(mounted.page)
  pending[1](studentIdentity('迟到学生')); await late
  assert.equal(mounted.page.user.name, undefined)
  assert.equal(mounted.session.applyCount, 1)
  let resolveProfile, profileStarted
  const started = new Promise(resolve => { profileStarted = resolve })
  const hidden = mountStudent({ response: async () => studentIdentity(), profile: () => {
    profileStarted(); return new Promise(resolve => { resolveProfile = resolve })
  } })
  const profileLoad = hidden.show(); await started
  assert.equal(hidden.profileCalls.length, 1)
  hidden.options.onHide.call(hidden.page)
  resolveProfile(studentProfile()); await profileLoad
  assert.equal(hidden.session.applyCount, 0)
  assert.equal(hidden.page.user.name, undefined)
})

test('学生我的会话代数及同会话上下文切换均丢弃旧核验', async () => {
  for (const switchContext of [false, true]) {
    let generation = 1, resolve
    const mounted = mountStudent({ generation: () => generation, response: () => new Promise(done => { resolve = done }) })
    const loading = mounted.show()
    if (switchContext) mounted.session.realUser = { ...studentIdentity('新身份'), activeContextId: 'another-context' }
    else generation++
    resolve(studentIdentity('旧学生')); await loading
    assert.equal(mounted.session.applyCount, 0)
    assert.equal(mounted.page.user.name, undefined)
  }
})

test('学生我的重入核验只消费最新响应', async () => {
  const pending = []
  const mounted = mountStudent({ response: () => new Promise(resolve => pending.push(resolve)) })
  const old = mounted.show(), current = mounted.page.load()
  pending[1](studentIdentity('新学生')); await current
  pending[0](studentIdentity('旧学生')); await old
  assert.equal(mounted.page.user.name, '新学生')
  assert.equal(mounted.session.applyCount, 1)
})

test('真实me不含改密字段，既有会话或公开门禁仍阻止资料读取和身份覆盖', async () => {
  for (const storedGate of [false, true]) {
    const mounted = mountStudent({ response: async () => studentIdentity(), forceGate: () => storedGate })
    mounted.session.mustChangePassword = !storedGate
    await mounted.show()
    assert.deepEqual(mounted.redirects, ['/pages/common/change-password/index?forced=1'])
    assert.notEqual(mounted.page.state, 'ready')
    assert.equal(mounted.page.user.name, undefined)
    assert.equal(mounted.profileCalls.length, 0)
    assert.equal(mounted.session.applyCount, 0)
    assert.equal(mounted.session.mustChangePassword, !storedGate)
  }
})
