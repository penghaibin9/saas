import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

// 本文件位于 frontend/tests；仓库根目录需向上两级。
const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('teacher miniapp approves the version visible in the list', () => {
  const source = read('miniapp/src/pages/teacher/affairs-review/index.vue')
  assert.match(source, /visibleVersion\(row, detail\)/)
  assert.match(source, /const visible = this\.versionOf\(row\)/)
  assert.match(source, /记录已被他人修改，请刷新后重新查看并确认/)
  assert.doesNotMatch(source, /version:\s*detail\.version/)
})

test('PC dorm checkout sends the visible bed version', () => {
  const api = read('frontend/src/modules/studentAffairs/api/dormReliability.api.js')
  const page = read('frontend/src/modules/studentAffairs/views/dorm/DormCheckinView.vue')
  assert.match(api, /body:\s*\{\s*version\s*\}/)
  assert.match(page, /version:\s*bd\.version/)
  assert.match(page, /dormReliabilityApi\.checkout\(this\.outDlg\.bedId, this\.outDlg\.version\)/)
})

test('student activity checkin never exposes manual checkin action', () => {
  const source = read('miniapp/src/pages/student/affairs/activity.vue')
  assert.match(source, /输入签到码/)
  assert.match(source, /secureActivityCheckin/)
  assert.doesNotMatch(source, /method:\s*['"]MANUAL['"]/)
})

test('student returned applications retain the new version when resubmit fails', () => {
  const aid = read('miniapp/src/pages/student/affairs/aid.vue')
  const funding = read('miniapp/src/pages/student/affairs/funding.vue')
  const leave = read('miniapp/src/pages/student/affairs/leave.vue')
  for (const source of [aid, funding, leave]) {
    assert.match(source, /修改已保存，但重新提交失败/)
    assert.match(source, /version:\s*updated\.version/)
  }
})

test('student portal clears forms only after a successful command', () => {
  const source = read('student-portal/src/views/affairs/AffairsFourEndView.vue')
  assert.match(source, /return \{ ok: true, data \}/)
  assert.match(source, /return \{ ok: false, error: e \}/)
  assert.match(source, /if \(result\.ok\) leaveForm\.reason = ''/)
  assert.match(source, /if \(result\.ok\) aidObjections\[item\.applyId\] = ''/)
  assert.match(source, /if \(result\.ok\) fundAppeals\[item\.applicationId\] = ''/)
  assert.match(source, /modal\.item = \{ \.\.\.\(modal\.item \|\| \{\}\), \.\.\.\(updated \|\| \{\}\), version:/)
  assert.match(source, /修改已保存，但重新提交失败/)
  assert.match(source, /setTimeout\(\(\) => closeModal\(\), 0\)/)
})

test('student portal affairs loads tabs on demand and refreshes only the affected tab', () => {
  const source = read('student-portal/src/views/affairs/AffairsFourEndView.vue')
  assert.match(source, /const TAB_LOADERS = \{/)
  assert.match(source, /leave:\s*\[\{ load: \(\) => portalApi\.affairsLeave\(\)/)
  assert.match(source, /watch\(tab, \(key\) => \{ loadTab\(key\) \}, \{ immediate: true \}\)/)
  assert.match(source, /const inflight = new Map\(\)/)
  assert.match(source, /if \(inflight\.has\(key\)\) return inflight\.get\(key\)/)
  assert.match(source, /if \(!viewActive \|\| loadEpoch\[key\] !== epoch\) return/)
  assert.match(source, /await loadTab\(refreshKey, \{ force: true \}\)/)
  assert.match(source, /'请假提交失败', 'leave'/)
  assert.match(source, /'调宿提交失败', 'dorm'/)
  assert.doesNotMatch(source, /const tasks = \{ leave: portalApi\.affairsLeave\(\), aid: portalApi\.affairsAid\(\)/)
  assert.doesNotMatch(source, /await reload\(\)/)
})

test('teacher editable decisions reopen with the previous text after non-conflict failure', () => {
  const leave = read('miniapp/src/pages/teacher/affairs-leave/index.vue')
  const review = read('miniapp/src/pages/teacher/affairs-review/index.vue')
  const dorm = read('miniapp/src/pages/teacher/dorm-review/index.vue')
  for (const source of [leave, review, dorm]) {
    assert.match(source, /content:\s*initial/)
    assert.match(source, /n\.kind !== 'conflict'/)
    assert.match(source, /setTimeout\(/)
  }
})

test('mental follow-up and talk records keep inline text until success', () => {
  const mental = read('miniapp/src/pages/teacher/affairs/mental/index.vue')
  const talk = read('miniapp/src/pages/teacher/affairs/talk/index.vue')
  assert.match(mental, /\.then\(\(d\) => \{[\s\S]*this\.actionContent = ''/)
  assert.match(mental, /\.catch\(\(e\) => this\.showError\(e, '操作失败'\)\)/)
  assert.match(talk, /\.then\(\(d\) => \{[\s\S]*this\.followContent = ''/)
  assert.match(talk, /\.catch\(\(e\) => this\.showError\(e, '处理失败'\)\)/)
})

test('student portal request serializes pagination query parameters', () => {
  const request = read('student-portal/src/services/request.js')
  const affairs = read('student-portal/src/services/affairsFourEndApi.js')
  assert.match(request, /function withQuery\(path, params\)/)
  assert.match(request, /params \|\| query/)
  assert.match(affairs, /myCreditAppeals: \(page = 1, pageSize = 100\)/)
})

test('student clients preserve the real error after refreshing an expired token', () => {
  const mini = read('miniapp/src/services/request.js')
  const portal = read('student-portal/src/services/request.js')
  assert.match(mini, /\.then\(resolve\)\s*\.catch\(reject\)/)
  assert.doesNotMatch(mini, /\.catch\(\(\) => reject\(\{ code: body\.code/)
  assert.match(portal, /let refreshing = null/)
  assert.match(portal, /async function refreshOnce\(\)/)
  assert.match(portal, /return request\(path, \{ method, body, auth, params, query, _retried: true \}\)/)
  assert.match(portal, /return uploadFile\(path, file, \{ auth, _retried: true \}\)/)
  assert.match(portal, /return downloadFile\(path, fallbackName, true\)/)
})

test('both student clients reject empty or non-positive credit claims', () => {
  const mini = read('miniapp/src/services/affairsAppealApi.js')
  const portal = read('student-portal/src/services/affairsFourEndApi.js')
  for (const source of [mini, portal]) {
    assert.match(source, /Number\.isFinite\(value\)/)
    assert.match(source, /value <= 0/)
    assert.match(source, /最多保留2位小数/)
  }
})
