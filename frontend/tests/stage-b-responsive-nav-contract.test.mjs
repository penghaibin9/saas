import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const main = fs.readFileSync(new URL('../src/main.js', import.meta.url), 'utf8')
const css = fs.readFileSync(new URL('../src/styles/stage-b-responsive-nav.css', import.meta.url), 'utf8')

test('Stage B B3 responsive navigation override is loaded globally', () => {
  assert.match(main, /import '\.\/styles\/stage-b-responsive-nav\.css'/)
  assert.match(css, /@media \(max-width: 900px\)/)
})

test('Stage B B3 keeps primary and secondary navigation operable below 900px', () => {
  assert.match(css, /\.bpl-rail\s*\{[\s\S]*display:\s*flex\s*!important/)
  assert.match(css, /\.bpl-rail[\s\S]*overflow-x:\s*auto/)
  assert.match(css, /\.bpl-aside,[\s\S]*\.bpl-aside\.is-hidden[\s\S]*display:\s*block\s*!important/)
  assert.match(css, /\.bpl-aside[\s\S]*overflow-y:\s*auto/)
  assert.match(css, /\.bpl-mobilehint\s*\{[\s\S]*display:\s*none\s*!important/)
})
