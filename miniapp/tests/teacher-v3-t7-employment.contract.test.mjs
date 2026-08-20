import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8')

const api = read('src/services/teacherEmploymentV3Api.js')
const page = read('src/pages/teacher/employment-follow/index.vue')


test('T7 employment API exposes recommendation, verification and formal evidence single-object commands', () => {
  assert.match(api, /\/teacher-mobile\/employment\/overview/)
  assert.match(api, /students\/\$\{enc\(String\(studentId/)
  assert.match(api, /\/recommendations`/)
  assert.match(api, /\/verification`/)
  assert.match(api, /materials\/\$\{enc\(String\(materialId/)
  assert.match(api, /\/evidence`/)
  assert.match(api, /verifications\/\$\{enc\(String\(verificationId/)
  assert.match(api, /\/review`/)
  assert.doesNotMatch(api, /bulk|batch/i)
})


test('T7 recommendation is a real job recommendation with expected student version', () => {
  assert.doesNotMatch(page, /recommend\(s\)\s*\{\s*this\.contact\(s\)/)
  assert.match(page, /teacherEmploymentV3Api\.recommend\(s\.id/)
  assert.match(page, /jobId:\s*Number\(job\.id\)/)
  assert.match(page, /expectedStudentVersion:\s*Number\(s\.version/)
  assert.match(page, /showActionSheet/)
  assert.match(page, /暂无可推荐在招岗位/)
})


test('T7 verification removes PC-only fake closure and uses server versioned commands', () => {
  assert.doesNotMatch(page, /去向核验需在 PC 端完成材料核对/)
  assert.match(page, /teacherEmploymentV3Api\.verification\(studentId\)/)
  assert.match(page, /reviewVerification\(this\.verification\.verificationId/)
  assert.match(page, /expectedVersion:\s*Number\(this\.verification\.version/)
  assert.match(page, /action === 'RETURN'/)
  assert.match(page, /补正意见至少 5 字/)
  assert.match(page, /n\.kind === 'conflict'/)
  assert.match(page, /this\.fetchVerification\(this\.verificationStudentId\)/)
  assert.match(page, /this\.load\(\)/)
})


test('T7 employment material evidence uses public file SDK and secure preview', () => {
  assert.match(page, /import \{ fileSdk \} from '@\/services\/fileSdk'/)
  assert.match(page, /fileSdk\.choose\(/)
  assert.match(page, /fileSdk\.upload\(chosen, \{ bizType: 'TEMP_PRIVATE'/)
  assert.match(page, /fileSdk\.metadata\(id\)/)
  assert.match(page, /teacherEmploymentV3Api\.bindMaterialEvidence\(m\.id/)
  assert.match(page, /expectedVersion:\s*Number\(m\.version/)
  assert.match(page, /fileSdk\.open\(m\.file\.fileId\)/)
  assert.match(page, /legacyFileNameOnly/)
  assert.doesNotMatch(page, /uni\.downloadFile|uni\.getLocation|chooseLocation/)
})


test('T7 writes remain single-object and server-authoritative', () => {
  assert.doesNotMatch(page, /ids\s*:/)
  assert.doesNotMatch(page, /Promise\.all\([^)]*(recommend|reviewVerification|bindMaterialEvidence)/)
  assert.match(page, /岗位推荐已记录/)
  assert.match(page, /正式材料证据已绑定/)
  assert.match(page, /去向已核验/)
})
