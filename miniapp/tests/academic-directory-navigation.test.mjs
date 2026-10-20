import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

test('repeated academic directory switches preserve the home return and bounded page stack', () => {
  const base = 'pages/student/academic-affairs/'
  const pages = [{ route: 'pages/student/home/index' }, { route: base + 'index' }]
  const context = vm.createContext({
    forcePasswordChangeRequired: () => false,
    getCurrentPages: () => pages,
    uni: {
      navigateTo: ({ url, complete }) => { pages.push({ route: url.slice(1) }); complete() },
      redirectTo: ({ url, complete }) => { pages.splice(pages.length - 1, 1, { route: url.slice(1) }); complete() },
      navigateBack: ({ delta, complete }) => { pages.splice(pages.length - delta, delta); complete() }
    }
  })
  vm.runInContext(readFileSync(new URL('../src/utils/nav.js', import.meta.url), 'utf8')
    .replace(/import[\s\S]*?from[^\n]+\n/, '').replace(/export default[^\n]+/, '').replace(/export /g, ''), context)
  for (let i = 0; i < 25; i++) {
    context.goSibling('/' + base + (i % 2 ? 'schedule' : 'transcript'), '/' + base)
    assert.equal(pages.length, 3)
  }
  context.goSibling('/' + base + 'index', '/' + base)
  assert.equal(pages.length, 2)
  assert.equal(pages[0].route, 'pages/student/home/index')
})
