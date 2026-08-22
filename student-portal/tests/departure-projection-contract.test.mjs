import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const view = readFileSync(new URL('../src/views/departure/DepartureView.vue', import.meta.url), 'utf8')
const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const orientation = readFileSync(new URL('../src/views/orientation/OrientationView.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/services/portalApi.js', import.meta.url), 'utf8')

test('SP-D04 离校有独立正式路由，且不使用仓库里已被占用的 clearance 语义', () => {
  assert.match(router, /path: 'departure'/)
  assert.match(api, /departureMy/)
  // 仓库里 clearance 是"清考"，离校不能复用这个词
  assert.doesNotMatch(router, /path: 'clearance'/)
})

test('SP-D04 迎新页保留兼容入口并引导到正式离校页，不删除历史路径', () => {
  assert.match(orientation, /key: 'departure'/)
  assert.match(orientation, /\$router\.push\('\/departure'\)/)
  // 旧的"待学校启用后开放"静态空态必须消失——它并不是真实业务状态
  assert.doesNotMatch(orientation, /离校清单待学校启用后开放/)
})

test('SP-D03 六种结果各自独立表述，UNKNOWN 与 ERROR 不得混为一谈', () => {
  for (const code of ['PASS', 'FAIL', 'NOT_REQUIRED', 'NOT_STARTED', 'MANUAL_PENDING', 'UNKNOWN', 'ERROR']) {
    assert.match(view, new RegExp(`${code}:`), `缺少结果文案：${code}`)
  }
  // "查得到但判不了"与"源故障"必须是两句不同的话
  assert.match(view, /UNKNOWN: '信息不完整'/)
  assert.match(view, /ERROR: '暂时无法读取'/)
  // 加载失败要显式报错，不能落到 empty 态
  assert.match(view, /v-else-if="error"/)
})

test('SP-D01 每项展示来源与证据版本，无真实落点时不给按钮', () => {
  assert.match(view, /item\.source/)
  assert.match(view, /item\.evidenceVersion/)
  assert.match(view, /v-if="item\.action"/)
})

test('离校页不自建业务判定，只渲染服务端结论', () => {
  // 页面不得出现"如果就业有记录就算办结"这类本地推断
  assert.doesNotMatch(view, /destinationType/)
  assert.doesNotMatch(view, /verifyStatus/)
  assert.match(view, /data\.readiness/)
})
