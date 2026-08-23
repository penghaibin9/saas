import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const productView = fs.readFileSync(path.join(root, 'src/views/official-site/OfficialProductView.vue'), 'utf8')
const salesView = fs.readFileSync(path.join(root, 'src/views/official-site/OfficialSalesPageView.vue'), 'utf8')

test('product demo CTAs preserve the originating product slug', () => {
  assert.match(productView, /contactRoute\(\)/)
  assert.match(productView, /query:\s*\{\s*product:\s*this\.product\?\.slug/)
  assert.ok((productView.match(/:to="contactRoute"/g) || []).length >= 4)
})

test('contact form maps product source to the customer-facing interest', () => {
  for (const [slug, label] of [
    ['academic-affairs', '教务系统'],
    ['student-affairs', '学工中心'],
    ['graduation', '毕业设计'],
    ['internship', '岗位实习']
  ]) {
    assert.ok(salesView.includes(`'${slug}': '${label}'`) || salesView.includes(`${slug}: '${label}'`))
  }
  assert.match(salesView, /interest:\s*'学生全生命周期平台'/)
  assert.match(salesView, /\$route\.query\.product/)
})

test('contact form keeps the no-database privacy statement visible', () => {
  assert.match(salesView, /不进入业务数据库/)
  assert.match(salesView, /不会写入跃科业务数据库/)
})
