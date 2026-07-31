#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const TOOL_DIR = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(TOOL_DIR, '..')
const MANIFEST_PATH = path.join(ROOT, 'manifest-parts/300-student-affairs-key.json')
const RUNTIME_REF = 'student-affairs/runtime-enhancements.js'
const RUNTIME_PATH = path.join(ROOT, RUNTIME_REF)
const MAIN_SCRIPT_REF = '../shared/v2-student-affairs-workbench.js'
const GUARD_SCRIPT_REF = 'runtime-enhancements.js'
const reportArg = process.argv.slice(2).find((value) => value.startsWith('--report='))
const reportPath = reportArg ? path.resolve(process.cwd(), reportArg.slice('--report='.length)) : null

const EXPECTED_HTML_COUNT = 11
const EXPECTED_ROUTES = new Map([
  ['学工工作台', '/admin/student-affairs/dashboard'],
  ['学生主档', '/admin/student/list'],
  ['班级与辅导员', '/admin/campus-service/classes'],
  ['数字迎新', '/admin/orientation'],
  ['请假销假', '/admin/student-affairs/leave'],
  ['宿舍与公寓', '/admin/student-affairs/dorm/exception'],
  ['风险预警与处置', '/admin/student-affairs/risk'],
  ['困难认定', '/admin/student-affairs/aid'],
  ['奖助勤贷补', '/admin/student-affairs/funding'],
  ['违纪处分', '/admin/student-affairs/discipline'],
  ['谈心谈话与家校协同', '/admin/student-affairs/talk'],
  ['心理关注', '/admin/student-affairs/mental'],
  ['活动与第二课堂', '/admin/student-affairs/activity'],
  ['统计与档案', '/admin/student-affairs/stats']
])

const errors = []
const notes = []

function fail(code, message, detail = {}) {
  errors.push({ code, message, ...detail })
}

function note(code, message, detail = {}) {
  notes.push({ code, message, ...detail })
}

function readText(file, label) {
  if (!fs.existsSync(file)) {
    fail('MISSING_FILE', `缺少${label}：${file}`)
    return ''
  }
  return fs.readFileSync(file, 'utf8')
}

function readJson(file, label) {
  const text = readText(file, label)
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch (error) {
    fail('INVALID_JSON', `${label}不是有效 JSON：${error.message}`)
    return null
  }
}

function rowsOf(part) {
  return Array.isArray(part?.routes) ? part.routes : Array.isArray(part?.entries) ? part.entries : []
}

function scriptIndex(html, ref) {
  const single = `<script src='${ref}'></script>`
  const double = `<script src="${ref}"></script>`
  const singleIndex = html.indexOf(single)
  const doubleIndex = html.indexOf(double)
  if (singleIndex < 0) return doubleIndex
  if (doubleIndex < 0) return singleIndex
  return Math.min(singleIndex, doubleIndex)
}

function requireRuntimeMarker(source, marker, label) {
  if (!source.includes(marker)) {
    fail('RUNTIME_MARKER_MISSING', `运行增强层缺少${label}`, { marker })
  }
}

function extractRoutePairs(source) {
  const match = source.match(/const\s+ROUTES\s*=\s*new\s+Map\s*\(\s*\[([\s\S]*?)\]\s*\)\s*;/)
  if (!match) {
    fail('ROUTE_MAP_MISSING', '运行增强层没有可解析的 ROUTES Map')
    return new Map()
  }

  const pairs = new Map()
  const pairPattern = /\[\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*\]/g
  let pair
  while ((pair = pairPattern.exec(match[1])) !== null) {
    const [, label, route] = pair
    if (pairs.has(label)) {
      fail('DUPLICATE_ROUTE_LABEL', `运行增强层路由标签重复：${label}`)
    }
    pairs.set(label, route)
  }
  return pairs
}

const manifest = readJson(MANIFEST_PATH, '学工关键工作台 Manifest')
const rows = rowsOf(manifest)
const htmlFiles = [...new Set(rows.map((row) => row?.html).filter(Boolean))].sort()

if (rows.length !== EXPECTED_HTML_COUNT) {
  fail('MANIFEST_ROW_COUNT', `300 Manifest 条目为 ${rows.length}，期望 ${EXPECTED_HTML_COUNT}`)
}
if (htmlFiles.length !== EXPECTED_HTML_COUNT) {
  fail('HTML_COUNT', `学工关键工作台唯一 HTML 为 ${htmlFiles.length}，期望 ${EXPECTED_HTML_COUNT}`)
}

