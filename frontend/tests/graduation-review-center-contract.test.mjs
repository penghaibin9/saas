import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('W7 keeps review-tasks route identity and reuses the Gold Reader', () => {
  const routes = read('src/modules/graduation/routes.js')
  const finalView = read('src/modules/graduation/views/FinalSubmissionListView.vue')
  const workspace = read('src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue')

  assert.match(routes, /review-tasks/)
  assert.match(routes, /graduation-review-tasks/)
  assert.match(routes, /graduationDesign\.review\.view/)
  assert.match(finalView, /GraduationDocumentReviewWorkspace/)
  assert.match(workspace, /AppDocumentViewer/)
  assert.match(workspace, /FileEvidencePanel/)
})

test('W7.0 does not add a universal review-center write endpoint', () => {
  const api = read('src/modules/graduation/api/graduation-defense-grade.api.js')
  assert.doesNotMatch(api, /review-center\/submit/)
  assert.match(api, /gd-reviews/)
})
