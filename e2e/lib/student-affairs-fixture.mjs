import fs from 'node:fs/promises'
import path from 'node:path'

const REQUIRED = [
  'studentId',
  'studentNo',
  'studentName',
  'classId',
  'className',
  'counselorUserId',
  'counselorLogin',
  'counselorName',
  'assignmentId'
]

export async function loadStudentAffairsFixture() {
  const target = process.env.E2E_STUDENT_AFFAIRS_FIXTURE_FILE
    ? path.resolve(process.env.E2E_STUDENT_AFFAIRS_FIXTURE_FILE)
    : path.resolve(process.cwd(), 'runtime', 'student-affairs-fixture.json')

  let fixture
  try {
    fixture = JSON.parse(await fs.readFile(target, 'utf8'))
  } catch (error) {
    throw new Error(`Unable to read student-affairs E2E fixture ${target}: ${error.message}`)
  }

  for (const key of REQUIRED) {
    if (fixture[key] === undefined || fixture[key] === null || fixture[key] === '') {
      throw new Error(`Student-affairs E2E fixture is missing ${key}: ${target}`)
    }
  }
  return fixture
}
