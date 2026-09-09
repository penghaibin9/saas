import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = process.cwd()
const student = fs.readFileSync(path.join(root, 'src/pages/student/affairs/reduction.vue'), 'utf8')
const teacher = fs.readFileSync(path.join(root, 'src/pages/teacher/affairs/reduction/index.vue'), 'utf8')
const pages = fs.readFileSync(path.join(root, 'src/pages.json'), 'utf8')
const realApi = fs.readFileSync(path.join(root, 'src/services/realApi.js'), 'utf8')

test('both mini programs register the reduction workflow', () => {
  assert.match(pages, /affairs\/reduction/)
  assert.match(pages, /affairs\/reduction\/index/)
  assert.match(student, /biz-purpose="REDUCTION"/)
  assert.match(realApi, /mobile\/affairs\/fee-reductions/)
  assert.match(realApi, /mobile\/teacher\/affairs\/fee-reductions/)
})

test('mobile workflows keep tasks and next actions compact', () => {
  assert.match(student, /RESUBMIT/)
  assert.match(student, /WITHDRAW/)
  assert.match(teacher, /status:'SUBMITTED'/)
  assert.match(teacher, /APPROVE.*RETURN.*REJECT.*FULFILL/s)
  assert.match(teacher, /确认减免/)
  assert.match(teacher, /登记发放/)
})
