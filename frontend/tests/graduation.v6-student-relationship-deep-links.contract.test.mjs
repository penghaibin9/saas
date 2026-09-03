import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const [topic, mentor, defense, group] = await Promise.all([
  readFile(new URL('../src/modules/graduation/views/GraduationStudentAssignTopicView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/modules/graduation/views/GraduationMentorAssignView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/modules/graduation/views/GraduationStudentDefenseView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/modules/graduation/views/GraduationStudentGroupView.vue', import.meta.url), 'utf8')
])

for (const [name, source] of [['topic', topic], ['mentor', mentor], ['defense', defense], ['group', group]]) {
  test(`V6 ${name} relationship page is a real workflow rather than a one-field white page`, () => {
    assert.match(source, /GraduationFormPageShell/)
    assert.match(source, /#context/)
    assert.match(source, /#aside/)
    assert.match(source, /保存前检查/)
    assert.match(source, /保存后的(?:下一步|真实流转)/)
    assert.match(source, /safeReturnTo/)
    assert.match(source, /beforeRouteLeave/)
    assert.match(source, /next\(false\)/)
    assert.match(source, /Object\.freeze\(/)
    assert.match(source, /gdStudentApi\.getStudentDetail/)
    assert.match(source, /勿重复提交/)
  })
}

test('V6 topic assignment preserves the canonical API and confirms the exact topic relation from the student master', () => {
  assert.match(topic, /gdStudentApi\.assignTopic\(target\.studentId, \{ topicId: target\.topicId \}\)/)
  assert.match(topic, /String\(latest\.data\?\.topicId \|\| ''\) !== target\.topicId/)
  assert.match(topic, /不会自动改导师/)
  assert.match(topic, /批次、题目状态、容量和学生当前阶段/)
})

test('V6 mentor assignment keeps qualification/capacity rules, canonical assign/change APIs and server readback', () => {
  assert.match(mentor, /AppAvailableGraduationMentorPicker/)
  assert.match(mentor, /graduationDesign\.student\.manage/)
  assert.match(mentor, /graduationDesign\.topic\.assign/)
  assert.match(mentor, /graduationMentorApi\.changeMentor\(target\.studentId, target\.mentorId, target\.reason\)/)
  assert.match(mentor, /graduationMentorApi\.assignMentor\(target\.studentId, target\.mentorId, target\.reason\)/)
  assert.match(mentor, /expectedMentorName = String\(response\.data\?\.mentorName \|\| ''\)/)
  assert.match(mentor, /latest\.data\.advisorName !== expectedMentorName/)
  assert.match(mentor, /已认证且未满员/)
  assert.match(mentor, /原分配记录保留为历史/)
})

test('V6 defense-group assignment preserves the canonical API and exact group readback', () => {
  assert.match(defense, /AppDefenseGroupPicker/)
  assert.match(defense, /gdStudentApi\.assignDefenseGroup\(target\.studentId, \{[\s\S]*defenseGroupId: target\.defenseGroupId,[\s\S]*reason: target\.reason/)
  assert.match(defense, /String\(latest\.data\?\.defenseGroupId \|\| ''\) !== target\.defenseGroupId/)
  assert.match(defense, /时间、地点、评委、秘书、容量和回避冲突/)
  assert.match(defense, /分配不等于发布/)
})

test('V6 process grouping distinguishes single and batch writes and verifies a durable result', () => {
  assert.match(group, /batchMode/)
  assert.match(group, /recordIds/)
  assert.match(group, /gdStudentApi\.batchSetStudentGroup\(\{ recordIds: target\.recordIds, groupName: target\.groupName, reason: target\.reason \}\)/)
  assert.match(group, /gdStudentApi\.setStudentGroup\(target\.studentId, \{ groupName: target\.groupName, reason: target\.reason \}\)/)
  assert.match(group, /String\(latest\.data\?\.studentGroup \|\| ''\) !== target\.groupName/)
  assert.match(group, /服务器未报告实际更新人数/)
  assert.match(group, /不会修改行政班级、指导教师、题目、答辩组或最终毕业资格/)
})

test('V6 relationship pages preserve batch page keyword and precise returnTo context', () => {
  for (const source of [topic, mentor, defense, group]) {
    assert.match(source, /returnTo/)
    assert.match(source, /batchId/)
  }
  assert.match(mentor, /query\.set\('keyword'/)
  assert.match(mentor, /query\.set\('page'/)
  assert.match(defense, /query\.set\('keyword'/)
  assert.match(defense, /query\.set\('page'/)
  assert.match(group, /for \(const key of \['batchId', 'page', 'keyword', 'source'\]\)/)
})
