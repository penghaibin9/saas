#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(SCRIPT_DIR, '../..')
const CODE_EXTENSIONS = ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.vue']
const ASSET_EXTENSIONS = new Set([
  '.css', '.scss', '.sass', '.less', '.styl', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp',
  '.woff', '.woff2', '.ttf', '.eot', '.json', '.md', '.html'
])

const ENTRY_GRAPHS = [
  {
    phase: 'A1',
    name: '审批中心 PC 正式路由',
    entry: 'frontend/src/modules/approval/approval.routes.js',
    registration: { file: 'frontend/src/router/index.js', needle: "@/modules/approval/approval.routes" },
    requiredReachable: ['frontend/src/modules/approval/api/approval.api.js']
  },
  {
    phase: 'A2',
    name: '学生中心 PC 正式路由',
    entry: 'frontend/src/modules/student/student.routes.js',
    registration: { file: 'frontend/src/router/index.js', needle: "@/modules/student/student.routes" },
    requiredReachable: ['frontend/src/modules/student/api/student.api.js']
  },
  {
    phase: 'A3',
    name: '就业中心 PC 正式路由',
    entry: 'frontend/src/modules/employment/employment.routes.js',
    registration: { file: 'frontend/src/router/index.js', needle: "@/modules/employment/employment.routes" },
    requiredReachable: ['frontend/src/modules/employment/api/employment.api.js']
  },
  {
    phase: 'A4',
    name: '数据驾驶舱 PC 正式路由',
    entry: 'frontend/src/modules/dataCenter/dataCenter.routes.js',
    registration: { file: 'frontend/src/router/index.js', needle: "@/modules/dataCenter/dataCenter.routes" },
    requiredReachable: ['frontend/src/modules/dataCenter/api/dataCenter.api.js']
  },
  {
    phase: 'A5',
    name: '平台运营 PC 正式路由',
    entry: 'frontend/src/modules/platform/platform.routes.js',
    registration: { file: 'frontend/src/router/index.js', needle: "@/modules/platform/platform.routes" },
    requiredReachable: ['frontend/src/modules/platform/api/platformControl.api.js']
  },
  {
    phase: 'A1',
    name: '教师小程序审批正式页',
    entry: 'miniapp/src/pages/teacher/approval/index.vue',
    registration: { file: 'miniapp/src/pages.json', needle: '"path": "pages/teacher/approval/index"' },
    requiredReachable: ['miniapp/src/services/approvalApi.js']
  }
]

const FORBIDDEN_EXACT_FILES = new Set([
  'frontend/src/modules/platform/api/platform.api.js'
])

const FORBIDDEN_IMPORTED_SYMBOLS = new Set([
  'mockStudents',
  'roleProfiles',
  'withFallback',
  'shouldTryReal'
])

