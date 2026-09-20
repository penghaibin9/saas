import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import {
  createStudentAcademicCommandGuard,
  exactPositiveDecimalId,
  readStudentAcademicSnapshot
} from '../src/components/academic/studentAcademicCommandGuard.js'

const read = (name) => readFileSync(new URL(`../src/views/academic/${name}`, import.meta.url), 'utf8')

const pages = [
  'StudentEvaluationView.vue',
  'StudentRecheckView.vue',
  'StudentMakeupView.vue',
  'StudentRegistrationView.vue',
  'StudentExamView.vue',
  'StudentRecognitionView.vue',
  'StudentMajorSplitView.vue'
]

function deferred() {
  let resolve
  let reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('command guard executes immutable attribution and rejects an identity-switched response', () => {
  let identity = 'student-A'
  const guard = createStudentAcademicCommandGuard(() => identity)
  const command = guard.beginCommand({ taskId: 'T-1', score: 88 })

  assert.equal(Object.isFrozen(command), true)
  assert.equal(guard.isCurrentCommand(command), true)
  assert.throws(() => { command.taskId = 'T-2' }, TypeError)

  identity = 'student-B'
  assert.equal(guard.isCurrentCommand(command), false)
})

test('read guard drops an older success and a response from another identity', async () => {
  let identity = 'student-A'
  const guard = createStudentAcademicCommandGuard(() => identity)
  const oldRead = deferred()
  const newRead = deferred()
  const oldResultPromise = readStudentAcademicSnapshot(guard, () => oldRead.promise)
  const newResultPromise = readStudentAcademicSnapshot(guard, () => newRead.promise)

  oldRead.resolve(['old-private-row'])
  const oldResult = await oldResultPromise
  assert.equal(oldResult.ok, false)
  assert.equal(oldResult.stale, true)

  identity = 'student-B'
  newRead.resolve(['student-A-row'])
  const switched = await newResultPromise
  assert.equal(switched.ok, false)
  assert.equal(switched.stale, true)
})

test('independent read scopes do not cancel each other', async () => {
  const guard = createStudentAcademicCommandGuard(() => 'student-A')
  const records = deferred()
  const courses = deferred()
  const recordResult = readStudentAcademicSnapshot(guard, () => records.promise, 'records')
  const courseResult = readStudentAcademicSnapshot(guard, () => courses.promise, 'courses')
  records.resolve(['record'])
  courses.resolve(['course'])
  assert.deepEqual((await recordResult).value, ['record'])
  assert.deepEqual((await courseResult).value, ['course'])
})

test('failed formal reread cannot turn a matching historical array row into success', async () => {
  const guard = createStudentAcademicCommandGuard(() => 'student-A')
  const command = guard.beginCommand({ key: 'grade:9007199254740993' })
  const uncertain = new Set([command.key])
  const historicalRows = [{ recheckId: 'ACK-1', acadGradeId: '9007199254740993' }]
  const readResult = await readStudentAcademicSnapshot(guard, async () => { throw Object.assign(new Error('offline'), { network: true }) })
  const formal = readResult.ok && guard.isCurrentCommand(command)
    ? historicalRows.find((row) => row.recheckId === 'ACK-1')
    : null

  assert.equal(readResult.ok, false)
  assert.equal(formal, null)
  assert.equal(uncertain.has(command.key), true)
})

test('403 invalidation clears private state while retaining the original uncertain reference', async () => {
  const guard = createStudentAcademicCommandGuard(() => 'student-A')
  const command = guard.beginCommand({ key: 'defer:D-9' })
  const uncertain = new Set([command.key])
  let privateRows = [{ studentNo: 'S-A' }]
  const forbidden = Object.assign(new Error('forbidden'), { status: 403 })
  const readResult = await readStudentAcademicSnapshot(guard, async () => { throw forbidden })
  assert.equal(readResult.error, forbidden)

  privateRows = []
  guard.invalidate()
  assert.deepEqual(privateRows, [])
  assert.equal(uncertain.has(command.key), true)
  assert.equal(guard.isCurrentCommand(command), false)
})

test('positive decimal ids reject already-corrupted numbers and preserve exact strings', () => {
  assert.equal(exactPositiveDecimalId(9007199254740993), '')
  assert.equal(exactPositiveDecimalId('9007199254740993'), '9007199254740993')
  assert.equal(exactPositiveDecimalId('0'), '')
  assert.equal(exactPositiveDecimalId('-1'), '')
  assert.equal(exactPositiveDecimalId('1e3'), '')
})

test('seven student application pages use the executable read and command guard', () => {
  for (const page of pages) {
    const source = read(page)
    assert.match(source, /guard\.beginCommand\(/, `${page} must freeze commands through the tested guard`)
    assert.match(source, /systemConfirm\(/, `${page} must confirm the frozen object inside the portal`)
    assert.match(source, /readStudentAcademicSnapshot\(/, `${page} must apply reads through the tested guard`)
    assert.match(source, /guard\.isCurrentCommand\(command\)/, `${page} must reject obsolete command responses`)
    assert.match(source, /onBeforeUnmount\(\(\) => guard\.dispose\(\)\)/, `${page} must invalidate reads and commands when left`)
    assert.match(source, /academicErrorKind\(.+\) === 'forbidden'/, `${page} must clear sensitive read state after 403`)
  }
})

test('recheck preserves bigint grade ids and needs exact ACK plus formal source id', () => {
  const source = read('StudentRecheckView.vue')
  assert.match(source, /exactPositiveDecimalId\(selectedGradeId\.value\)/)
  assert.match(source, /acadGradeId: command\.gradeId/)
  assert.match(source, /result\?\.recheckId/)
  assert.match(source, /formal\.acadGradeId \|\| formal\.gradeId/)
  assert.match(source, /uncertainGradeId\.value = command\.gradeId/)
})

test('recognition never attributes a network timeout to a same-name historical row', () => {
  const source = read('StudentRecognitionView.vue')
  assert.doesNotMatch(source, /kind === 'network' \? formalRows\.find/)
  assert.match(source, /result\?\.recognitionId/)
  assert.match(source, /String\(formal\.targetCourseId\) === command\.payload\.targetCourseId/)
  assert.match(source, /uncertainCommandKey\.value = command\.key/)
})

test('remaining workflows keep exact business attribution keys', () => {
  const makeup = read('StudentMakeupView.vue')
  assert.match(makeup, /formal\.originGradeId \|\| formal\.gradeId/)
  assert.match(makeup, /formal\.course\?\.id \|\| formal\.courseId/)

  const exam = read('StudentExamView.vue')
  assert.match(exam, /result\?\.deferId/)
  assert.match(exam, /formal\.examCourseId/)

  const registration = read('StudentRegistrationView.vue')
  assert.match(registration, /result\?\.deferralId/)
  assert.match(registration, /String\(formal\.deferralId\) === String\(resultId\)/)

  const evaluation = read('StudentEvaluationView.vue')
  assert.match(evaluation, /result\?\.taskId/)
  assert.match(evaluation, /formal\?\.submitted === true/)

  const major = read('StudentMajorSplitView.vue')
  assert.match(major, /result\?\.volunteerId/)
  assert.match(major, /String\(formal\.batchId \|\| ''\) === command\.batchId/)
  assert.match(major, /JSON\.stringify\(command\.choices\)/)
})
