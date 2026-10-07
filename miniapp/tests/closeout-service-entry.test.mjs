import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { roleConfigs } from '../src/config/roles.config.js'
import { teacherServices, teacherServiceRoute } from '../src/services/teacherServiceCatalog.mjs'
const manifest = JSON.parse(readFileSync(new URL('../src/pages.json', import.meta.url), 'utf8'))
const routes = new Set([...manifest.pages.map(p => '/' + p.path), ...manifest.subPackages.flatMap(s => s.pages.map(p => '/' + s.root + '/' + p.path))])
test('all configured teacher service entries resolve to registered pages without fake placeholders', () => {
  for (const [role, config] of Object.entries(roleConfigs)) {
    if (config.side !== 'teacher') continue
    for (const action of config.quickActions || []) {
      const path = teacherServiceRoute(action.key, role)
      assert.ok(path, `${role}/${action.key} has no real service`)
      assert.ok(routes.has(path.split('?')[0]), `${role}/${action.key} points outside registered pages`)
    }
    const items = teacherServices(config, role, { can: () => true })
    assert.ok(items.every(x => !x.disabledReason))
    assert.equal(new Set(items.map(x => x.path)).size, items.length)
    assert.ok(items.every(x => !['创建关怀', '移动催办'].includes(x.label)), 'Do not promise an unimplemented command')
  }
})
test('contact and record entries reuse scoped student and family-contact workspaces', () => {
  assert.equal(teacherServiceRoute('contact', 'counselor'), '/pages/teacher/my-students/index')
  assert.equal(teacherServiceRoute('record', 'counselor'), '/pages/teacher/family-contact/index?mode=create')
})
