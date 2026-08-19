import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve, join, relative } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const manifest = JSON.parse(read('src/pages.json'))

// V3 S1 分包契约：完整 /pages/... URL 必须由 subPackages[].root + pages[].path 还原，
// 页面总数守恒，且主包只保留 login/common/role-switch。
const MAIN_PACKAGE_PREFIXES = ['pages/login/', 'pages/common/', 'pages/role-switch/']
const SUBPACKAGE_ROOTS = ['pages/student', 'pages/teacher']
// S1 冻结基线：分包重构当时的页面规模。V3 后续波次会新增学生页（Agenda、我的办理…），
// 所以这里是「不得低于」的下界 + 「每个页面文件恰好注册一次」的守恒，而不是死数字——
// 死数字既挡不住漏页，也会把正常新增页面误判成回归。
const S1_BASELINE_TOTAL_PAGES = 134
const S1_BASELINE_STUDENT_PAGES = 65
const S1_BASELINE_TEACHER_PAGES = 57

function resolveRoutes() {
  const rows = []
  for (const page of manifest.pages || []) rows.push({ route: page.path, pkg: 'main', style: page.style })
  for (const pkg of manifest.subPackages || []) {
    const pkgRoot = String(pkg.root || '').replace(/\/+$/, '')
    for (const page of pkg.pages || []) {
      rows.push({ route: `${pkgRoot}/${page.path}`, pkg: pkgRoot, style: page.style })
    }
  }
  return rows
}

const rows = resolveRoutes()
const routes = rows.map((row) => row.route)
const routeSet = new Set(routes)

test('S1-G1 pages.json 可解析且声明了普通分包', () => {
  assert.ok(Array.isArray(manifest.pages), 'pages 必须是数组')
  assert.ok(Array.isArray(manifest.subPackages), 'subPackages 必须存在')
  assert.deepEqual(
    manifest.subPackages.map((pkg) => pkg.root),
    SUBPACKAGE_ROOTS,
    '分包 root 必须且只能是 pages/student 与 pages/teacher'
  )
})

test('S1-G1 严禁 independent 分包', () => {
  for (const pkg of manifest.subPackages) {
    assert.equal(pkg.independent, undefined, `${pkg.root} 不允许 independent`)
  }
  assert.doesNotMatch(read('src/pages.json'), /"independent"/)
})

test('S1-G1 页面守恒：无重复、无漏页、不低于 S1 基线', () => {
  assert.equal(routeSet.size, routes.length, '还原后的完整 URL 不允许重复')
  assert.ok(routes.length >= S1_BASELINE_TOTAL_PAGES,
    `页面总数 ${routes.length} 低于 S1 基线 ${S1_BASELINE_TOTAL_PAGES}，说明有页面在分包重构中丢失`)
  const student = routes.filter((route) => route.startsWith('pages/student/'))
  const teacher = routes.filter((route) => route.startsWith('pages/teacher/'))
  assert.ok(student.length >= S1_BASELINE_STUDENT_PAGES, `学生页 ${student.length} < ${S1_BASELINE_STUDENT_PAGES}`)
  assert.ok(teacher.length >= S1_BASELINE_TEACHER_PAGES, `教师页 ${teacher.length} < ${S1_BASELINE_TEACHER_PAGES}`)
})

test('S1-G1 每个页面文件恰好注册一次（既不漏注册也不重复注册）', () => {
  const files = []
  const walk = (dir, prefix) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry)
      if (statSync(full).isDirectory()) walk(full, `${prefix}${entry}/`)
      else if (entry.endsWith('.vue')) files.push(`${prefix}${entry.slice(0, -4)}`)
    }
  }
  walk(resolve(root, 'src/pages'), 'pages/')
  // 页面目录里允许放局部组件（仓库约定：组件文件名 PascalCase，页面文件名小写/kebab）。
  const isComponent = (file) => /\/[A-Z][A-Za-z0-9]*$/.test(file)
  const pageFiles = files.filter((file) => !isComponent(file))
  const unregistered = pageFiles.filter((file) => !routeSet.has(file))
  assert.deepEqual(unregistered, [], `以下页面文件存在但未注册:\n${unregistered.join('\n')}`)
  assert.equal(pageFiles.length, routes.length, '页面文件数与注册路由数必须一一对应')
})

test('S1-G1 每个注册页面都有真实存在的 .vue 文件', () => {
  for (const route of routes) {
    const file = resolve(root, 'src', `${route}.vue`)
    assert.ok(statSync(file).isFile(), `${route} 缺少页面文件`)
  }
})

test('S1-G2 主包只保留 login/common/role-switch，且入口页不变', () => {
  assert.equal(manifest.pages[0].path, 'pages/login/index', '首页入口必须仍是登录选择页')
  for (const page of manifest.pages) {
    assert.ok(
      MAIN_PACKAGE_PREFIXES.some((prefix) => page.path.startsWith(prefix)),
      `${page.path} 不属于主包白名单，必须进入分包`
    )
  }
})

test('S1-G2 学生/教师页面必须全部进入对应分包，不得留在主包', () => {
  for (const page of manifest.pages) {
    assert.doesNotMatch(page.path, /^pages\/(student|teacher)\//)
  }
  const studentPkg = manifest.subPackages.find((pkg) => pkg.root === 'pages/student')
  const teacherPkg = manifest.subPackages.find((pkg) => pkg.root === 'pages/teacher')
  for (const page of studentPkg.pages) {
    assert.doesNotMatch(page.path, /^pages\//, '分包内 path 必须是 root 相对路径')
  }
  for (const page of teacherPkg.pages) {
    assert.doesNotMatch(page.path, /^pages\//, '分包内 path 必须是 root 相对路径')
  }
})

test('S1-G2 页面 style 在分包重构中逐条保留', () => {
  for (const row of rows) {
    assert.ok(row.style && typeof row.style === 'object', `${row.route} 丢失 style`)
    assert.ok(
      typeof row.style.navigationBarTitleText === 'string' && row.style.navigationBarTitleText.length > 0,
      `${row.route} 丢失 navigationBarTitleText`
    )
  }
})

// S1-G2：仓库里所有硬编码的完整 /pages/... 跳转目标都必须仍然解析到唯一页面。
function collectSourceFiles(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      if (entry === 'node_modules') continue
      collectSourceFiles(full, acc)
    } else if (/\.(vue|js|mjs)$/.test(entry)) {
      acc.push(full)
    }
  }
  return acc
}

test('S1-G2 源码中的完整 /pages/... 链接全部可解析', () => {
  const files = collectSourceFiles(resolve(root, 'src'))
  const pattern = /["'`](\/pages\/[A-Za-z0-9_\-/]+)/g
  const unresolved = []
  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    for (const match of source.matchAll(pattern)) {
      const literal = match[1]
      // 模板串前缀（以 / 结尾）由运行时拼接，交给 registry reachability 契约覆盖。
      if (literal.endsWith('/')) continue
      const route = literal.slice(1)
      if (!routeSet.has(route)) {
        unresolved.push(`${relative(root, file)} -> ${literal}`)
      }
    }
  }
  assert.deepEqual(unresolved, [], `以下跳转目标在分包还原后不可达:\n${unresolved.join('\n')}`)
})

test('S1-G4 不得同时预载 student 与 teacher 分包', () => {
  const rules = manifest.preloadRule || {}
  for (const [page, rule] of Object.entries(rules)) {
    const packages = rule.packages || []
    const both = packages.includes('pages/student') && packages.includes('pages/teacher')
    assert.ok(!both, `${page} 同时预载两个分包会抵消瘦身收益`)
  }
})
