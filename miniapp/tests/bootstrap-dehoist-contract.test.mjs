import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve, join, relative } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const mainJs = read('src/main.js')
const viteConfig = read('../miniapp/vite.config.js')
const finalizer = read('scripts/finalize-mp-weixin-release.mjs')
const studentInstaller = read('src/services/mobilePerformanceInstaller.student.js')
const teacherInstaller = read('src/services/mobilePerformanceInstaller.teacher.js')

// 主包源码根：这些目录/文件永远在主包里，一旦静态依赖某一端的 API 或 mock 图，
// 分包瘦身就被重新抵消（V3 深审 P0-01）。
const MAIN_PACKAGE_SOURCES = ['src/pages/login', 'src/pages/common', 'src/pages/role-switch']
const MAIN_PACKAGE_FILES = ['src/App.vue', 'src/main.js']

function collect(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) collect(full, acc)
    else if (/\.(vue|js|mjs)$/.test(entry)) acc.push(full)
  }
  return acc
}

function mainPackageFiles() {
  const files = []
  for (const dir of MAIN_PACKAGE_SOURCES) collect(resolve(root, dir), files)
  for (const file of MAIN_PACKAGE_FILES) files.push(resolve(root, file))
  return files
}

test('S1.5-G1 旧的全局 mobilePerformanceInstaller 已删除', () => {
  assert.equal(
    existsSync(resolve(root, 'src/services/mobilePerformanceInstaller.js')),
    false,
    '全局安装器必须拆成 .student / .teacher 两个侧向安装器'
  )
})

test('S1.5-G1 main.js 不再全局安装任何一端的高频接口适配', () => {
  assert.doesNotMatch(mainJs, /import\s+['"][^'"]*mobilePerformanceInstaller/)
  assert.doesNotMatch(mainJs, /from\s+['"][^'"]*(studentApi|teacherApi)['"]/)
  assert.doesNotMatch(mainJs, /['"]@\/mock/)
})

test('S1.5-G1 主包页面不得静态依赖 studentApi / teacherApi / @mock', () => {
  const offenders = []
  for (const file of mainPackageFiles()) {
    const source = readFileSync(file, 'utf8')
    for (const match of source.matchAll(/from\s+['"]([^'"]+)['"]/g)) {
      const specifier = match[1]
      if (/(^|\/)(studentApi|teacherApi)$/.test(specifier) || specifier.startsWith('@/mock')) {
        offenders.push(`${relative(root, file)} -> ${specifier}`)
      }
    }
  }
  assert.deepEqual(offenders, [], `主包源码把某一端依赖重新提升进主包:\n${offenders.join('\n')}`)
})

test('S1.5-G1 侧向安装器是幂等的显式安装函数', () => {
  for (const [name, source] of [['student', studentInstaller], ['teacher', teacherInstaller]]) {
    const fn = name === 'student' ? 'ensureStudentPerformanceApi' : 'ensureTeacherPerformanceApi'
    assert.match(source, new RegExp(`export function ${fn}\\(`), `${name} 安装器必须导出 ${fn}`)
    assert.match(source, /if \(installed\) return/, `${name} 安装器必须幂等`)
  }
  // 学生安装器不得触碰教师 API，反之亦然。
  assert.doesNotMatch(studentInstaller, /teacherApi/)
  assert.doesNotMatch(teacherInstaller, /studentApi/)
})

test('S1.5-G1 侧向安装器只被对应分包页面导入', () => {
  const wrong = []
  for (const file of collect(resolve(root, 'src'))) {
    const source = readFileSync(file, 'utf8')
    const relPath = relative(root, file).split('\\').join('/')
    if (/mobilePerformanceInstaller\.student/.test(source) && !/^src\/(pages\/student|services)\//.test(relPath)) {
      wrong.push(`${relPath} 导入了学生安装器`)
    }
    if (/mobilePerformanceInstaller\.teacher/.test(source) && !/^src\/(pages\/teacher|services)\//.test(relPath)) {
      wrong.push(`${relPath} 导入了教师安装器`)
    }
  }
  assert.deepEqual(wrong, [], wrong.join('\n'))
})

test('S1.5-G1 使用高频接口的页面必须先显式安装', () => {
  const required = [
    ['src/pages/teacher/workbench/index.vue', 'ensureTeacherPerformanceApi', 'getWorkbench'],
    ['src/pages/teacher/todos/index.vue', 'ensureTeacherPerformanceApi', 'getTodosPage'],
    ['src/pages/teacher/risk-students/index.vue', 'ensureTeacherPerformanceApi', 'getRiskStudentsPage'],
    ['src/pages/student/messages/index.vue', 'ensureStudentPerformanceApi', 'getMessagesPage']
  ]
  for (const [file, installer, method] of required) {
    const source = read(file)
    assert.match(source, new RegExp(`\\.${method}\\(`), `${file} 应仍在调用 ${method}`)
    const installAt = source.indexOf(`${installer}()`)
    const useAt = source.indexOf(`.${method}(`)
    assert.ok(installAt > 0, `${file} 缺少 ${installer}() 显式安装`)
    assert.ok(installAt < useAt, `${file} 必须先安装再调用 ${method}`)
  }
})

test('S1.5-G2 生产构建剥离 mock 数据体', () => {
  assert.match(viteConfig, /miniapp-v3-strip-mock-payload-in-production/)
  assert.match(viteConfig, /env\.command === 'build' && env\.mode !== 'development'/)
})

test('S1.5-G2 release finalize 产出机器可读三包报告并按 V3 预算判定', () => {
  assert.match(finalizer, /miniapp-package-report\.json/)
  assert.match(finalizer, /V3_PACKAGE_BUDGET/)
  assert.match(finalizer, /main:\s*520 \* 1024/)
  assert.match(finalizer, /'pages\/student':\s*850 \* 1024/)
  assert.match(finalizer, /'pages\/teacher':\s*950 \* 1024/)
  assert.match(finalizer, /budgetPass/)
  assert.match(finalizer, /duplicateAssets/)
  assert.match(finalizer, /topFiles/)
  // 超预算必须硬失败，禁止只打印告警。
  assert.match(finalizer, /if \(overBudget\.length\) \{\s*\n\s*fail\(/)
})
