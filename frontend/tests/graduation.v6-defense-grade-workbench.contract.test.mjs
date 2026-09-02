import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('../src/modules/graduation/views/GraduationDefenseGradeView.vue', import.meta.url), 'utf8')

test('V6 defense and grade workbench restores canonical batch student mode queue keyword and page context', () => {
  for (const key of ['batchId', 'studentId', 'mode', 'queue', 'keyword', 'page']) {
    assert.ok(source.includes(key), `missing score/grade context key ${key}`)
  }
  assert.match(source, /requestedMode = this\.routeText\(query\.mode\) \|\| \(this\.routeText\(query\.view\) === 'batch'/)
  assert.match(source, /view: undefined/)
  assert.match(source, /mode: this\.mode/)
  assert.match(source, /queue: this\.mode === 'batch'/)
  assert.match(source, /page: this\.mode === 'batch' && this\.batch\.page > 1/)
})

test('V6 score entry and secretary confirmation permissions remain strictly separate', () => {
  assert.match(source, /canEnterScore\(\).*permissionActions\.enterDefenseScore/)
  assert.match(source, /canConfirmScores\(\).*permissionActions\.confirmDefenseScores/)
  assert.match(source, /评委只能提交本人评分；秘书只能确认服务端判定为完整的评分轮次，不能代替评委补分/)
  assert.match(source, /graduationDefenseGradeApi\.confirmScores\(ctx\.studentId\)/)
  assert.match(source, /openForm\('scoreEntry'\)/)
  assert.ok(!source.includes('enterScore({ gdStudentId: snapshot.studentId'), 'secretary confirmation must not synthesize judge scores')
})

test('V6 student panel and grade-ledger reads are latest-wins and context-bound', () => {
  for (const token of ['studentLoadToken', 'restoreToken', 'plagiarismToken', 'reviewToken', 'scoreToken', 'gradeToken', 'batchLoadToken']) {
    assert.ok(source.includes(token), `missing stale-read guard ${token}`)
  }
  assert.match(source, /token !== this\.batchLoadToken/)
  assert.match(source, /snapshot\.batchId !== String\(this\.batchStore\.selectedBatchId/)
  assert.match(source, /snapshot\.studentId === String\(this\.current\?\.id/)
  assert.match(source, /snapshot\.tab === this\.tab/)
})

test('V6 grade ledger uses server pagination and queues instead of filtering the current page', () => {
  assert.match(source, /graduationDefenseGradeApi\.getGrades\(\{ keyword: snapshot\.keyword, status: queue\.status \|\| undefined, missingType: queue\.missingType \|\| undefined, batchId: snapshot\.batchId, page: snapshot\.page, pageSize: state\.pageSize \}\)/)
  assert.match(source, /state\.total = Number\(res\.data\?\.total\) \|\| 0/)
  assert.match(source, /页面不会在当前页二次筛选冒充全量/)
  assert.match(source, /核算 → 复核 → 发布 → 撤回/)
})

test('V6 all direct writes freeze action batch student panel and route, then reread server truth', () => {
  assert.match(source, /createCommandSnapshot\(action, extra = \{\}\)/)
  assert.match(source, /batchId: String\(this\.batchStore\.selectedBatchId/)
  assert.match(source, /studentId: String\(this\.current\?\.id/)
  assert.match(source, /panel: this\.tab/)
  assert.match(source, /route: this\.currentRouteSnapshot\(\)/)
  assert.match(source, /await this\.loadActivePanel\(\)/)
  assert.match(source, /beforeRouteLeave\(to, from, next\)/)
  assert.match(source, /next\(false\)/)
  assert.match(source, /this\.batchStore\.selectBatch\(snapshot\.batchId\)/)
})

test('V6 canonical grade actions keep their original service methods and state order', () => {
  assert.match(source, /graduationDefenseGradeApi\.calculateGrade/)
  assert.match(source, /graduationDefenseGradeApi\.reviewGrade\(ctx\.studentId, \{ action: 'APPROVE' \}\)/)
  assert.match(source, /graduationDefenseGradeApi\.publishGrade\(ctx\.studentId\)/)
  assert.match(source, /openForm\('withdraw'\)/)
  assert.match(source, /服务端会再次校验状态顺序/)
})
