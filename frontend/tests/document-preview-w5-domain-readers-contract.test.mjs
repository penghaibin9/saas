import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8')

const courseReader = read('src/modules/academicAffairs/api/course-material-reader.api.js')
const courseDetail = read('src/modules/academicAffairs/views/AaCourseDetailView.vue')
const approvalReader = read('src/modules/approval/api/approval-attachments.api.js')
const approvalDetail = read('src/views/admin/approval/ApprovalDetailView.vue')

test('W5 academic course materials use File Center bytes through inline Reader', () => {
  assert.match(courseReader, /fileSdk\.metadata\(material\.fileId\)/)
  assert.match(courseReader, /fileSdk\.blob\(descriptor\.fileId\)/)
  assert.doesNotMatch(courseReader, /fileSdk\.preview\(/)
  assert.match(courseDetail, /FilePreviewer/)
  assert.match(courseDetail, /inline/)
  assert.match(courseDetail, /materialPreviewProvider/)
  assert.match(courseDetail, /courseMaterialReaderApi\.list\(this\.courseId\)/)
})

test('W5 generic approval attachments use task-scoped business tickets and shared Viewer', () => {
  assert.match(approvalReader, /\/approvals\/tasks\/\$\{encodeURIComponent\(taskId\)\}\/attachments/)
  assert.match(approvalReader, /\/files\/\$\{encodeURIComponent\(fileId\)\}\/ticket/)
  assert.match(approvalReader, /body: \{ action \}/)
  assert.match(approvalReader, /fileSdk\.blobFrom\(ticketPath\(ticket\)\)/)
  assert.match(approvalReader, /fileSdk\.downloadFrom\(ticketPath\(ticket\)/)
  assert.doesNotMatch(approvalReader, /authorizedUrl|fileSdk\.preview\(/)
  assert.match(approvalDetail, /AppDocumentViewer/)
  assert.match(approvalDetail, /approvalAttachmentsApi\.createPreviewProvider\(this\.task\.taskId\)/)
  assert.match(approvalDetail, /approvalAttachmentsApi\.download\(this\.task\.taskId, file\)/)
})
