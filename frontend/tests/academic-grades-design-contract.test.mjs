import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = name => readFileSync(new URL(`../src/modules/academicAffairs/views/${name}`, import.meta.url), 'utf8')

test('shared grade import and export routes present their own designed page identity', () => {
  const entry = read('AaGradeEntryView.vue')
  const transcript = read('AaTranscriptView.vue')
  assert.match(entry, /pageTitle\(\).*importMode \? '成绩导入' : '成绩录入'/)
  assert.match(entry, /与正式名单和成绩方案匹配后才能确认/)
  assert.match(transcript, /pageTitle\(\).*exportMode \? '成绩导出' : '学生成绩单'/)
  assert.match(transcript, /查询件与正式证明分开，导出用途写入审计/)
})

test('grade pages keep fail count wording separate from warning count and hide scan diagnostics', () => {
  const publish = read('AaGradePublishView.vue')
  const change = read('AaGradeChangeView.vue')
  assert.match(publish, /不及格人数不能替代预警条数/)
  assert.match(publish, /不及格人数 \$\{result\.failedGradeCount/)
  assert.doesNotMatch(change, /p\.ack\.warningScanError/)
  assert.match(change, /正式成绩已生效，后置扫描结果待核对。/)
})

test('uncertain publication replay lock is scoped by authenticated identity and task', () => {
  const publish = read('AaGradePublishView.vue')
  assert.match(publish, /publishLockKey\(taskId, identity = this\.identity\(\)\)/)
  assert.match(publish, /JSON\.stringify\(\[identity, String\(taskId\)\]\)/)
  assert.doesNotMatch(publish, /unconfirmedPublishIds/)
})
