const test = require('node:test');
const assert = require('node:assert/strict');
const express = require('express');
const { once } = require('node:events');
const { createToken } = require('../middlewares/auth');

async function withServer(router, prefix, run) {
  const app = express();
  app.use(prefix, router);
  app.use((err, req, res, next) => {
    res.status(500).json({ success: false, message: err.message });
  });
  const server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const { port } = server.address();
  try {
    await run(`http://127.0.0.1:${port}${prefix}`);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test('公开演示路由返回固定字段白名单且无需认证', async () => {
  const router = require('../routes/publicRoutes');
  await withServer(router, '/public', async (base) => {
    const response = await fetch(`${base}/product-overview-demo`);
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.success, true);
    assert.deepEqual(
      Object.keys(body.data).sort(),
      ['collegeRanking', 'demoFlow', 'generatedAt', 'kpis', 'source'].sort()
    );
    assert.equal(body.data.source, 'mock-public-demo');

    const serialized = JSON.stringify(body.data).toLowerCase();
    for (const forbidden of [
      'diagnostics', 'fallbackused', 'phone', 'mobile', 'id_card', 'address',
      'real_name', 'student_name', 'username', 'eeid', 'sql', 'stack', 'database'
    ]) {
      assert.equal(serialized.includes(forbidden), false, `公开响应不得包含 ${forbidden}`);
    }
  });
});

test('真实产品概览执行 401/403/200 角色边界', async () => {
  const model = require('../models/schoolReadinessModel');
  const originalOverview = model.overview;
  let overviewCalls = 0;
  model.overview = async () => {
    overviewCalls += 1;
    return { source: 'test', kpis: {}, collegeRanking: [] };
  };

  delete require.cache[require.resolve('../routes/statsRoutes')];
  const router = require('../routes/statsRoutes');

  const tokenFor = (role) => createToken({
    id: role,
    username: `role${role}`,
    role,
    real_name: `角色${role}`,
    college_id: 1,
    enterprise_id: null,
    must_change_password: 0
  });

  try {
    await withServer(router, '/stats', async (base) => {
      const anonymous = await fetch(`${base}/product-overview?demo=1`);
      assert.equal(anonymous.status, 401);

      for (const role of [3, 4, 5]) {
        const denied = await fetch(`${base}/product-overview?demo=1`, {
          headers: { Authorization: `Bearer ${tokenFor(role)}` }
        });
        assert.equal(denied.status, 403, `角色 ${role} 不应读取校级概览`);
      }

      for (const role of [1, 2]) {
        const allowed = await fetch(`${base}/product-overview?demo=1`, {
          headers: { Authorization: `Bearer ${tokenFor(role)}` }
        });
        assert.equal(allowed.status, 200, `角色 ${role} 应可读取校级概览`);
        const body = await allowed.json();
        assert.equal(body.success, true);
      }
      assert.equal(overviewCalls, 2, '只有获授权的管理员请求可以进入统计模型');
    });
  } finally {
    model.overview = originalOverview;
    delete require.cache[require.resolve('../routes/statsRoutes')];
  }
});
