import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const qualification = read('../src/views/admin/orientation/OrientationQualificationView.vue')
const payment = read('../src/views/admin/orientation/PaymentGreenChannelView.vue')
const green = read('../src/views/admin/orientation/OrientationGreenChannelView.vue')
const api = read('../src/modules/orientation/api/orientation.api.js')
const studentPc = read('../../student-portal/src/views/orientation/OrientationView.vue')
const miniApi = read('../../miniapp/src/services/realApi.js')
const miniStudent = read('../../miniapp/src/pages/student/orientation/index.vue')
const miniGreen = read('../../miniapp/src/pages/student/orientation/green-channel/index.vue')
const miniTeacher = read('../../miniapp/src/pages/teacher/orientation/green-channel/index.vue')

test('O4 qualification screens only render the server verdict and blockers', () => {
  assert.match(qualification, /getOrientationQualifications/)
  assert.match(qualification, /row\.verdict/)
  assert.match(qualification, /blockers/)
  assert.match(qualification, /recalculateOrientationQualification/)
  assert.doesNotMatch(qualification, /stage\s*===|blockedStep\s*===/)
  assert.match(studentPc, /my\.value\.qualification\?\.verdictLabel/)
  assert.match(studentPc, /my\.qualification\.blockers/)
  assert.match(miniStudent, /o\.qualification\.verdict/)
  assert.match(miniStudent, /qualificationBlockers/)
})

test('O4 payment and green-channel writes carry real concurrency and idempotency keys', () => {
  assert.match(api, /syncOrientationPayment/)
  assert.match(api, /\/orientation\/payments\/\$\{id\}/)
  assert.match(api, /getOrientationQualifications/)
  assert.match(payment, /expectedVersion: this\.paymentTarget\.paymentVersion/)
  assert.match(payment, /expectedVersion: this\.detailTarget\.version/)
  assert.match(green, /expectedVersion: row\.version/)
  assert.match(studentPc, /clientSubmissionId: materialRequestId\.value/)
  assert.match(studentPc, /clientRequestId: greenRequestId\.value/)
  assert.match(miniGreen, /clientRequestId: this\.clientRequestId/)
  assert.match(miniTeacher, /expectedVersion: target\.version/)
  assert.match(miniTeacher, /reviewDialog/)
  assert.doesNotMatch(miniTeacher, /uni\.showModal/)
})

test('O4 miniapp forwards canonical server qualification and payment facts', () => {
  assert.match(miniApi, /qualification: r\.qualification \|\| null/)
  assert.match(miniApi, /payment: r\.payment \|\| \{\}/)
})
