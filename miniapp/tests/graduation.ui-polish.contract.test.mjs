import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const root = new URL('../src/', import.meta.url)
const read = path => fs.readFileSync(new URL(path, root), 'utf8')
const app = read('App.vue')
const css = read('styles/graduation-usability.css')

const teacherRoots = [
  'pages/teacher/graduation-guide/index.vue',
  'pages/teacher/graduation-topics/index.vue',
  'pages/teacher/graduation-taskbook/index.vue',
  'pages/teacher/defense-score/index.vue'
]
const studentRoots = [
  'pages/student/graduation/index.vue',
  'pages/student/graduation/topics/index.vue',
  'pages/student/graduation/taskbook/index.vue',
  'pages/student/graduation/defense/index.vue',
  'pages/student/graduation/evidence-package.vue'
]

test('graduation mobile polish is loaded through the existing graduation-only owner', () => {
  assert.match(app, /@import '\.\/styles\/graduation-usability\.css';/)
  assert.doesNotMatch(css, /(^|\n)\s*(?:button|input|textarea|view|text)\s*\{/)
  assert.doesNotMatch(css, /@import|:root|page\s*\{/)
})

test('all nine real teacher/student graduation roots still exist', () => {
  for (const path of [...teacherRoots, ...studentRoots]) {
    assert.equal(fs.existsSync(new URL(path, root)), true, path)
  }
})

test('high-frequency graduation controls use the existing 44px touch token', () => {
  assert.match(css, /\.gg__go,[\s\S]*?\.gd__att-add,[\s\S]*?\.tp__search\s*\{[\s\S]*?min-height:\s*var\(--touch-target-min\) !important;/)
  assert.match(css, /\.rv__nav,[\s\S]*?\.rv__act/)
  assert.match(css, /\.gt__tab,[\s\S]*?\.tb__tab/)
  assert.match(css, /\.ds__input/)
})

test('mobile typography keeps 14–16px primary text and 12–13px supporting text tokens', () => {
  const tokens = read('styles/tokens.css')
  assert.match(tokens, /--font-size-xs:\s*12px/)
  assert.match(tokens, /--font-size-sm:\s*13px/)
  assert.match(tokens, /--font-size-base:\s*14px/)
  assert.match(tokens, /--font-size-md:\s*15px/)
  assert.match(tokens, /--font-size-lg:\s*16px/)
  assert.match(css, /font-size:\s*var\(--font-size-sm\) !important/)
})

test('student main is current-task first from the shared server journey, with ordered steps', () => {
  const page = read('pages/student/graduation/index.vue')
  // “当前要做”来自后端统一派生（与学生 PC 同源），不再按 stage 在前端写死
  assert.match(page, /studentApi\.getGraduationJourney\(\)/)
  assert.match(page, /<MobileActionCard[\s\S]*?:title="currentTitle"/)
  assert.match(page, /v-for="step in journey\.steps"/)
  assert.doesNotMatch(page, /GD_PRIMARY|g\.primaryAction/)
  assert.match(page, /title="需要重交"/)
  // 论文可在手机提交；仅设计作品包、源代码等大型压缩包引导到电脑端
  assert.match(page, /设计作品包、源代码等大型文件请到电脑端上传/)
  assert.doesNotMatch(page, /论文定稿、作品和源代码请使用学生 PC 上传/)
})

test('teacher guide keeps continuous review and real-role handoff instead of a mini PC menu', () => {
  const guide = read('pages/teacher/graduation-guide/index.vue')
  assert.match(guide, /开始批阅开题/)
  assert.match(guide, /开始批阅成果/)
  assert.match(guide, /处理后自动下一条|自动下一条/)
  assert.match(guide, /pages\/teacher\/defense-score\/index/)
  assert.doesNotMatch(guide, /BasePortalLayout|TeacherWorkspaceFrame/)
})

test('teacher guide never exposes file workflow machine codes to teachers', () => {
  const guide = read('pages/teacher/graduation-guide/index.vue')
  assert.match(guide, /第 \{\{ v\.versionNo \|\| '—' \}\} 版/)
  assert.match(guide, /fileScanLabel\(v\.scanStatus\)/)
  assert.match(guide, /fileReviewLabel\(v\.reviewStatus \|\| v\.versionStatus \|\| v\.status\)/)
  assert.match(guide, /FILE_STATUS_TEXT/)
  assert.doesNotMatch(guide, /FileVersion \{\{ v\.versionId \}\}/)
})
