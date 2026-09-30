import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const layoutUrl = new URL('../src/layouts/PortalLayout.vue', import.meta.url)

test('菜单宽度由用户固定偏好决定，页面切换不强制折叠；小屏保留目录入口', async () => {
  const source = await readFile(layoutUrl, 'utf8')

  assert.doesNotMatch(source, /['"]is-compact['"]\s*:\s*route\.name\s*!==\s*['"]home['"]/)
  assert.match(source, /v-model:mode="prefs.second"/)
  assert.match(source, /v-model:mode="prefs.third"/)
  const css = await readFile(new URL('../src/styles/student-workspace.css', import.meta.url), 'utf8')
  assert.match(css, /@media\(max-width:700px\)/)
  assert.match(css, /workspace-menu-toggle/)
})
