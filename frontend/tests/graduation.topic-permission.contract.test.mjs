import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const here = dirname(fileURLToPath(import.meta.url))
const src = (path) => readFileSync(resolve(here, '..', path), 'utf8')

const routes = src('src/modules/graduation/routes.js')
const workspaces = src('src/modules/graduation/config/graduationWorkspaces.js')
const topicLib = src('src/modules/graduation/views/TopicLibListView.vue')
const rounds = src('src/modules/graduation/views/TopicRoundListView.vue')

test('topic library and round routes do not use retired aggregate aliases', () => {
  for (const source of [routes, workspaces]) {
    assert.doesNotMatch(source, /graduationDesign\.topic\.lib/)
    assert.doesNotMatch(source, /graduationDesign\.topic\.round/)
  }
})

test('topic library separates read, create, review and export permissions', () => {
  assert.match(topicLib, /canTopicView\(\)[^{]*\{[^}]*topic\.view/)
  assert.match(topicLib, /canTopicCreate\(\)[^{]*\{[^}]*topic\.create/)
  assert.match(topicLib, /canTopicReview\(\)[^{]*\{[^}]*topic\.review/)
  assert.match(topicLib, /canTopicExport\(\)[^{]*\{[^}]*topic\.export/)
  assert.match(topicLib, /v-if="canTopicReview && activePanel === 'pending'/)
  assert.match(topicLib, /v-if="canTopicCreate"[\s\S]*AppExcelImportDrawer/)
})

test('topic rounds separate match, review, assign, import and export actions', () => {
  for (const code of ['topic.match', 'topic.review', 'topic.assign', 'topic.create', 'topic.export']) {
    assert.match(rounds, new RegExp(code.replace('.', '\\.')))
  }
  assert.match(rounds, /canTopicMatch && \(row\.status === 'OPEN' \|\| row\.status === 'CLOSED'\)/)
  assert.match(rounds, /v-if="canTopicReview"[^>]*@click="askConfirmChoice/)
  assert.match(rounds, /v-if="canTopicAssign"[^>]*@click="askWithdraw/)
})
