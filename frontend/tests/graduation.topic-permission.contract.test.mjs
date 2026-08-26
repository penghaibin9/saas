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
const topicManage = src('src/modules/graduation/views/TopicManageView.vue')
const topicDetail = src('src/modules/graduation/views/TopicManageDetailView.vue')
const changeList = src('src/modules/graduation/views/TopicChangeRequestListView.vue')
const changeDetail = src('src/modules/graduation/views/TopicChangeDetailView.vue')

test('graduation topic routes and navigation do not use retired aggregate aliases', () => {
  for (const source of [routes, workspaces]) {
    for (const alias of ['lib', 'round', 'manage', 'change']) {
      assert.doesNotMatch(source, new RegExp(`graduationDesign\\.topic\\.${alias}`))
    }
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

test('topic management separates maintenance, assignment and export actions', () => {
  assert.match(topicManage, /canTopicCreate\(\)[^{]*\{[^}]*topic\.create/)
  assert.match(topicManage, /canTopicAssign\(\)[^{]*\{[^}]*topic\.assign/)
  assert.match(topicManage, /canTopicExport\(\)[^{]*\{[^}]*topic\.export/)
  assert.match(topicManage, /v-if="canTopicAssign"[\s\S]*>分配学生<\/button>/)
})

test('topic detail actually loads and no longer uses the legacy write permission string', () => {
  assert.doesNotMatch(topicDetail, /graduation:topic:write/)
  assert.match(topicDetail, /\n  mounted\(\) \{\n    this\.load\(\)\n  \},\n  methods:/)
  assert.match(topicDetail, /goEdit\(\) \{/)
  assert.match(topicDetail, /canTopicCreate/)
  assert.match(topicDetail, /canTopicAssign/)
})

test('topic change list and detail require review permission for approve or reject', () => {
  for (const source of [changeList, changeDetail]) {
    assert.match(source, /canTopicReview\(\)[^{]*\{[^}]*topic\.review/)
    assert.match(source, /if \(!this\.canTopicReview\) return/)
  }
})
