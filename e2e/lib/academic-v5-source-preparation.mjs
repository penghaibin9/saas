#!/usr/bin/env node
// V5 已有课程与培养方案源数据准备；不计入 R4/A-H 的真实浏览器动作验收。
// 默认只打印离线预览。--execute 仅对本机 8002 正式 API 写入，并逐步留存私有回执。
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../', import.meta.url))
const backend = path.join(root, 'backend')
const base = 'http://127.0.0.1:8002/api/v1'
const academic = '/academic-affairs'
const databaseName = 'student_lifecycle_v5_e2e'

function privatePath(value) {
  assert.ok(value, '必须显式提供私有状态与凭据路径')
  const target = path.resolve(root, value)
  const relative = path.relative(root, target)
  assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative), '私有文件必须位于本仓库')
  const ignored = spawnSync('git', ['check-ignore', '--quiet', '--', relative], { cwd: root, stdio: 'ignore' })
  assert.equal(ignored.status, 0, '私有文件路径必须受当前仓库忽略规则保护')
  return target
}

async function existingPrivateFile(value) {
  const target = privatePath(value)
  const actual = await fs.realpath(target)
  assert.equal(path.normalize(actual).toLowerCase(), path.normalize(target).toLowerCase(), '私有文件不得经符号链接或连接点跳转')
  assert.ok((await fs.stat(target)).isFile(), '私有路径必须是常规文件')
  return target
}

function validateFixture(fixture, credentials) {
  assert.match(String(fixture.prefix || ''), /^v5j_[a-z0-9]{6,12}_$/, '身份回执前缀无效')
  assert.equal(fixture.tenantCode, 'demo')
  assert.equal(String(fixture.tenantId), '1000000000000000001')
  assert.equal(fixture.cohort?.entryYear, 2023)
  assert.equal(fixture.cohort?.expectedGraduateYear, 2026)
  for (const key of ['school', 'schoolReviewer', 'collegeA', 'collegeB']) {
    const account = fixture.accounts?.[key]
    assert.match(String(account?.userId || ''), /^\d+$/, `${key} 用户编号无效`)
    assert.ok(account.loginName && account.contextId && account.roleCode, `${key} 身份不完整`)
    assert.equal(account.roleCode, key.startsWith('college') ? 'COLLEGE_ADMIN' : 'ACADEMIC_ADMIN')
    if (credentials) assert.ok(credentials[account.loginName]?.password, `${key} 私有凭据缺失`)
  }
  for (const key of ['A', 'B']) {
    for (const field of ['collegeId', 'majorId', 'classId']) {
      assert.match(String(fixture.colleges?.[key]?.[field] || ''), /^\d+$/, `${key} ${field} 无效`)
    }
    assert.equal(fixture.colleges[key].studentIds?.length, 2, `${key} 学生身份数量不符`)
  }
}

function planFor(fixture) {
  const seed = Number.parseInt(createHash('sha256').update(fixture.prefix).digest('hex').slice(0, 10), 16) % 1_000_000
  const digits = String(seed).padStart(6, '0')
  const courses = [
    { key: 'aProfessional', college: 'A', code: `VJ${digits}1`, name: `${fixture.prefix}甲学院专业核心`, category: 'MAJOR_CORE', module: '专业核心' },
    { key: 'bProfessional', college: 'B', code: `VJ${digits}2`, name: `${fixture.prefix}乙学院专业核心`, category: 'MAJOR_CORE', module: '专业核心' },
    { key: 'bPublic', college: 'B', code: `VJ${digits}3`, name: `${fixture.prefix}乙学院公共基础`, category: 'PUBLIC_BASIC', module: '公共基础' },
  ]
  const programs = [
    { key: 'A', name: `${fixture.prefix}甲学院2023级培养方案`, courses: courses.slice(0, 1) },
    { key: 'B', name: `${fixture.prefix}乙学院2023级培养方案`, courses: courses.slice(1) },
  ]
  return { courses, programs }
}

