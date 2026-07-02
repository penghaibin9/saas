process.env.NODE_ENV = 'test';
process.env.JWT_SECRET = 'unit-test-secret-key-at-least-32-chars-long';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { systemConfigModel, userModel } = require('../models');
const integrationController = require('../controllers/integrationController');

function mockReq({ body = {}, query = {} } = {}) {
  return {
    body,
    query,
    protocol: 'https',
    get(name) {
      const headers = { host: 'school.example.edu', 'x-forwarded-proto': 'https' };
      return headers[String(name).toLowerCase()];
    }
  };
}

function mockRes() {
  return {
    statusCode: 200,
    body: null,
    location: null,
    status(code) { this.statusCode = code; return this; },
    json(payload) { this.body = payload; return this; },
    redirect(location) { this.statusCode = 302; this.location = location; return this; }
  };
}

function casConfig(overrides = {}) {
  return {
    cas_enabled: '1',
    cas_login_url: 'https://cas.example.edu/login',
    cas_validate_url: 'https://cas.example.edu/serviceValidate',
    app_public_url: 'https://school.example.edu',
    ...overrides
  };
}

test('CAS 登录缺少 ticket 时直接拒绝，不进入本地用户查询', async () => {
  const originalGetAll = systemConfigModel.getAll;
  const originalFind = userModel.findByCasIdentity;
  let lookedUp = false;
  try {
    systemConfigModel.getAll = async () => casConfig();
    userModel.findByCasIdentity = async () => { lookedUp = true; return null; };

    const res = mockRes();
    await integrationController.casLogin(mockReq(), res);

    assert.equal(res.statusCode, 400);
    assert.equal(res.body.data.code, 'CAS_TICKET_MISSING');
    assert.equal(lookedUp, false, '未验证票据时不得查询并签发本地身份');
  } finally {
    systemConfigModel.getAll = originalGetAll;
    userModel.findByCasIdentity = originalFind;
  }
});

test('CAS 已启用但缺少 validateUrl 时返回明确 503，绝不回退本地身份', async () => {
  const originalGetAll = systemConfigModel.getAll;
  const originalFind = userModel.findByCasIdentity;
  let lookedUp = false;
  try {
    systemConfigModel.getAll = async () => casConfig({ cas_validate_url: '', cas_server_url: '' });
    userModel.findByCasIdentity = async () => { lookedUp = true; return null; };

    const res = mockRes();
    await integrationController.casLogin(mockReq({ body: { ticket: 'ST-forged', username: 'admin' } }), res);

    assert.equal(res.statusCode, 503);
    assert.equal(res.body.data.code, 'CAS_VALIDATE_URL_MISSING');
    assert.equal(lookedUp, false);
  } finally {
    systemConfigModel.getAll = originalGetAll;
    userModel.findByCasIdentity = originalFind;
  }
});

test('CAS 无效 ticket 即使附带伪造 username/service 也返回 401', async () => {
  const originalGetAll = systemConfigModel.getAll;
  const originalFind = userModel.findByCasIdentity;
  const originalFetch = global.fetch;
  let lookedUp = false;
  let validationUrl = '';
  try {
    systemConfigModel.getAll = async () => casConfig();
    userModel.findByCasIdentity = async () => { lookedUp = true; return null; };
    global.fetch = async (url) => {
      validationUrl = url;
      return {
        ok: true,
        status: 200,
        text: async () => '<cas:authenticationFailure code="INVALID_TICKET">Ticket invalid<cas:user>admin</cas:user></cas:authenticationFailure>'
      };
    };

    const res = mockRes();
    await integrationController.casLogin(mockReq({
      body: { ticket: 'ST-invalid', username: 'admin', service: 'https://evil.example/callback' }
    }), res);

    assert.equal(res.statusCode, 401);
    assert.equal(res.body.data.code, 'CAS_TICKET_INVALID');
    assert.equal(lookedUp, false);
    assert.equal(
      new URL(validationUrl).searchParams.get('service'),
      'https://school.example.edu/api/integration/cas/callback',
      'CAS service 必须由服务端固定，不能信任客户端传值'
    );
  } finally {
    systemConfigModel.getAll = originalGetAll;
    userModel.findByCasIdentity = originalFind;
    global.fetch = originalFetch;
  }
});

