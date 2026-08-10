import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const source = fs.readFileSync(path.join(root, 'src/components/common/experience/AppStepGuide.vue'), 'utf8')

test('lightweight page guide must not block global account and identity controls', () => {
  const maskBlock = source.match(/\.app-step-guide__mask\s*\{([\s\S]*?)\n\}/)?.[1] || ''
  const cardBlock = source.match(/\.app-step-guide\s*\{([\s\S]*?)\n\}/)?.[1] || ''

  assert.match(maskBlock, /pointer-events:\s*none\s*;/, 'visual mask must pass pointer events through to app shell')
  assert.match(cardBlock, /pointer-events:\s*auto\s*;/, 'guide card itself must remain interactive')
  assert.match(source, /role="dialog"/)
  assert.match(source, /aria-modal="false"/)
  assert.doesNotMatch(source, /aria-modal="true"/)
  assert.doesNotMatch(source, /@click\.self="onSkip"/, 'background click must not consume an app-shell interaction')
})
