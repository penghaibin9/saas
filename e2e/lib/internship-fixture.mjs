import fs from 'node:fs/promises'
import path from 'node:path'

const REQUIRED = [
  'runId',
  'batchId',
  'batchName',
  'internshipId',
  'studentNo',
  'studentName',
  'mentorName',
  'companyName',
  'positionName'
]

export async function loadInternshipFixture() {
  const target = process.env.E2E_INTERNSHIP_FIXTURE_FILE
    ? path.resolve(process.env.E2E_INTERNSHIP_FIXTURE_FILE)
    : path.resolve(process.cwd(), 'runtime', 'internship-fixture.json')

  let fixture
  try {
    fixture = JSON.parse(await fs.readFile(target, 'utf8'))
  } catch (error) {
    throw new Error(`Unable to read internship E2E fixture ${target}: ${error.message}`)
  }

  for (const key of REQUIRED) {
    if (fixture[key] === undefined || fixture[key] === null || fixture[key] === '') {
      throw new Error(`Internship E2E fixture is missing ${key}: ${target}`)
    }
  }
  return fixture
}