test('CAS 仅在明确 authenticationSuccess 后按票据身份登录', async () => {
  const originalGetAll = systemConfigModel.getAll;
  const originalFind = userModel.findByCasIdentity;
  const originalFetch = global.fetch;
  try {
    systemConfigModel.getAll = async () => casConfig();
    userModel.findByCasIdentity = async (identity) => ({
      id: 7,
      username: identity,
      real_name: '测试教师',
      role: 3,
      college_id: 2,
      status: 1
    });
    global.fetch = async () => ({
      ok: true,
      status: 200,
      text: async () => '<cas:serviceResponse><cas:authenticationSuccess><cas:user>teacher01</cas:user></cas:authenticationSuccess></cas:serviceResponse>'
    });

    const res = mockRes();
    await integrationController.casLogin(mockReq({ body: { ticket: 'ST-valid' } }), res);

    assert.equal(res.statusCode, 200);
    assert.equal(res.body.success, true);
    assert.equal(res.body.data.casUser, 'teacher01');
    assert.ok(res.body.data.token);
  } finally {
    systemConfigModel.getAll = originalGetAll;
    userModel.findByCasIdentity = originalFind;
    global.fetch = originalFetch;
  }
});

test('CAS redirect 拒绝未列入白名单的外域 returnTo', async () => {
  const originalGetAll = systemConfigModel.getAll;
  const originalAllowlist = process.env.CAS_RETURN_TO_ALLOWLIST;
  const originalOrigins = process.env.CAS_RETURN_TO_ORIGINS;
  try {
    delete process.env.CAS_RETURN_TO_ALLOWLIST;
    delete process.env.CAS_RETURN_TO_ORIGINS;
    systemConfigModel.getAll = async () => casConfig();

    const res = mockRes();
    await integrationController.casRedirect(mockReq({ query: { returnTo: 'https://evil.example/steal' } }), res);

    assert.equal(res.statusCode, 400);
    assert.equal(res.body.data.code, 'CAS_RETURN_TO_NOT_ALLOWED');
    assert.equal(res.location, null);
  } finally {
    systemConfigModel.getAll = originalGetAll;
    if (originalAllowlist === undefined) delete process.env.CAS_RETURN_TO_ALLOWLIST;
    else process.env.CAS_RETURN_TO_ALLOWLIST = originalAllowlist;
    if (originalOrigins === undefined) delete process.env.CAS_RETURN_TO_ORIGINS;
    else process.env.CAS_RETURN_TO_ORIGINS = originalOrigins;
  }
});

test('CAS redirect 接受本站根相对 returnTo 并原样绑定到 service', async () => {
  const originalGetAll = systemConfigModel.getAll;
  try {
    systemConfigModel.getAll = async () => casConfig();

    const res = mockRes();
    await integrationController.casRedirect(mockReq({ query: { returnTo: '/admin?tab=cas' } }), res);

    assert.equal(res.statusCode, 302);
    const loginUrl = new URL(res.location);
    const service = new URL(loginUrl.searchParams.get('service'));
    assert.equal(service.origin, 'https://school.example.edu');
    assert.equal(service.pathname, '/api/integration/cas/callback');
    assert.equal(service.searchParams.get('returnTo'), '/admin?tab=cas');
  } finally {
    systemConfigModel.getAll = originalGetAll;
  }
});

test('CAS callback 内部异常不会把数据库细节带到跳转地址', async () => {
  const originalGetAll = systemConfigModel.getAll;
  const originalFind = userModel.findByCasIdentity;
  const originalFetch = global.fetch;
  try {
    systemConfigModel.getAll = async () => casConfig();
    userModel.findByCasIdentity = async () => {
      throw new Error('connect ECONNREFUSED mysql.internal:3306 secret_schema');
    };
    global.fetch = async () => ({
      ok: true,
      status: 200,
      text: async () => '<cas:serviceResponse><cas:authenticationSuccess><cas:user>teacher01</cas:user></cas:authenticationSuccess></cas:serviceResponse>'
    });

    const res = mockRes();
    await integrationController.casCallback(mockReq({ query: { ticket: 'ST-valid', returnTo: '/admin' } }), res);

    assert.equal(res.statusCode, 302);
    assert.match(decodeURIComponent(res.location), /统一认证暂不可用/);
    assert.doesNotMatch(res.location, /mysql|secret_schema|3306/i);
  } finally {
    systemConfigModel.getAll = originalGetAll;
    userModel.findByCasIdentity = originalFind;
    global.fetch = originalFetch;
  }
});