// A6 继承 A1-A5 已封板合同，但只匹配“旧实现特征”，不把真实 DTO 字段名本身当违规。
// 例如 approvalList / overviewMetrics 作为服务端响应字段是合法的；只有本地声明、内存变更、
// mock import / fallback 调用等能够重新形成浏览器事实源的形态才 fail-closed。
const FILE_FORBIDDEN_PATTERNS = new Map([
  ['frontend/src/modules/approval/api/approval.api.js', [
    { label: '@/mocks/approval', regex: /@\/mocks\/approval\b/ },
    { label: 'withFallback()', regex: /\bwithFallback\s*\(/ },
    { label: 'mockApproval', regex: /\bmockApproval\b/ },
    { label: '审批旧内存台账声明', regex: /\b(?:const|let|var)\s+(?:approvalList|doneItems|returnedItems)\b/ },
    { label: '审批旧内存台账写入', regex: /\b(?:approvalList|doneItems|returnedItems)\s*\.\s*(?:push|pop|shift|unshift|splice|sort|reverse)\s*\(/ }
  ]],
  ['frontend/src/modules/student/api/student.api.js', [
    { label: '@/mocks/', regex: /@\/mocks\// },
    { label: 'withFallback()', regex: /\bwithFallback\s*\(/ },
    { label: '_mockGet()', regex: /\b_mockGet\s*\(/ },
    { label: '_mockCreate()', regex: /\b_mockCreate\s*\(/ },
    { label: 'mockStudents', regex: /\bmockStudents\b/ },
    { label: 'roleProfiles', regex: /\broleProfiles\b/ }
  ]],
  ['frontend/src/modules/employment/api/employment.api.js', [
    { label: '@/mocks/employment', regex: /@\/mocks\/employment\b/ },
    { label: 'shouldTryReal()', regex: /\bshouldTryReal\s*\(/ },
    { label: '就业旧浏览器 db 事实源', regex: /\bdb\s*\.\s*(?:employmentStudents|materialReviews|followUpRecords|auditLogs)\b/ }
  ]],
  ['frontend/src/modules/dataCenter/api/dataCenter.api.js', [
    { label: '@/mocks/dataCenter', regex: /@\/mocks\/dataCenter\b/ },
    { label: 'shouldTryReal()', regex: /\bshouldTryReal\s*\(/ },
    { label: '驾驶舱旧本地 KPI/report 事实声明', regex: /\b(?:const|let|var)\s+(?:overviewMetrics|lifecycleFunnel|riskStats|collegeRankings|majorRankings|classRankings|drilldownStudents|mockRuntime|roleProfiles|reportList|reportDetailMap|reportSeq|auditSeq)\b/ },
    { label: '驾驶舱旧本地审计写入', regex: /\bauditLogs\s*\.\s*push\s*\(/ },
    { label: '驾驶舱浏览器伪导出任务', regex: /\btaskId\s*:\s*`EXP-/ },
    { label: '驾驶舱浏览器比例估算', regex: /Math\.round\s*\(\s*funnel\.totalCount\s*\*\s*ratio\s*\)/ }
  ]],
  ['frontend/src/modules/platform/api/platformControl.api.js', [
    { label: 'shouldTryReal()', regex: /\bshouldTryReal\s*\(/ },
    { label: '平台旧 MOCK_TENANTS/MOCK_OVERVIEW 声明', regex: /\b(?:const|let|var)\s+(?:MOCK_TENANTS|MOCK_OVERVIEW)\b/ },
    { label: 'mockData', regex: /\bmockData\b/ },
    { label: '@/mocks/platform', regex: /@\/mocks\/platform\b/ },
    { label: '回退演示数据', regex: /回退演示数据/ },
    { label: 'ok（演示数据）', regex: /ok（演示数据）/ }
  ]],
  ['miniapp/src/services/approvalApi.js', [
    { label: '@/mocks/', regex: /@\/mocks\// },
    { label: 'realFirst()', regex: /\brealFirst\s*\(/ },
    { label: 'realFirstStrict()', regex: /\brealFirstStrict\s*\(/ },
    { label: 'mockRequest()', regex: /\bmockRequest\s*\(/ },
    { label: 'shouldTryReal()', regex: /\bshouldTryReal\s*\(/ }
  ]]
])

const BUSINESS_OWNED_PREFIXES = [
  'frontend/src/modules/approval/',
  'frontend/src/views/admin/approval/',
  'frontend/src/modules/student/',
  'frontend/src/views/admin/student/',
  'frontend/src/modules/employment/',
  'frontend/src/views/admin/employment/',
  'frontend/src/modules/dataCenter/',
  'frontend/src/views/admin/dataCenter/',
  'frontend/src/modules/platform/',
  'miniapp/src/pages/teacher/approval/',
  'miniapp/src/services/approvalApi.js'
]

function rel(absPath) {
  return path.relative(REPO_ROOT, absPath).split(path.sep).join('/')
}

function abs(repoPath) {
  return path.join(REPO_ROOT, ...repoPath.split('/'))
}

function isCodeFile(filePath) {
  return CODE_EXTENSIONS.includes(path.extname(filePath).toLowerCase())
}

function packageSrcRoot(fromFile) {
  const relative = rel(fromFile)
  for (const pkg of ['frontend', 'miniapp', 'student-portal']) {
    if (relative.startsWith(`${pkg}/src/`)) return abs(`${pkg}/src`)
  }
  return null
}

function stripQuery(specifier) {
  return String(specifier || '').split('?')[0].split('#')[0]
}

function candidateFiles(basePath) {
  const values = [basePath]
  if (!path.extname(basePath)) {
    for (const ext of CODE_EXTENSIONS) values.push(`${basePath}${ext}`)
    for (const ext of CODE_EXTENSIONS) values.push(path.join(basePath, `index${ext}`))
  }
  return values
}

function resolveLocalImport(fromFile, specifier) {
  const clean = stripQuery(specifier)
  let basePath = null
  if (clean.startsWith('@/')) {
    const srcRoot = packageSrcRoot(fromFile)
    if (!srcRoot) return { kind: 'unresolved', reason: `无法为 @/ 别名确定 package src root: ${rel(fromFile)}` }
    basePath = path.join(srcRoot, clean.slice(2))
  } else if (clean.startsWith('./') || clean.startsWith('../')) {
    basePath = path.resolve(path.dirname(fromFile), clean)
  } else {
    return { kind: 'external' }
  }

  for (const candidate of candidateFiles(basePath)) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return { kind: isCodeFile(candidate) ? 'code' : 'asset', file: candidate }
  }

  const ext = path.extname(basePath).toLowerCase()
  if (ASSET_EXTENSIONS.has(ext)) return { kind: 'unresolved', reason: `本地资源 import 不存在: ${specifier}` }
  return { kind: 'unresolved', reason: `本地代码 import 无法解析: ${specifier}` }
}

function extractImports(source) {
  const imports = []
  const seen = new Set()
  const push = (specifier, clause = '', kind = 'import') => {
    const key = `${kind}\0${specifier}\0${clause}`
    if (seen.has(key)) return
    seen.add(key)
    imports.push({ specifier, clause, kind })
  }

  let match
  const staticFrom = /\b(import|export)\s+(?:type\s+)?([A-Za-z0-9_$*{},\s]+?)\s+from\s*(['"])([^'"]+)\3/g
  while ((match = staticFrom.exec(source))) push(match[4], match[2], match[1])

  const sideEffectImport = /\bimport\s*(['"])([^'"]+)\1/g
  while ((match = sideEffectImport.exec(source))) push(match[2], '', 'import')

  const dynamicImport = /\bimport\s*\(\s*(['"])([^'"]+)\1\s*\)/g
  while ((match = dynamicImport.exec(source))) push(match[2], '', 'dynamic-import')

  const requireImport = /\brequire\s*\(\s*(['"])([^'"]+)\1\s*\)/g
  while ((match = requireImport.exec(source))) push(match[2], '', 'require')

  return imports
}

function removeComments(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/(^|[^:])\/\/.*$/gm, '$1 ')
}

function isBusinessOwned(repoPath) {
  return BUSINESS_OWNED_PREFIXES.some((prefix) => repoPath === prefix || repoPath.startsWith(prefix))
}

function forbiddenPathReason(repoPath) {
  if (FORBIDDEN_EXACT_FILES.has(repoPath)) return 'A5 纯 mock platform.api.js 不得进入正式依赖图'
  if (/(^|\/)(?:mocks?|__mocks__)(\/|$)/i.test(repoPath)) return '正式依赖图不得进入 mock/mocks 目录'
  if (/\.mock\.(?:js|mjs|cjs|ts|tsx|jsx|vue|json)$/i.test(repoPath)) return '正式依赖图不得进入 *.mock.* 文件'
  return ''
}

function inspectBusinessSource(repoPath, source, chain, violations) {
  const code = removeComments(source)

  if (isBusinessOwned(repoPath)) {
    const localPatterns = [
      { label: '_mock* 业务方法', regex: /\b_mock[A-Za-z0-9_]*\s*\(/ },
      { label: 'MOCK_* 业务事实常量', regex: /\b(?:const|let|var)\s+MOCK_[A-Z0-9_]+\b/ },
      { label: 'mockStudents 业务事实', regex: /\bmockStudents\b/ },
      { label: 'roleProfiles 业务事实', regex: /\broleProfiles\b/ },
      { label: 'withFallback 正式业务回退', regex: /\bwithFallback\s*\(/ },
      { label: 'shouldTryReal 正式业务回退', regex: /\bshouldTryReal\s*\(/ }
    ]
    for (const item of localPatterns) {
      if (item.regex.test(code)) violations.push({ type: 'forbidden-business-symbol', file: repoPath, message: `${repoPath} 命中 ${item.label}`, chain })
    }
  }

  const filePatterns = FILE_FORBIDDEN_PATTERNS.get(repoPath) || []
  for (const item of filePatterns) {
    if (item.regex.test(code)) {
      violations.push({ type: 'stage-contract-regression', file: repoPath, message: `${repoPath} 重新出现阶段 A 已封板旧真值源实现: ${item.label}`, chain })
    }
  }
}

function inspectImportedSymbols(repoPath, imp, chain, violations) {
  if (!imp.clause) return
  for (const symbol of FORBIDDEN_IMPORTED_SYMBOLS) {
    const regex = new RegExp(`\\b${symbol}\\b`)
    if (regex.test(imp.clause)) {
      violations.push({ type: 'forbidden-imported-symbol', file: repoPath, message: `${repoPath} 从 ${imp.specifier} 导入禁用符号 ${symbol}`, chain })
    }
  }
}

function assertRegistration(graph, violations) {
  const registrationFile = abs(graph.registration.file)
  if (!fs.existsSync(registrationFile)) {
    violations.push({ type: 'missing-registration-file', file: graph.registration.file, message: `${graph.registration.file} 不存在`, chain: [graph.entry] })
    return
  }
  const source = fs.readFileSync(registrationFile, 'utf8')
  if (!source.includes(graph.registration.needle)) {
    violations.push({
      type: 'formal-entry-not-registered',
      file: graph.registration.file,
      message: `${graph.entry} 未在 ${graph.registration.file} 以正式入口注册（缺少 ${graph.registration.needle}）`,
      chain: [graph.entry]
    })
  }
}

function scanGraph(graph) {
  const violations = []
  const entryFile = abs(graph.entry)
  if (!fs.existsSync(entryFile)) {
    return { graph, violations: [{ type: 'missing-entry', file: graph.entry, message: `正式入口不存在: ${graph.entry}`, chain: [graph.entry] }], visited: new Set(), edges: 0 }
  }

  assertRegistration(graph, violations)
  const visited = new Set()
  const queued = new Set([entryFile])
  const queue = [{ file: entryFile, chain: [graph.entry] }]
  let edges = 0

  while (queue.length) {
    const current = queue.shift()
    const repoPath = rel(current.file)
    queued.delete(current.file)
    if (visited.has(current.file)) continue
    visited.add(current.file)

    const pathReason = forbiddenPathReason(repoPath)
    if (pathReason) {
      violations.push({ type: 'forbidden-path', file: repoPath, message: `${repoPath}: ${pathReason}`, chain: current.chain })
      continue
    }

    let source = ''
    try {
      source = fs.readFileSync(current.file, 'utf8')
    } catch (error) {
      violations.push({ type: 'read-error', file: repoPath, message: `无法读取 ${repoPath}: ${error.message}`, chain: current.chain })
      continue
    }

    inspectBusinessSource(repoPath, source, current.chain, violations)
    for (const imp of extractImports(removeComments(source))) {
      inspectImportedSymbols(repoPath, imp, current.chain, violations)
      const resolved = resolveLocalImport(current.file, imp.specifier)
      if (resolved.kind === 'external') continue
      if (resolved.kind === 'unresolved') {
        violations.push({ type: 'unresolved-local-import', file: repoPath, message: `${repoPath}: ${resolved.reason}`, chain: [...current.chain, imp.specifier] })
        continue
      }

      const targetPath = rel(resolved.file)
      const nextChain = [...current.chain, targetPath]
      const targetReason = forbiddenPathReason(targetPath)
      if (targetReason) {
        violations.push({ type: 'forbidden-path', file: targetPath, message: `${targetPath}: ${targetReason}`, chain: nextChain })
        continue
      }
      if (resolved.kind === 'asset') continue

      edges += 1
      if (!visited.has(resolved.file) && !queued.has(resolved.file)) {
        queued.add(resolved.file)
        queue.push({ file: resolved.file, chain: nextChain })
      }
    }
  }

  const reachable = new Set([...visited].map(rel))
  for (const required of graph.requiredReachable || []) {
    if (!reachable.has(required)) {
      violations.push({ type: 'required-real-facade-not-reachable', file: graph.entry, message: `${graph.entry} 未能到达阶段封板真实 facade: ${required}`, chain: [graph.entry, required] })
    }
  }
  return { graph, violations, visited: reachable, edges }
}

function escapeAnnotation(value) {
  return String(value || '').replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A').replace(/:/g, '%3A').replace(/,/g, '%2C')
}

function printViolation(graph, violation) {
  const chain = violation.chain?.length ? violation.chain.join(' -> ') : ''
  console.error(`\n❌ [${graph.phase} · ${graph.name}] ${violation.message}`)
  if (chain) console.error(`   依赖链: ${chain}`)
  const file = violation.file || graph.entry || 'scripts/check/check-formal-route-dependency-graph.mjs'
  const title = `A6 ${graph.phase} · ${graph.name}`
  const detail = chain ? `${violation.message} | 依赖链: ${chain}` : violation.message
  console.error(`::error file=${escapeAnnotation(file)},title=${escapeAnnotation(title)}::${escapeAnnotation(detail)}`)
}

function run() {
  const results = ENTRY_GRAPHS.map(scanGraph)
  const failures = results.flatMap((result) => result.violations.map((violation) => ({ result, violation })))

  console.log('A6 正式路由依赖图门禁')
  console.log(`仓库: ${REPO_ROOT}`)
  for (const result of results) {
    console.log(`${result.violations.length ? '❌' : '✅'} ${result.graph.phase} · ${result.graph.name}: ${result.visited.size} 个代码节点 / ${result.edges} 条本地依赖边 / ${result.violations.length} 个违规`)
  }

  if (failures.length) {
    for (const { result, violation } of failures) printViolation(result.graph, violation)
    console.error(`\nA6 FAIL：发现 ${failures.length} 个正式路由 mock/回退/依赖图违规。`)
    process.exit(1)
  }

  console.log('\n✅ A6 PASS：A1-A5 正式入口依赖图无法到达已禁止的 mock 事实源/回退实现；正式真实 facade 仍可达。')
}

run()
