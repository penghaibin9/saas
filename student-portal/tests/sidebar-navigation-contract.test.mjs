import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const layoutUrl = new URL('../src/layouts/PortalLayout.vue', import.meta.url)

test('desktop sidebar stays expanded after navigating away from home', async () => {
  const source = await readFile(layoutUrl, 'utf8')

  assert.doesNotMatch(source, /['"]is-compact['"]\s*:\s*route\.name\s*!==\s*['"]home['"]/)
  assert.match(source, /@media\(max-width:900px\)/)
})