// 直接只读 3311 库，再用正式 API 回读同一批随机学院/专业/班级编号。
// /health/ready 不返回实际数据库名，不能单独作为 8002 目标证明。
function assertLocalDatabase(fixture) {
  const code = String.raw`
import json, os, sys
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from scripts.e2e_seed_academic_v5_journey import require_target
from app.core.config import settings
data = json.load(sys.stdin)
raw = require_target(os.environ)
if settings.effective_database_url != raw or not settings.DB_ENABLED or settings.APP_ENV != 'test':
    raise RuntimeError('app_config_mismatch')
engine = create_engine(raw, poolclass=NullPool, hide_parameters=True)
try:
    with engine.connect() as conn:
        conn.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
        if conn.scalar(text('SELECT DATABASE()')) != 'student_lifecycle_v5_e2e':
            raise RuntimeError('database_mismatch')
        for key in ('A', 'B'):
            obj = data['colleges'][key]
            ids = {name: int(obj[name]) for name in ('collegeId', 'majorId', 'classId')}
            params = {**ids, 'tenantId': int(data['tenantId']), 'prefix': data['prefix'] + '%',
                      'grade': '2023', 'classStatus': 'NORMAL'}
            for query in (
                'SELECT id FROM t_college WHERE id=:collegeId AND tenant_id=:tenantId AND code LIKE :prefix AND is_deleted=0',
                'SELECT id FROM t_major WHERE id=:majorId AND college_id=:collegeId AND tenant_id=:tenantId AND code LIKE :prefix AND is_deleted=0',
                'SELECT id FROM t_class WHERE id=:classId AND major_id=:majorId AND tenant_id=:tenantId AND grade=:grade AND class_status=:classStatus AND is_deleted=0',
            ):
                if conn.scalar(text(query), params) is None:
                    raise RuntimeError('fixture_mismatch')
            rows = conn.execute(text('SELECT id FROM t_student_profile WHERE class_id=:classId AND tenant_id=:tenantId AND student_no LIKE :prefix AND is_deleted=0'), params).all()
            if {str(row[0]) for row in rows} != set(obj['studentIds']):
                raise RuntimeError('student_mismatch')
finally:
    engine.dispose()
print('{"ok":true}')
`
  const run = spawnSync(process.env.E2E_V5_PYTHON || 'python', ['-c', code], {
    cwd: backend, input: JSON.stringify(fixture), encoding: 'utf8', timeout: 30_000,
    maxBuffer: 4096, windowsHide: true,
  })
  assert.equal(run.status, 0, '隔离库只读目标核验失败；禁止写入（详细连接信息不输出）')
  assert.equal(JSON.parse(run.stdout).ok, true, '隔离库目标核验未通过')
}

function jwtClaims(token) {
  const parts = String(token).split('.')
  assert.equal(parts.length, 3, '登录未返回规范令牌')
  return JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'))
}

