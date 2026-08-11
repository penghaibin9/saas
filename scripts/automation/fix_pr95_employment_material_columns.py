from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
view = ROOT / 'student-portal/src/views/employment/EmploymentView.vue'
test = ROOT / 'student-portal/tests/ui-presentation-v3-data-contract.test.mjs'

text = view.read_text(encoding='utf-8')
old = """const MATERIAL_COLS = [
  { key: 'materialType', label: '材料类型' }, { key: 'fileName', label: '文件名称' },
  { key: 'uploadedAt', label: '提交时间' }, { key: 'status', label: '审核状态' },
  { key: 'reviewNote', label: '审核意见' }
]
"""
new = """const MATERIAL_COLS = [
  { key: 'type', label: '材料类型' },
  { key: 'fileName', label: '文件名称' },
  { key: 'status', label: '审核状态' }
]
"""
if text.count(old) != 1:
    raise RuntimeError('EmploymentView MATERIAL_COLS contract changed unexpectedly')
view.write_text(text.replace(old, new, 1), encoding='utf-8')

t = test.read_text(encoding='utf-8')
addition = """

test('就业签约材料表绑定真实 DTO，不制造不存在字段', () => {
  const block = employment.match(/const MATERIAL_COLS = \\[[\\s\\S]*?\\n\\]/)?.[0] || ''
  assert.match(block, /key: 'type'/)
  assert.match(block, /key: 'fileName'/)
  assert.match(block, /key: 'status'/)
  assert.doesNotMatch(block, /materialType|uploadedAt|reviewNote/)
})
"""
if "就业签约材料表绑定真实 DTO" not in t:
    test.write_text(t.rstrip() + addition, encoding='utf-8')
