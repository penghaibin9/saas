import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8')

test('Teacher Mini fetches bounded server pages instead of sorting a whole batch locally', () => {
  const page = read('src/pages/teacher/internship-review/index.vue')
  const adapter = read('src/services/teacherSequentialV3Api.js')
  assert.match(adapter, /weeklyPage = 1, exceptionPage = 1, pageSize = 20/)
  assert.match(adapter, /weeklyPage=\$\{weeklyPage\}&exceptionPage=\$\{exceptionPage\}&pageSize=\$\{pageSize\}/)
  assert.match(page, /getWeeklyReports\(\{ weeklyPage: 1, exceptionPage: 1, pageSize: 20 \}\)/)
  assert.match(page, /loadMoreQueue\('weekly'\)/)
  assert.match(page, /loadMoreQueue\('abnormal'\)/)
  assert.match(page, /pagination\.weeklyHasMore/)
  assert.match(page, /pagination\.exceptionHasMore/)
  assert.doesNotMatch(page, /\.sort\(/)
})

test('Teacher Mini totals distinguish server truth from the currently loaded page', () => {
  const page = read('src/pages/teacher/internship-review/index.vue')
  const adapter = read('src/services/teacherSequentialV3Api.js')
  assert.match(page, /pagination\?\.weeklyPendingTotal/)
  assert.match(page, /pagination\?\.weeklyOverdueTotal/)
  assert.match(page, /pagination\?\.exceptionTotal/)
  assert.match(page, /已加载风险提示/)
  assert.match(adapter, /pagination: d\.pagination/)
})

test('shared Mini segments and sequential mode use operable button semantics', () => {
  const segmented = read('src/components/MobileSegmented.vue')
  const page = read('src/pages/teacher/internship-review/index.vue')
  assert.match(segmented, /<button/)
  assert.match(segmented, /role="tab"/)
  assert.match(segmented, /:aria-selected="item\.key === modelValue"/)
  assert.match(page, /<button class="ir__queue-toggle" :aria-pressed="sequentialMode"/)
})