const wiring = []
for (const htmlRef of htmlFiles) {
  const htmlPath = path.resolve(ROOT, htmlRef)
  if (!htmlPath.startsWith(`${ROOT}${path.sep}`)) {
    fail('HTML_OUTSIDE_ROOT', `HTML 越出原型目录：${htmlRef}`)
    continue
  }
  const html = readText(htmlPath, `关键工作台 HTML ${htmlRef}`)
  if (!html) continue

  const guardIndex = scriptIndex(html, GUARD_SCRIPT_REF)
  const mainIndex = scriptIndex(html, MAIN_SCRIPT_REF)
  wiring.push({ html: htmlRef, guardIndex, mainIndex })

  if (guardIndex < 0) {
    fail('GUARD_NOT_REFERENCED', `${htmlRef} 未引用 ${GUARD_SCRIPT_REF}`)
  }
  if (mainIndex < 0) {
    fail('MAIN_SCRIPT_NOT_REFERENCED', `${htmlRef} 未引用 ${MAIN_SCRIPT_REF}`)
  }
  if (guardIndex >= 0 && mainIndex >= 0 && guardIndex > mainIndex) {
    fail('GUARD_LOAD_ORDER', `${htmlRef} 的运行增强层必须先于主脚本加载`)
  }
}

const runtimeSource = readText(RUNTIME_PATH, '学工运行增强层')
if (runtimeSource) {
  try {
    new vm.Script(runtimeSource, { filename: RUNTIME_REF })
  } catch (error) {
    fail('RUNTIME_SYNTAX', `学工运行增强层语法错误：${error.message}`)
  }

  const requiredMarkers = [
    ["const ICON_FROM = '../../shared/icons.svg#'", '原错误图标路径识别'],
    ["const ICON_TO = '../shared/icons.svg#'", '正确图标路径'],
    ["button:not([type])", '按钮 type 修复'],
    ['link.dataset.productionRoute = route', '生产路由追溯'],
    ['aria-labelledby', '对话框标题关联'],
    ['const openerByOverlay = new WeakMap()', '打开按钮追踪'],
    ['new MutationObserver', '动态 DOM 修补'],
    ['queueMicrotask(() => focusDialog(overlay))', '打开后焦点进入'],
    ['const [first] = focusableElements(overlay)', '首个可操作控件聚焦'],
    ['event.key === \'Escape\'', 'Escape 顶层关闭'],
    ["event.key !== 'Tab'", 'Tab 焦点陷阱'],
    ['event.stopImmediatePropagation()', '阻止主脚本关闭全部弹层'],
    ['restoreFocus(overlay)', '关闭后焦点归还'],
    ["event.target === overlay", '遮罩点击关闭']
  ]
  requiredMarkers.forEach(([marker, label]) => requireRuntimeMarker(runtimeSource, marker, label))

  const actualRoutes = extractRoutePairs(runtimeSource)
  if (actualRoutes.size !== EXPECTED_ROUTES.size) {
    fail('ROUTE_MAP_COUNT', `运行增强层路由映射为 ${actualRoutes.size}，期望 ${EXPECTED_ROUTES.size}`)
  }
  for (const [label, expectedRoute] of EXPECTED_ROUTES) {
    const actualRoute = actualRoutes.get(label)
    if (actualRoute !== expectedRoute) {
      fail('ROUTE_MAP_MISMATCH', `${label} 的生产入口不一致`, {
        expected: expectedRoute,
        actual: actualRoute || null
      })
    }
  }
  for (const [label, route] of actualRoutes) {
    if (!EXPECTED_ROUTES.has(label)) {
      fail('STALE_ROUTE_MAP_ENTRY', `运行增强层含未登记标签：${label}`, { route })
    }
  }
}

if (!errors.length) {
  note('STUDENT_AFFAIRS_RUNTIME_PASS', '学工 11 个关键 HTML 的运行增强层引用、顺序、语法、14 个生产入口和焦点契约一致')
}

const report = {
  generatedAt: new Date().toISOString(),
  manifest: path.relative(ROOT, MANIFEST_PATH).split(path.sep).join('/'),
  runtime: RUNTIME_REF,
  counts: {
    manifestRows: rows.length,
    uniqueHtmlFiles: htmlFiles.length,
    wiredHtmlFiles: wiring.filter((item) => item.guardIndex >= 0 && item.mainIndex >= 0 && item.guardIndex < item.mainIndex).length,
    expectedRoutes: EXPECTED_ROUTES.size,
    errors: errors.length,
    notes: notes.length
  },
  wiring,
  errors,
  notes
}

if (reportPath) {
  fs.mkdirSync(path.dirname(reportPath), { recursive: true })
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
}

console.log(JSON.stringify(report.counts, null, 2))
for (const item of errors) console.error(`ERROR [${item.code}] ${item.message}`)
for (const item of notes) console.log(`NOTE  [${item.code}] ${item.message}`)

if (errors.length) process.exit(1)
