import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..')
const sourceRoot = path.join(root, 'src')

function vueFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(dir, entry.name)
    return entry.isDirectory() ? vueFiles(target) : (entry.name.endsWith('.vue') ? [target] : [])
  })
}

test('学生门户业务页统一使用 AppDatePicker', () => {
  const componentPath = path.join(sourceRoot, 'components', 'AppDatePicker.vue')
  assert.equal(fs.existsSync(componentPath), true)
  const violations = vueFiles(sourceRoot)
    .filter((file) => file !== componentPath)
    .filter((file) => /<input\b[^>]*\btype=["'](?:date|datetime-local)["']/i.test(fs.readFileSync(file, 'utf8')))
    .map((file) => path.relative(root, file))
  assert.deepEqual(violations, [])
})

test('公共日期组件提供统一 v-model 与起止约束', () => {
  const source = fs.readFileSync(path.join(sourceRoot, 'components', 'AppDatePicker.vue'), 'utf8')
  assert.match(source, /update:modelValue/)
  assert.match(source, /role === 'end'/)
  assert.match(source, /role === 'start'/)
  assert.match(source, /aria-label/)
})
