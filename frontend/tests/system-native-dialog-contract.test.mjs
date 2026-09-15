import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join, relative } from 'node:path'
import { Linter } from 'eslint'
import vueParser from 'vue-eslint-parser'
import globals from 'globals'

const root = fileURLToPath(new URL('../../', import.meta.url))
const linter = new Linter()
const config = [{
  files: ['**/*.js', '**/*.mjs', '**/*.vue'],
  linterOptions: { reportUnusedDisableDirectives: false },
  languageOptions: { parser: vueParser, ecmaVersion: 'latest', sourceType: 'module', globals: globals.browser },
  rules: { 'no-alert': 'error' }
}]

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(path) : /\.(?:m?js|vue)$/.test(entry.name) ? [path] : []
  })
}

for (const project of ['frontend', 'student-portal', 'miniapp']) {
  test(`${project}: business source uses in-app dialogs, never browser alert/confirm/prompt`, () => {
    const violations = []
    for (const path of sourceFiles(join(root, project, 'src'))) {
      if (/\.(?:test|spec)\./.test(path)) continue
      const filename = relative(root, path).replaceAll('\\', '/')
      const messages = linter.verify(readFileSync(path, 'utf8'), config, { filename })
      for (const message of messages) {
        violations.push(`${filename}:${message.line} ${message.message}`)
      }
    }
    assert.deepEqual(violations, [])
  })
}

test('business source keeps documents and previews in the current system surface', () => {
  const violations = []
  for (const project of ['frontend', 'student-portal', 'miniapp']) {
    for (const path of sourceFiles(join(root, project, 'src'))) {
      const filename = relative(root, path).replaceAll('\\', '/')
      const source = readFileSync(path, 'utf8')
      // Computed member access still opens a browser/remote surface and must be
      // caught alongside the normal member form.
      if (
        /\b(?:window|globalThis)\.(?:open|alert|confirm|prompt)\s*\(/.test(source) ||
        /\b(?:window|globalThis)\s*\[\s*['"](?:open|alert|confirm|prompt)['"]\s*\]\s*\(/.test(source) ||
        /target\s*=\s*['"]_blank/.test(source)
      ) violations.push(filename)
    }
  }
  assert.deepEqual(violations, [])
})

test('shared file preview stays in a closable in-app layer', () => {
  const source = readFileSync(join(root, 'frontend', 'src', 'services', 'file', 'fileSdk.js'), 'utf8')
  assert.match(source, /function showInAppPreview\(/)
  assert.match(source, /setAttribute\('role', 'dialog'\)/)
  assert.match(source, /document\.createElement\('iframe'\)/)
  assert.match(source, /close\.textContent = '关闭预览'/)
  assert.doesNotMatch(source, /window\.location\.assign\(/)
})

test('miniapp H5 converts framework dialogs into the current application surface', () => {
  const source = readFileSync(join(root, 'miniapp', 'src', 'services', 'h5InAppDialogInstaller.js'), 'utf8')
  const viteConfig = readFileSync(join(root, 'miniapp', 'vite.config.js'), 'utf8')
  assert.match(source, /window\.__schoolInAppModal\s*=\s*showModal/)
  assert.match(source, /window\.__schoolInAppActionSheet\s*=\s*showActionSheet/)
  assert.match(source, /role', 'dialog'/)
  assert.doesNotMatch(source, /window\.open\s*\(/)
  assert.match(viteConfig, /globalThis\.__schoolInAppModalInvoker\(uni\.showModal\)\(/)
  assert.match(viteConfig, /globalThis\.__schoolInAppActionSheetInvoker\(uni\.showActionSheet\)\(/)
})

test('guard detects native calls but permits local business methods', () => {
  for (const code of ['alert("message")', 'window.confirm("message")', 'globalThis["prompt"]("message")']) {
    assert.equal(linter.verify(code, config, { filename: 'example.js' })[0]?.ruleId, 'no-alert')
  }
  assert.deepEqual(linter.verify('function confirm() {} confirm(); const api = { confirm() {} }; api.confirm()', config, { filename: 'example.js' }), [])
})

test('portal help stays in the application instead of opening a remote browser window', () => {
  const source = readFileSync(join(root, 'frontend', 'src', 'layouts', 'BasePortalLayout.vue'), 'utf8')
  assert.match(source, /openHelpWindow\(to = '\/admin\/help'\)[\s\S]*?this\.\$router\.push\(to\)/)
  assert.doesNotMatch(source, /openHelpWindow[\s\S]*?window\.open\(/)
})

test('academic-affairs print routes stay in the current application tab', () => {
  const views = [
    'AaExamConsoleView.vue',
    'AaMakeupConsoleView.vue',
    'AaScheduleViewsView.vue',
    'AaSemesterScheduleView.vue',
    'AaStatusChangeDetailView.vue'
  ]
  for (const view of views) {
    const source = readFileSync(join(root, 'frontend', 'src', 'modules', 'academicAffairs', 'views', view), 'utf8')
    assert.doesNotMatch(source, /window\.open\(/, `${view} must keep print routes in the system`)
    assert.match(source, /\$router\.push\(/, `${view} must navigate through the application router`)
  }
})

test('academic-affairs evidence previews never navigate away from the system', () => {
  const views = [
    'AaExemptionArchiveView.vue',
    'AaGradeRecognitionView.vue',
    'AaGradeChangeView.vue',
    'AaStatusChangeDetailView.vue'
  ]
  for (const view of views) {
    const source = readFileSync(join(root, 'frontend', 'src', 'modules', 'academicAffairs', 'views', view), 'utf8')
    assert.doesNotMatch(source, /window\.location\.(?:assign|replace)\(/, `${view} must keep evidence preview in the system`)
    assert.match(source, /fileSdk\.preview\(/, `${view} must use the shared in-app preview`)
  }
})
