import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (relative) => fs.readFileSync(new URL(`../${relative}`, import.meta.url), 'utf8')

test('graduation landing shows the workbench before return-and-resubmit history', () => {
  const closure = read('src/views/graduation/GraduationStudentClosureView.vue')
  assert.ok(closure.indexOf('<GraduationWorkbenchView') < closure.indexOf('<GraduationFeedbackResubmitView'))
})

test('student-facing evidence is human-first while technical evidence remains available on demand', () => {
  const feedback = read('src/views/graduation/GraduationFeedbackResubmitView.vue')
  const materials = read('src/views/graduation/GraduationMaterialsView.vue')
  assert.doesNotMatch(feedback, /W7\.5 ·/)
  for (const source of [feedback, materials]) {
    assert.match(source, /<details/)
    assert.match(source, /FileVersion/)
    assert.match(source, /SHA/)
  }
})

test('topic selection uses searchable true cursor pages and keeps the approved topic pinned', () => {
  const page = read('src/views/graduation/GraduationWorkbenchView.vue')
  const api = read('src/services/portalApi.js')
  for (const token of ['topicKeyword', 'topicCategory', 'topicAdvisor', 'topicsNextCursor', 'topicsHasMore']) {
    assert.ok(page.includes(token), `missing ${token}`)
  }
  assert.match(page, /v-if="hasTopic" class="gd-topic-pinned" aria-label="当前已选课题"/)
  assert.match(page, /\{\{ my\.topicTitle \|\| '课题信息待同步' \}\}/,
    'the pinned card must show the server-owned selected topic, not a filtered candidate')
  assert.match(page, /剩余 \{\{ topic\.remaining/)
  assert.match(page, /loadTopics\(false\)/)
  assert.match(api, /pageSize: 20/)
  assert.match(api, /URLSearchParams/)
  assert.doesNotMatch(api, /pageSize:\s*500/)
})
