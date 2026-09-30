import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

for (const role of ['student', 'teacher']) {
  test(`${role} legacy material entry derives its return target from the matched requirement`, async () => {
    const source = fs.readFileSync(new URL(`../src/pages/${role}/affairs/index.vue`, import.meta.url), 'utf8')
    const contextBody = source.match(/materialReturnContext\(\) \{([\s\S]*?)\n    \},/)[1]
    const returnBody = source.match(/(?:async )?returnToApplication\(\) \{(.*) \},/)[1]
    const vm = { leaveContext: {}, materials: [], focusMaterialId: '7' }, routes = []
    const resolve = () => new Function(contextBody).call(vm)
    assert.deepEqual(resolve(), {})
    vm.materials = [{ requirementId: '8', bizType: 'FUNDING', bizId: '90' }]
    assert.deepEqual(resolve(), {})
    vm.materials.push({ requirementId: '7', bizType: 'FUNDING', bizId: '41' })
    vm.materialReturnContext = resolve(); vm.go = async url => routes.push(url)
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
    await new AsyncFunction('uni', returnBody).call(vm, { navigateTo: ({ url }) => routes.push(url) })
    assert.match(routes[0], /recordId=41$/)
    assert.ok(routes[0].includes('funding') || routes[0].includes('FUNDING_APPROVAL'))
    assert.deepEqual(vm.leaveContext, {})
  })
  test(`${role} material page accepts funding context and returns to the same funding application`, async () => {
    const source = fs.readFileSync(new URL(`../src/pages/${role}/affairs/index.vue`, import.meta.url), 'utf8')
    const assignment = source.match(/this\.leaveContext = ([^\n]+)/)[1]
    const returnBody = source.match(/(?:async )?returnToApplication\(\) \{(.*) \},/)[1]
    const vm = { leaveContext: {} }, routes = [], query = { bizType: 'FUNDING', bizId: '41' }
    vm.leaveContext = new Function('query', `return ${assignment}`)(query)
    assert.deepEqual(vm.leaveContext, query)
    vm.go = async url => routes.push(url)
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
    await new AsyncFunction('uni', returnBody).call(vm, { navigateTo: ({ url }) => routes.push(url) })
    assert.equal(routes[0], role === 'teacher' ? '/pages/teacher/affairs-review/index?type=FUNDING_APPROVAL&recordId=41' : '/pages/student/affairs/funding?recordId=41')
  })
}
