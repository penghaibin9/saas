import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const positionForm = fs.readFileSync(new URL('../src/modules/internship/views/PositionFormView.vue', import.meta.url), 'utf8')
const exceptionDetail = fs.readFileSync(new URL('../src/modules/internship/views/AttendanceExceptionDetailView.vue', import.meta.url), 'utf8')

test('position form persists a complete geofence and explains frozen placement rules', () => {
  for (const field of ['geofenceLat', 'geofenceLng', 'geofenceRadiusM']) assert.match(positionForm, new RegExp(field))
  assert.match(positionForm, /正式落岗会冻结本次围栏规则/)
  assert.match(positionForm, /低精度和围栏边界记录会转教师人工核验/)
})

test('teacher exception detail shows factual location evidence without fake device claims', () => {
  assert.match(exceptionDetail, /定位证据对照/)
  assert.match(exceptionDetail, /当前客户端未提供可信检测/)
  assert.doesNotMatch(exceptionDetail, /detail\.mockDetect/)
  assert.doesNotMatch(exceptionDetail, /detail\.systemRisk/)
})
