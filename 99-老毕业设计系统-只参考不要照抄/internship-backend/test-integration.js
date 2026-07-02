/**
 * 集成测试脚本
 * 用法：npm test 或 node test-api.js
 * 注意：确保服务器已启动并且数据库已初始化
 */
require('dotenv').config();
const http = require('http');
const assert = require('assert');

const BASE_URL = `http://localhost:${process.env.PORT || 3000}`;
let testResults = { passed: 0, failed: 0 };
let adminToken = null;
let studentToken = null;
let collegeId = null;
let majorId = null;
let classId = null;
let studentId = null;
let teacherId = null;
let enterpriseId = null;
let positionId = null;
let applicationId = null;

// HTTP 请求辅助函数
function request(method, path, body = null, token = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE_URL);
    const options = {
      hostname: url.hostname,
      port: url.port || 3000,
      path: url.pathname + url.search,
      method,
      headers: {
        'Content-Type': 'application/json'
      }
    };

    if (token) {
      options.headers.Authorization = `Bearer ${token}`;
    }

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = data ? JSON.parse(data) : {};
          resolve({ status: res.statusCode, body: json });
        } catch (err) {
          reject(err);
        }
      });
    });

    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

// 测试用例
async function runTests() {
  console.log('🧪 开始集成测试...\n');

  try {
    // 1. 服务健康检查
    await test('服务健康检查', async () => {
      const { status } = await request('GET', '/api/health');
      assert.strictEqual(status, 200);
    });

    // 2. 用户注册
    await test('用户注册（学生）', async () => {
      const { status, body } = await request('POST', '/api/users/register', {
        username: 'student001',
        password: '123456',
        real_name: '张三',
        role: 4,
        eeid: '20240001'
      });
      assert.strictEqual(status, 201);
      assert.strictEqual(body.success, true);
      studentId = body.data?.id;
    });

    // 3. 用户登录
    await test('用户登录（学生）', async () => {
      const { status, body } = await request('POST', '/api/users/login', {
        username: 'student001',
        password: '123456'
      });
      assert.strictEqual(status, 200);
      assert.strictEqual(body.success, true);
      studentToken = body.data?.token;
    });

    // 4. 管理员登录
    await test('用户登录（管理员）', async () => {
      const { status, body } = await request('POST', '/api/users/login', {
        username: 'admin',
        password: '123456'
      });
      assert.strictEqual(status, 200);
      adminToken = body.data?.token;
    });

    // 5. 创建学院
    await test('创建学院', async () => {
      const { status, body } = await request('POST', '/api/colleges', {
        name: '信息工程学院',
        code: 'IE-TEST',
        description: '测试学院'
      }, adminToken);
      assert.strictEqual(status, 201);
      collegeId = body.data?.id;
    });

    // 6. 获取学院列表
    await test('获取学院列表', async () => {
      const { status, body } = await request('GET', '/api/colleges', null, adminToken);
      assert.strictEqual(status, 200);
      assert(Array.isArray(body.data) || body.data?.list);
    });

    // 7. 创建专业
    await test('创建专业', async () => {
      const { status, body } = await request('POST', '/api/majors', {
        college_id: collegeId,
        name: '计算机科学与技术',
        code: 'CS-TEST',
        description: '测试专业'
      }, adminToken);
      assert.strictEqual(status, 201);
      majorId = body.data?.id;
    });

    // 8. 创建班级
    await test('创建班级', async () => {
      const { status, body } = await request('POST', '/api/classes', {
        major_id: majorId,
        name: '计科2024-1班',
        grade: 2024
      }, adminToken);
      assert.strictEqual(status, 201);
      classId = body.data?.id;
    });

    // 9. 注册教师
    await test('注册教师用户', async () => {
      const { status, body } = await request('POST', '/api/users/register', {
        username: 'teacher001',
        password: '123456',
        real_name: '李老师',
        role: 3,
        college_id: collegeId
      }, null);
      assert.strictEqual(status, 201);
      teacherId = body.data?.id;
    });

    // 10. 创建企业
    await test('创建企业', async () => {
      const { status, body } = await request('POST', '/api/enterprises', {
        name: '北京科技有限公司',
        short_name: '北京科技',
        industry: '互联网',
        contact_name: '王经理',
        contact_phone: '13800000001'
      }, adminToken);
      assert.strictEqual(status, 201);
      enterpriseId = body.data?.id;
    });

    // 11. 创建岗位
    await test('创建岗位', async () => {
      const { status, body } = await request('POST', '/api/positions', {
        enterprise_id: enterpriseId,
        title: 'Java 开发工程师',
        description: '从事后端开发',
        requirement: '计算机专业',
        salary: '15K-25K',
        headcount: 5,
        college_id: collegeId
      }, adminToken);
      assert.strictEqual(status, 201);
      positionId = body.data?.id;
    });

    // 12. 获取岗位列表
    await test('获取岗位列表', async () => {
      const { status, body } = await request('GET', '/api/positions', null, studentToken);
      assert.strictEqual(status, 200);
      assert(body.data);
    });

    // 13. 提交申请
    await test('学生提交实习申请', async () => {
      const { status, body } = await request('POST', '/api/applications', {
        position_id: positionId,
        student_remark: '我对这个岗位很感兴趣'
      }, studentToken);
      assert.strictEqual(status, 201);
      applicationId = body.data?.id;
    });

    // 14. 获取个人申请列表
    await test('学生获取申请列表', async () => {
      const { status, body } = await request('GET', '/api/applications', null, studentToken);
      assert.strictEqual(status, 200);
      assert(body.data);
    });

    // 15. 分配教师
    await test('管理员分配指导教师', async () => {
      const { status, body } = await request(
        'PUT',
        `/api/applications/${applicationId}/assign-teacher`,
        { teacher_id: teacherId },
        adminToken
      );
      assert.strictEqual(status, 200);
      assert.strictEqual(body.data?.teacher_id, teacherId);
    });

    // 16. 获取用户信息
    await test('用户获取个人信息', async () => {
      const { status, body } = await request('GET', '/api/users/profile', null, studentToken);
      assert.strictEqual(status, 200);
      assert.strictEqual(body.data?.username, 'student001');
    });

    // 17. 修改用户信息
    await test('用户修改个人信息', async () => {
      const { status, body } = await request('PUT', '/api/users/profile', {
        real_name: '张三（更新）',
        phone: '13900000001'
      }, studentToken);
      assert.strictEqual(status, 200);
    });

    // 18. 导出用户列表
    await test('管理员导出用户列表', async () => {
      const { status } = await request('GET', '/api/export/users', null, adminToken);
      assert.strictEqual(status, 200);
    });

    // 19. 统计概览
    await test('获取统计概览', async () => {
      const { status, body } = await request('GET', '/api/stats/overview', null, adminToken);
      assert.strictEqual(status, 200);
      assert(body.data);
    });

    // 20. 通知列表
    await test('获取通知列表', async () => {
      const { status, body } = await request('GET', '/api/notifications', null, studentToken);
      assert.strictEqual(status, 200);
      assert(body.data);
    });

  } catch (err) {
    console.error('❌ 测试出错：', err.message);
    process.exit(1);
  }

  // 输出测试结果
  console.log('\n' + '='.repeat(60));
  console.log(`测试完成：${testResults.passed} 个通过，${testResults.failed} 个失败`);
  console.log('='.repeat(60));

  if (testResults.failed > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

// 测试装饰器
async function test(name, fn) {
  try {
    await fn();
    console.log(`✓ ${name}`);
    testResults.passed++;
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  ${err.message}`);
    testResults.failed++;
  }
}

// 启动测试
if (require.main === module) {
  console.log(`测试服务器地址: ${BASE_URL}\n`);
  runTests().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { request, test };
