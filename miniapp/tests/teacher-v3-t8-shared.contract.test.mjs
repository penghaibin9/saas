import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..', '..')
const read = (path) => readFileSync(resolve(repo, path), 'utf8')

test('T8 教师待办消费 shared NetworkPager + runAction，不再手写 group 路由表', () => {
  const page = read('miniapp/src/pages/teacher/todos/index.vue')
  assert.match(page, /createNetworkPager/)
  assert.match(page, /runAction\(todo && todo\.action, \{ side: 'teacher' \}\)/)
  assert.match(page, /teacherTodoT8Api/)
  assert.doesNotMatch(page, /const map\s*=\s*\{/)
  assert.doesNotMatch(page, /map\[todo\.group\]/)
  assert.doesNotMatch(page, /getTodosPage\(/)
})

test('T8 教师待办 API 走 grouped continuous server cursor', () => {
  const api = read('miniapp/src/services/teacherTodoT8Api.js')
  assert.match(api, /\/teacher-mobile\/todos\/grouped-continuous/)
  assert.match(api, /cursor=/)
  assert.match(api, /pageSize=/)
})

test('T8 巡访附件消费 shared MobileAttachmentPicker，不再复制 fileSdk 上传轮询', () => {
  const form = read('miniapp/src/components/teacher/InternshipVisitEvidenceForm.vue')
  assert.match(form, /<MobileAttachmentPicker/)
  assert.match(form, /:file-ids="evidenceFileIds"/)
  assert.match(form, /@update:fileIds="evidenceFileIds = \$event"/)
  assert.match(form, /@update:ready="evidenceReady = \$event"/)
  assert.match(form, /biz-purpose="INTERNSHIP_VISIT"/)
  assert.match(form, /fileIds: this\.evidenceFileIds/)
  assert.doesNotMatch(form, /from '@\/services\/fileSdk'/)
  assert.doesNotMatch(form, /chooseAndUpload|refreshFile/)
})

test('T8 就业核验附件也消费 shared picker，正式 FileBinding 仍由业务命令完成', () => {
  const page = read('miniapp/src/pages/teacher/employment-follow/index.vue')
  assert.match(page, /<MobileAttachmentPicker/)
  assert.match(page, /biz-purpose="EMPLOYMENT_MATERIAL"/)
  assert.match(page, /setEvidenceFileIds\(m, \$event\)/)
  assert.match(page, /setEvidenceReady\(m, \$event\)/)
  assert.match(page, /teacherEmploymentV3Api\.bindMaterialEvidence\(m\.id/)
  assert.match(page, /fileSdk\.open\(m\.file\.fileId\)/)
  assert.doesNotMatch(page, /fileSdk\.choose|fileSdk\.upload|fileSdk\.metadata/)
})

test('T8 handoff import 无副作用且有独立 downstream machine verifier', () => {
  const generator = read('miniapp/scripts/generate-v3-handoff.mjs')
  const verifier = read('miniapp/scripts/verify-v3-handoff-downstream.mjs')
  const workflow = read('.github/workflows/miniapp-teacher-v3-t8-handoff.yml')
  assert.match(generator, /function isCliEntry\(\)/)
  assert.match(generator, /if \(isCliEntry\(\)\)/)
  assert.match(verifier, /merge-base', '--is-ancestor'/)
  assert.match(verifier, /SHARED_FIELDS/)
  assert.match(verifier, /alembicHead\.includes\(','\)/)
  assert.match(workflow, /fetch-depth:\s*0/)
  assert.match(workflow, /verify-v3-handoff-downstream\.mjs/)
})

test('T8 shared search shell 保持 side-aware，Teacher server search 留到 T9', () => {
  const providers = read('miniapp/src/services/searchProviders.js')
  const shell = read('miniapp/src/pages/common/search/index.vue')
  assert.match(providers, /const teacherProvider = \{/)
  assert.match(providers, /serverSide:\s*false/)
  assert.match(providers, /side === 'teacher' \? teacherProvider : studentProvider/)
  assert.doesNotMatch(shell, /teacherApi|studentApi/)
})

test('T8 bootstrap 继续 de-hoist：main 不装教师 API，教师 installer 仅显式消费', () => {
  const main = read('miniapp/src/main.js')
  const installer = read('miniapp/src/services/mobilePerformanceInstaller.teacher.js')
  assert.doesNotMatch(main, /mobilePerformanceInstaller|ensureTeacherPerformanceApi/)
  assert.match(installer, /export function ensureTeacherPerformanceApi\(\)/)
  assert.match(installer, /if \(installed\) return teacherApi/)
})
