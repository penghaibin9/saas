import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

for (const [name, mainPath, projectionPath] of [
  ['student PC', 'student-portal/src/main.js', 'student-portal/src/services/affairsAllowedActions.js'],
  ['student miniapp', 'miniapp/src/main.js', 'miniapp/src/services/affairsAllowedActions.js']
]) {
  test(`${name} uses server allowedActions before legacy booleans`, () => {
    const main = read(mainPath)
    const source = read(projectionPath)
    assert.match(main, /services\/affairsAllowedActions/)
    assert.match(source, /Array\.isArray\(row(?:\?\.| && row\.)allowedActions\)/)
    assert.match(source, /allowedActions\.includes\(action\)/)
    assert.match(source, /\['EDIT_RETURNED', 'RESUBMIT'\]/)
    assert.match(source, /'SUBMIT_CANCEL'/)
    assert.match(source, /'SUBMIT_EXTENSION'/)
    assert.match(source, /'SUBMIT_OBJECTION'/)
    assert.match(source, /'SUBMIT_APPEAL'/)
  })
}
