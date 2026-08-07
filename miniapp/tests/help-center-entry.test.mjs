import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const pages = read('src/pages.json')
const env = read('src/config/env.js')
const helpPage = read('src/pages/common/help/index.vue')
const studentMe = read('src/pages/student/me/index.vue')
const teacherMe = read('src/pages/teacher/me/index.vue')

test('miniapp registers one shared help page', () => {
  assert.match(pages, /"pages\/common\/help\/index"/)
  assert.equal((pages.match(/"pages\/common\/help\/index"/g) || []).length, 1)
})

test('student and teacher personal centers both open the shared help page', () => {
  assert.match(studentMe, /row\.key === 'help'.*pages\/common\/help\/index/s)
  assert.match(teacherMe, /row\.key === 'help'.*pages\/common\/help\/index/s)
  assert.doesNotMatch(studentMe, /help[^\n]+即将开放/)
  assert.doesNotMatch(teacherMe, /help[^\n]+即将开放/)
})

test('help center URL is deployment-configured and not hardcoded to one SaaS domain', () => {
  assert.match(env, /VITE_HELP_CENTER_URL/)
  assert.match(env, /helpCenterUrl:\s*resolveDocUrl\('VITE_HELP_CENTER_URL'\)/)
  assert.doesNotMatch(env, /https:\/\/hnyueke\.com\/admin\/help/)
  assert.doesNotMatch(helpPage, /https:\/\/hnyueke\.com/)
})

test('shared help webview carries normalized role and miniapp source', () => {
  assert.match(helpPage, /<web-view[^>]+:src="helpUrl"/)
  assert.match(helpPage, /role:\s*normalizeHelpRole\(session\)/)
  assert.match(helpPage, /source:\s*'miniapp'/)
  assert.match(helpPage, /SCHOOL_ADMIN/)
  assert.match(helpPage, /ACADEMIC/)
  assert.match(helpPage, /COUNSELOR/)
  assert.match(helpPage, /return 'student'/)
  assert.match(helpPage, /return 'teacher'/)
})

test('missing deployment URL fails visibly instead of opening a fake link', () => {
  assert.match(helpPage, /帮助中心尚未配置访问地址/)
  assert.match(helpPage, /VITE_HELP_CENTER_URL/)
  assert.match(helpPage, /微信公众平台.*业务域名/)
  assert.match(helpPage, /不在小程序复制第二套内容/)
})
