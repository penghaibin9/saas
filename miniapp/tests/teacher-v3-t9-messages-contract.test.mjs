import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/pages/teacher/messages/index.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/services/teacherMessagesV3Api.js', import.meta.url), 'utf8')
const search = readFileSync(new URL('../src/services/searchProviders.js', import.meta.url), 'utf8')
const detail = readFileSync(new URL('../src/pages/common/message-detail/index.vue', import.meta.url), 'utf8')

assert.match(page, /createNetworkPager/)
assert.match(page, /maxItems:\s*100/)
assert.match(page, /getTeacherMessageBadges/)
assert.doesNotMatch(page, /listPaging|pagedSlice|teacherApi\.getMessages/)

assert.match(api, /teacher\/messages-page/)
assert.match(api, /teacher\/messages-badges/)
assert.match(api, /pageSize\s*=\s*20/)
assert.match(search, /side:\s*'teacher'[\s\S]*serverSide:\s*true/)
assert.match(search, /getTeacherMessagesPage\(\{\s*tab:\s*'all'/)
assert.doesNotMatch(search, /getSearchPool|仅搜索本机/)

assert.match(detail, /getTeacherMessageDetail/)
assert.match(detail, /side === 'teacher'/)
assert.match(detail, /ackTeacherMessageReceipt/)

console.log('Teacher Miniapp V3 T9 message contract: OK')
