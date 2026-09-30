import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/views/admin/orientation/OrientationMaterialReviewView.vue', import.meta.url), 'utf8')

test('迎新材料审核使用安全文件中心预览真实提交版本', () => {
  assert.match(source, /FilePreviewer/)
  assert.match(source, /v-if="viewTarget\.fileId"/)
  assert.doesNotMatch(source, /原文件在线预览尚未配置/)
  assert.match(source, /第 \{\{ viewTarget\.submissionNo \}\} 版/)
})
