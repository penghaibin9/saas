/**
 * 注册防提权回归测试（不依赖数据库）
 * 目标：公开注册必须固定为学生(role=4)，即使请求体伪造 role=1(管理员) 也不得生效。
 * 做法：桩替换 userModel 的 DB 方法，仅验证控制器写入的角色与返回值。
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
process.env.JWT_SECRET = 'unit-test-secret-key-at-least-32-chars-long';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { userModel } = require('../models');
const userController = require('../controllers/userController');

function mockRes() {
  return {
    statusCode: 200,
    body: null,
    status(code) { this.statusCode = code; return this; },
    json(obj) { this.body = obj; return this; },
  };
}

test('register：伪造 role=1 仍被强制为学生 role=4', async () => {
  let created = null;
  const origFindByUsername = userModel.findByUsername;
  const origCreate = userModel.create;
  const origFindById = userModel.findById;
  try {
    userModel.findByUsername = async () => null;          // 用户名未占用
    userModel.create = async (u) => { created = u; return 99; };
    userModel.findById = async (id) => ({
      id, username: 'hacker', real_name: '攻击者', role: 4, status: 1,
    });

    const req = { body: { username: 'hacker', password: 'abc123', real_name: '攻击者', role: 1, status: 1 } };
    const res = mockRes();
    await userController.register(req, res);

    assert.equal(created.role, 4, '写入数据库的角色必须是学生(4)');
    assert.equal(res.statusCode, 201);
    assert.equal(res.body.data.role, 4, '返回给前端的角色必须是学生(4)');
  } finally {
    userModel.findByUsername = origFindByUsername;
    userModel.create = origCreate;
    userModel.findById = origFindById;
  }
});

test('register：缺少必填字段返回 400', async () => {
  const req = { body: { username: 'x' } };
  const res = mockRes();
  await userController.register(req, res);
  assert.equal(res.statusCode, 400);
});

test('register：用户名已存在返回 409', async () => {
  const origFindByUsername = userModel.findByUsername;
  try {
    userModel.findByUsername = async () => ({ id: 1, username: 'taken' });
    const req = { body: { username: 'taken', password: 'abc123', real_name: '某人' } };
    const res = mockRes();
    await userController.register(req, res);
    assert.equal(res.statusCode, 409);
  } finally {
    userModel.findByUsername = origFindByUsername;
  }
});