async function request(method, route, token, body, params) {
  assert.ok(route.startsWith('/') && !route.startsWith('//'), '接口路径无效')
  const url = new URL(base + route)
  for (const [key, value] of Object.entries(params || {})) url.searchParams.set(key, String(value))
  const response = await fetch(url, {
    method, redirect: 'manual', signal: AbortSignal.timeout(30_000),
    headers: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  assert.equal(new URL(response.url).origin, new URL(base).origin, '接口目标发生跳转')
  let envelope
  try { envelope = await response.json() } catch { throw new Error(`${method} ${route} 返回非 JSON`) }
  if (response.status !== 200 || envelope?.code !== 0) {
    throw new Error(`${method} ${route} 被拒绝：HTTP ${response.status}，业务码 ${String(envelope?.code ?? '未知')}`)
  }
  return envelope.data
}

function list(data) {
  const rows = data?.items
  assert.ok(Array.isArray(rows), '正式列表结构与预期不符')
  assert.ok(Number(data.total ?? rows.length) <= rows.length, '列表未读全，禁止推断目标不存在')
  return rows
}

async function login(fixture, credentials, role) {
  const account = fixture.accounts[role]
  const data = await request('POST', '/auth/login', '', {
    loginName: account.loginName, password: credentials[account.loginName].password,
    tenantCode: fixture.tenantCode, clientType: 'PC',
  })
  const token = String(data?.accessToken || '')
  const claims = jwtClaims(token)
  assert.equal(String(claims.tenantId), fixture.tenantId)
  assert.equal(String(claims.userId), `db-${account.userId}`)
  assert.equal(claims.currentRoleCode, account.roleCode)
  assert.equal(claims.activeContextId, account.contextId)
  assert.equal(claims.clientType, 'PC')
  const me = await request('GET', '/auth/me', token)
  assert.equal(String(me.userId), `db-${account.userId}`)
  assert.equal(String(me.tenantId), fixture.tenantId)
  assert.equal(me.activeContextId, account.contextId)
  assert.equal(me.currentRole?.roleCode, account.roleCode)
  return token
}

async function assertBackendFixture(fixture, token) {
  for (const key of ['A', 'B']) {
    const obj = fixture.colleges[key]
    const colleges = list(await request('GET', `${academic}/orgs/colleges`, token, undefined,
      { keyword: fixture.prefix, page: 1, pageSize: 200 }))
    assert.equal(colleges.filter(row => String(row.id) === obj.collegeId).length, 1, '8002 学院编号与隔离库不一致')
    const majors = list(await request('GET', `${academic}/orgs/majors`, token, undefined,
      { collegeId: obj.collegeId, keyword: fixture.prefix, page: 1, pageSize: 200 }))
    assert.equal(majors.filter(row => String(row.id) === obj.majorId && String(row.collegeId) === obj.collegeId).length, 1,
      '8002 专业编号与隔离库不一致')
    const classes = list(await request('GET', `${academic}/orgs/classes`, token, undefined,
      { majorId: obj.majorId, grade: '2023', keyword: fixture.prefix, page: 1, pageSize: 200 }))
    assert.equal(classes.filter(row => String(row.id) === obj.classId && String(row.majorId) === obj.majorId).length, 1,
      '8002 班级编号与隔离库不一致')
  }
}

async function assertNoExistingSources(fixture, plan, school) {
  for (const course of plan.courses) {
    const rows = list(await request('GET', `${academic}/courses`, school, undefined,
      { keyword: course.code, page: 1, pageSize: 200 }))
    assert.ok(!rows.some(row => row.courseCode === course.code), '源课程代码已存在；禁止自动接管或重建')
  }
  for (const program of plan.programs) {
    const majorId = fixture.colleges[program.key].majorId
    const rows = list(await request('GET', `${academic}/programs`, school, undefined,
      { majorId, page: 1, pageSize: 200 }))
    assert.ok(!rows.some(row => row.programName === program.name || String(row.gradeYear) === '2023'),
      '本专业 2023 级方案已存在；禁止自动替换正式绑定')
    for (const row of rows) {
      const bindings = (await request('GET', `${academic}/programs/${row.programId}/bindings`, school))?.items
      assert.ok(Array.isArray(bindings), '正式绑定列表结构与预期不符')
      assert.ok(!bindings.some(binding => binding.status === 'ACTIVE' && String(binding.gradeYear) === '2023'),
        '2023 级已有正式绑定；禁止覆盖')
    }
  }
}

async function saveJournal(file, report) {
  const temp = `${file}.tmp`
  await fs.writeFile(temp, JSON.stringify(report, null, 2), { encoding: 'utf8', mode: 0o600 })
  await fs.rename(temp, file)
}

async function writeStep(report, file, step, actor, route, invoke, readBack) {
  assert.equal(report.pending, null, '存在尚未核实的写入，不得继续')
  report.pending = { step, actor, route, sentAt: new Date().toISOString() }
  await saveJournal(file, report)
  const result = await invoke()
  // 即使回读或本地进程随后失败，也保留写请求返回的对象编号，不自动重放。
  report.pending.receipt = result
  await saveJournal(file, report)
  const observed = await readBack(result)
  report.steps.push({ ...report.pending, observed, observedAt: new Date().toISOString() })
  report.pending = null
  await saveJournal(file, report)
  return result
}

async function execute(fixture, credentials, plan, journalFile) {
  for (const key of ['E2E_ALLOW_DESTRUCTIVE_TESTS', 'APP_ENV', 'DEPLOYMENT_MODE', 'DB_ENABLED']) {
    const expected = { E2E_ALLOW_DESTRUCTIVE_TESTS: 'true', APP_ENV: 'test', DEPLOYMENT_MODE: 'local', DB_ENABLED: 'true' }[key]
    assert.equal(process.env[key], expected, `${key} 未指向隔离测试环境`)
  }
  assertLocalDatabase(fixture)
  const tokens = {}
  for (const role of ['school', 'schoolReviewer', 'collegeA', 'collegeB']) tokens[role] = await login(fixture, credentials, role)
  await assertBackendFixture(fixture, tokens.school)
  await assertNoExistingSources(fixture, plan, tokens.school)
  const report = { kind: 'V5_SOURCE_PREPARATION_ONLY', prefix: fixture.prefix, tenantId: fixture.tenantId,
    database: databaseName, api: base, complete: false, pending: null, steps: [], courses: {}, programs: {} }
  const handle = await fs.open(journalFile, 'wx', 0o600)
  try { await handle.writeFile(JSON.stringify(report, null, 2)) } finally { await handle.close() }

  const getCourse = id => request('GET', `${academic}/courses/${id}`, tokens.school)
  const getProgram = id => request('GET', `${academic}/programs/${id}`, tokens.school)
  try {
    for (const course of plan.courses) {
      const ownerCollegeId = fixture.colleges[course.college].collegeId
      const payload = { courseCode: course.code, courseName: course.name, category: course.category,
        nature: 'REQUIRED', credit: 4, hoursTotal: 40, hoursTheory: 40, hoursPractice: 0,
        examMode: 'EXAM', ownerCollegeId }
      const created = await writeStep(report, journalFile, `${course.key}:create`, 'school', `${academic}/courses`,
        () => request('POST', `${academic}/courses`, tokens.school, payload), async result => {
          assert.match(String(result?.courseId || ''), /^\d+$/)
          const row = await getCourse(result.courseId)
          assert.equal(row.courseCode, course.code); assert.equal(row.status, 'DRAFT')
          assert.equal(String(row.ownerCollegeId), ownerCollegeId)
          return { courseId: row.courseId, status: row.status }
        })
      const id = String(created.courseId)
      report.courses[course.key] = { courseId: id, courseCode: course.code }
      await saveJournal(journalFile, report)
      for (const [step, actor, expected] of [
        ['submit', 'school', 'COLLEGE_REVIEW'],
        ['collegeReview', `college${course.college}`, 'ACADEMIC_REVIEW'],
        ['schoolReview', 'schoolReviewer', 'ENABLED'],
      ]) {
        await writeStep(report, journalFile, `${course.key}:${step}`, actor, `${academic}/courses/${id}/${step === 'submit' ? 'submit' : 'review'}`,
          () => request('POST', `${academic}/courses/${id}/${step === 'submit' ? 'submit' : 'review'}`,
            tokens[actor], step === 'submit' ? undefined : { action: 'APPROVE' }), async () => {
            const row = await getCourse(id); assert.equal(row.status, expected)
            return { courseId: id, status: row.status }
          })
      }
    }

    for (const program of plan.programs) {
      const org = fixture.colleges[program.key]
      const created = await writeStep(report, journalFile, `${program.key}:createProgram`, 'school', `${academic}/programs`,
        () => request('POST', `${academic}/programs`, tokens.school, {
          programName: program.name, majorId: org.majorId, gradeYear: '2023', totalCredits: program.courses.length * 4,
        }), async result => {
          assert.match(String(result?.programId || ''), /^\d+$/)
          const row = await getProgram(result.programId)
          assert.equal(row.programName, program.name); assert.equal(row.status, 'DRAFT')
          assert.equal(String(row.majorId), org.majorId)
          return { programId: row.programId, status: row.status }
        })
      const id = String(created.programId)
      report.programs[program.key] = { programId: id, majorId: org.majorId, classId: org.classId }
      await saveJournal(journalFile, report)
      for (const course of program.courses) {
        const courseId = report.courses[course.key].courseId
        await writeStep(report, journalFile, `${program.key}:add:${course.key}`, 'school', `${academic}/programs/${id}/courses`,
          () => request('POST', `${academic}/programs/${id}/courses`, tokens.school, {
            courseId, courseName: course.name, openTermNo: 6, module: course.module, credit: 4,
            formationMode: 'ADMIN_FIXED',
          }), async result => {
            const row = await getProgram(id)
            assert.equal(row.courses.filter(item => String(item.programCourseId) === String(result.programCourseId)
              && String(item.courseId) === courseId && item.openTermNo === 6).length, 1)
            return { programCourseId: String(result.programCourseId), courseId }
          })
      }
      const items = [...new Set(program.courses.map(course => course.module))].map(module => ({
        module, creditTarget: program.courses.filter(course => course.module === module).length * 4,
      }))
      await writeStep(report, journalFile, `${program.key}:credits`, 'school', `${academic}/programs/${id}/credit-requirements`,
        () => request('PUT', `${academic}/programs/${id}/credit-requirements`, tokens.school, { items }), async () => {
          const data = await request('GET', `${academic}/programs/${id}/credit-requirements`, tokens.school)
          assert.deepEqual(data.items.map(item => [item.module, Number(item.creditTarget)]).sort(),
            items.map(item => [item.module, item.creditTarget]).sort())
          return { items: data.items.map(item => ({ module: item.module, creditTarget: item.creditTarget })) }
        })
      await writeStep(report, journalFile, `${program.key}:graduationRequirement`, 'school',
        `${academic}/programs/${id}/graduation-requirements`,
        () => request('POST', `${academic}/programs/${id}/graduation-requirements`, tokens.school,
          { category: 'ABILITY', content: `${program.name}课程考核达标` }), async result => {
          const data = await request('GET', `${academic}/programs/${id}/graduation-requirements`, tokens.school)
          assert.equal(data.items.filter(row => String(row.requirementId) === String(result.requirementId)).length, 1)
          return { requirementId: String(result.requirementId) }
        })
      for (const [step, actor, expected] of [
        ['submit', 'school', 'COLLEGE_REVIEW'],
        ['collegeReview', `college${program.key}`, 'ACADEMIC_REVIEW'],
        ['schoolReview', 'schoolReviewer', 'PUBLISHED'],
      ]) {
        await writeStep(report, journalFile, `${program.key}:${step}`, actor, `${academic}/programs/${id}/${step === 'submit' ? 'submit' : 'review'}`,
          () => request('POST', `${academic}/programs/${id}/${step === 'submit' ? 'submit' : 'review'}`,
            tokens[actor], step === 'submit' ? undefined : { action: 'APPROVE' }), async () => {
            const row = await getProgram(id); assert.equal(row.status, expected)
            return { programId: id, status: row.status }
          })
      }
      await writeStep(report, journalFile, `${program.key}:bind`, 'school', `${academic}/programs/${id}/bind`,
        () => request('POST', `${academic}/programs/${id}/bind`, tokens.school,
          { gradeYear: '2023', classId: org.classId }), async () => {
          const data = await request('GET', `${academic}/programs/${id}/bindings`, tokens.school)
          assert.equal(data.items.filter(row => row.status === 'ACTIVE' && String(row.gradeYear) === '2023'
            && String(row.classId) === org.classId).length, 1)
          const row = await getProgram(id); assert.equal(row.status, 'ENABLED')
          return { programId: id, classId: org.classId, status: row.status }
        })
    }
    report.complete = true
    await saveJournal(journalFile, report)
    console.log(JSON.stringify({ executed: true, complete: true, journalFile,
      courseIds: Object.fromEntries(Object.entries(report.courses).map(([key, value]) => [key, value.courseId])),
      programIds: Object.fromEntries(Object.entries(report.programs).map(([key, value]) => [key, value.programId])) }, null, 2))
  } catch (error) {
    console.error(`源数据准备停止：${error.message}。核对私有回执 ${journalFile} 的 pending 后再决定如何恢复；禁止盲目重跑。`)
    process.exitCode = 1
  }
}

async function main() {
  const args = process.argv.slice(2)
  assert.ok(args.every(arg => arg === '--execute'), '仅接受可选的 --execute 参数；路径由 E2E_V5_STATE/CREDENTIALS 指定')
  const executeMode = args.includes('--execute')
  const stateFile = await existingPrivateFile(process.env.E2E_V5_STATE)
  const credentialFile = await existingPrivateFile(process.env.E2E_V5_CREDENTIALS)
  assert.notEqual(stateFile, credentialFile, '状态与凭据文件必须分开')
  const fixture = JSON.parse(await fs.readFile(stateFile, 'utf8'))
  const credentials = executeMode ? JSON.parse(await fs.readFile(credentialFile, 'utf8')) : null
  validateFixture(fixture, credentials)
  const journalFile = privatePath(`${stateFile}.source-preparation.json`)
  assert.equal(path.extname(journalFile), '.json')
  const plan = planFor(fixture)
  if (!executeMode) {
    console.log(JSON.stringify({ executed: false, api: base, database: databaseName, prefix: fixture.prefix,
      journalFile, courses: plan.courses.map(row => ({ code: row.code, name: row.name, ownerCollegeId: fixture.colleges[row.college].collegeId })),
      programs: plan.programs.map(row => ({ name: row.name, majorId: fixture.colleges[row.key].majorId,
        classId: fixture.colleges[row.key].classId, gradeYear: '2023', openTermNo: 6,
        totalCredits: row.courses.length * 4 })) }, null, 2))
    return
  }
  try {
    await fs.stat(journalFile)
    throw new Error('该前置准备已有私有回执；禁止自动重复写入')
  } catch (error) { if (error.code !== 'ENOENT') throw error }
  await execute(fixture, credentials, plan, journalFile)
}

main().catch(() => { console.error('源数据准备未通过安全核验；未输出敏感内容，未自动重试。'); process.exitCode = 1 })
