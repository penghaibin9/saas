import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')
const layout = read('frontend/src/layouts/BasePortalLayout.vue')
const styles = read('frontend/src/styles/base-portal-theme-controls.css')
const main = read('frontend/src/main.js')

function themeBlock() {
  const match = layout.match(/<div class="bpl-thdots"[\s\S]*?<\/div>/)
  assert.ok(match, 'theme control group must exist')
  return match[0]
}

test('six themes use native button semantics and expose selection state', () => {
  const block = themeBlock()
  assert.match(block, /role="group"/)
  assert.match(block, /aria-label="界面主题"/)
  assert.match(block, /<button[\s\S]*?v-for="t in themeOptions"/)
  assert.match(block, /type="button"/)
  assert.match(block, /:aria-label="`切换到\$\{t\.label\}主题`"/)
  assert.match(block, /:aria-pressed="theme === t\.key"/)
  assert.match(block, /@click="setTheme\(t\.key\)"/)
  assert.doesNotMatch(block, /<span[\s\S]*?class="bpl-thdot"/)
})

test('responsive hardening is loaded last and keeps a visible keyboard focus', () => {
  const stageIndex = main.indexOf("import './styles/stage-b-responsive-nav.css'")
  const themeIndex = main.indexOf("import './styles/base-portal-theme-controls.css'")
  assert.ok(stageIndex >= 0 && themeIndex > stageIndex)
  assert.match(styles, /\.bpl-thdot:focus-visible/)
  assert.match(styles, /outline:\s*2px solid var\(--pri\)/)
  assert.match(styles, /@media \(max-width: 1450px\)[\s\S]*?\.bpl-cmdk--fn kbd[\s\S]*?display:\s*none/)
  assert.match(styles, /\.bpl-thdot[\s\S]*?width:\s*24px[\s\S]*?height:\s*24px/)
  assert.match(styles, /touch-action:\s*manipulation/)
})

test('all six existing theme swatches remain represented without changing theme keys', () => {
  for (const key of ['a', 'b', 'c', 'd', 'e', 'f']) {
    assert.match(styles, new RegExp(`\\.bpl-thdot--${key}\\s*\\{`))
  }
  assert.match(layout, /const THEME_OPTIONS = \[[\s\S]*?key: 'e'[\s\S]*?key: 'f'[\s\S]*?key: 'a'[\s\S]*?key: 'b'[\s\S]*?key: 'd'[\s\S]*?key: 'c'/)
})
