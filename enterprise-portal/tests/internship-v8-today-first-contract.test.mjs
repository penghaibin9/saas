import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const home = readFileSync(new URL('../src/views/EnterpriseHomeView.vue', import.meta.url), 'utf8')
const service = readFileSync(new URL('../../backend/app/modules/internship/services/internship_enterprise_position_service.py', import.meta.url), 'utf8')

test('V8 enterprise home puts Today First concrete objects before KPI metrics', () => {
  const today = home.indexOf('今天要做什么')
  const metrics = home.indexOf('当前招聘季关键数字')

  assert.ok(today >= 0)
  assert.ok(metrics > today)
  assert.match(home, /task\.whyHere/)
  assert.match(home, /task\.recentChange/)
  assert.match(home, /task\.waitingOn/)
  assert.match(home, /task\.nextActor/)
  assert.match(home, /系统不会把加载失败显示为无待办/)
})

test('V8 enterprise Today tasks are bounded exact objects with resumable routes', () => {
  assert.match(service, /page_size=3, decision_status="PENDING"/)
  assert.match(service, /\.limit\(2\)/)
  assert.match(service, /"objectType": "INTERNSHIP_APPLICATION"/)
  assert.match(service, /"objectType": "INTERNSHIP_POSITION"/)
  assert.match(service, /f"\/applications\/\{application_id\}"/)
  assert.match(service, /f"\/positions\/\{position_id\}\/edit"/)
  assert.match(service, /"resumeKey": f"enterprise:application:/)
  assert.match(service, /"nextActor": "如选择拟接收，下一步仍由学校最终确认正式落岗"/)
  assert.doesNotMatch(service, /"href": "\/applicants"/)
})
