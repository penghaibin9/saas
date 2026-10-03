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
