import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const view = readFileSync(new URL('../src/views/EvaluationTaskListView.vue', import.meta.url), 'utf8')
const service = readFileSync(new URL('../../backend/app/modules/internship/services/internship_enterprise_collaboration_service.py', import.meta.url), 'utf8')

test('Enterprise evaluation submit uses server identity, CAS on resubmit and placement receipt', () => {
  assert.match(view, /payload\.expectedVersion=selected\.value\.evaluationVersion/)
  assert.match(view, /placementSnapshotId:result\?\.placementSnapshotId/)
  assert.match(view, /安置快照/)
  assert.match(view, /系统自动留痕/)
  assert.doesNotMatch(view, /companyId:Number\(form|mentorId:Number\(form/)
})

test('Enterprise current-task reads cannot reuse an evaluation from an old placement', () => {
  const binding = 'InternshipEnterpriseEval.placement_snapshot_id == InternshipRecord.current_placement_snapshot_id'
  assert.ok(service.split(binding).length - 1 >= 2)
  assert.match(service, /InternshipEnterpriseEval\.enterprise_id == InternshipRecord\.enterprise_id/)
  assert.match(service, /InternshipEnterpriseEval\.position_id == InternshipRecord\.position_id/)
  assert.match(service, /elif evaluation:/)
  assert.match(service, /保留旧评价作为历史证据/)
  assert.match(service, /placement_snapshot_id=placement\.id/)
})
