const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..');
const pc = fs.readFileSync(path.join(root, 'web', '管理平台.html'), 'utf8');
const mobile = fs.readFileSync(path.join(root, 'web', 'm', 'index.html'), 'utf8');

test('PC毕业设计按五个业务阶段形成三级导航', () => {
  for (const phase of ['毕业设计 · 任务启动','毕业设计 · 选题任务书','毕业设计 · 过程指导','毕业设计 · 成果检查','毕业设计 · 答辩成绩']) {
    assert.match(pc, new RegExp(phase.replace('·','\\·')));
  }
});

test('核心页面提供前置条件、下一步和异常处理', () => {
  assert.match(pc, /const FLOW_CONTEXT=/);
  assert.match(pc, /完成后的下一步/);
  assert.match(pc, /异常处理/);
  for (const page of ['internplan','applications','procmon','risk','filings','gdtopics','taskbooks','guidance','achievements','defense','gdgrades']) {
    assert.match(pc, new RegExp(page + ':'));
  }
});

test('移动H5强调常用办理而非复制PC全部管理能力', () => {
  assert.match(mobile, /常用办理/);
  assert.doesNotMatch(mobile, />全部功能</);
});

test('业务导航持续隐藏省平台', () => {
  assert.doesNotMatch(pc + mobile, /page:'province'|renderProvince|省平台|省厅/);
});
