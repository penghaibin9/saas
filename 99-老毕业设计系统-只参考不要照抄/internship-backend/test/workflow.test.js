/**
 * 配置化流程引擎 纯逻辑单元测试（状态机核心，不依赖数据库）
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const wf = require('../models/workflowModel');

const T = [
  { from_state: 'draft', to_state: 'submitted', action: 'submit', name: '提交', roles: '4' },
  { from_state: 'submitted', to_state: 'approved', action: 'approve', name: '通过', roles: '3,1' },
  { from_state: 'submitted', to_state: 'rejected', action: 'reject', name: '驳回', roles: '3' },
];

test('resolveTransition：按状态+动作匹配流转', () => {
  assert.equal(wf.resolveTransition(T, 'draft', 'submit').to_state, 'submitted');
  assert.equal(wf.resolveTransition(T, 'submitted', 'approve').to_state, 'approved');
  assert.equal(wf.resolveTransition(T, 'draft', 'approve'), null); // 非法
  assert.equal(wf.resolveTransition(T, 'approved', 'submit'), null);
});

test('canPerform：按角色判定动作权限', () => {
  const submit = wf.resolveTransition(T, 'draft', 'submit');
  assert.equal(wf.canPerform(submit, 4), true);   // 学生可提交
  assert.equal(wf.canPerform(submit, 3), false);  // 教师不能提交
  const approve = wf.resolveTransition(T, 'submitted', 'approve');
  assert.equal(wf.canPerform(approve, 3), true);  // 教师可通过
  assert.equal(wf.canPerform(approve, 1), true);  // 院校管理员可通过
  assert.equal(wf.canPerform(approve, 4), false); // 学生不能通过
});

test('availableActions：某状态下该角色可执行的动作', () => {
  const teacherAtSubmitted = wf.availableActions(T, 'submitted', 3);
  const actions = teacherAtSubmitted.map(a => a.action).sort();
  assert.deepEqual(actions, ['approve', 'reject']); // 教师在待审：通过/驳回
  const studentAtSubmitted = wf.availableActions(T, 'submitted', 4);
  assert.equal(studentAtSubmitted.length, 0); // 学生在待审：无动作
  const studentAtDraft = wf.availableActions(T, 'draft', 4);
  assert.deepEqual(studentAtDraft.map(a => a.action), ['submit']);
});

test('默认流程齐备（实习申请/报告/请假，均有起始与终止）', () => {
  for (const biz of ['intern_apply', 'report', 'leave']) {
    const d = wf.DEFAULTS[biz];
    assert.ok(d && d.states.length && d.transitions.length, biz);
    assert.ok(d.states.some(s => s.is_start), biz + ' 缺起始');
    assert.ok(d.states.some(s => s.is_end), biz + ' 缺终止');
  }
});
