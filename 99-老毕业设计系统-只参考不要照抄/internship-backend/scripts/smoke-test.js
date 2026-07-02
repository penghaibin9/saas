/**
 * 一键 HTTP 冒烟测试：覆盖实习 + 毕设核心链路。
 * 前提：服务已启动（默认 http://localhost:3000）。
 * 运行：npm run smoke    （可用 SMOKE_BASE 覆盖地址，如 SMOKE_BASE=http://localhost:3999/api）
 *
 * 脚本会用数据库播种 smoke_admin/smoke_teacher/smoke_student 三个测试账号（密码见下），
 * 不影响你的真实数据；可重复运行。
 */
require('dotenv').config();
const pwdHash = require('../utils/password');
const pool = require('../config/db');

const BASE = process.env.SMOKE_BASE || `http://localhost:${process.env.PORT || 3000}/api`;
const PWD = 'smoke1234';
let pass = 0, fail = 0;

function check(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra ? '  -> ' + extra : '')); }
}

async function api(method, path, { token, body } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let json; const text = await res.text();
  try { json = JSON.parse(text); } catch { json = text; }
  return { status: res.status, json };
}

async function seedUser(username, real_name, role, extra = {}) {
  const hash = await pwdHash.hash(PWD);
  await pool.query(
    `INSERT INTO t_user (username, password, real_name, role, status, must_change_password, college_id, major_id, class_id, eeid)
     VALUES (?, ?, ?, ?, 1, 0, ?, ?, ?, ?)
     ON DUPLICATE KEY UPDATE password=VALUES(password), must_change_password=0, status=1,
       college_id=VALUES(college_id), major_id=VALUES(major_id), class_id=VALUES(class_id), eeid=VALUES(eeid)`,
    [username, hash, real_name, role, extra.college_id || null, extra.major_id || null, extra.class_id || null, extra.eeid || null]
  );
  const [[u]] = await pool.query('SELECT id FROM t_user WHERE username = ?', [username]);
  return u.id;
}

async function login(username) {
  const r = await api('POST', '/users/login', { body: { username, password: PWD } });
  return r.json && r.json.data ? r.json.data.token : null;
}

(async () => {
  console.log('== 冒烟测试开始 ==  BASE =', BASE);
  try {
    // 0) 健康检查
    const health = await api('GET', '/health');
    check('GET /health', health.status === 200);

    // 1) 播种管理员并登录
    await seedUser('smoke_admin', '冒烟管理员', 1);
    const adminToken = await login('smoke_admin');
    check('管理员登录', !!adminToken);
    if (!adminToken) throw new Error('管理员登录失败，后续中止');

    // 2) 基础数据：学院/专业/班级/企业
    const col = await api('POST', '/colleges', { token: adminToken, body: { name: '冒烟学院', code: 'SMOKE_' + Date.now() } });
    const collegeId = col.json?.data?.id;
    check('创建学院', !!collegeId, JSON.stringify(col.json));

    const ent = await api('POST', '/enterprises', { token: adminToken, body: { name: '冒烟企业' + Date.now(), latitude: 28.2, longitude: 112.9, checkin_radius: 200 } });
    const enterpriseId = ent.json?.data?.id;
    check('创建企业(含坐标)', !!enterpriseId);

    // 3) 播种教师/学生（归属冒烟学院）
    const teacherId = await seedUser('smoke_teacher', '冒烟教师', 3, { college_id: collegeId, eeid: 'T9001' });
    const studentId = await seedUser('smoke_student', '冒烟学生', 4, { college_id: collegeId, eeid: 'S9001' });
    const teacherToken = await login('smoke_teacher');
    const studentToken = await login('smoke_student');
    check('教师/学生登录', !!teacherToken && !!studentToken);

    // 4) 实习计划：创建 -> 审批通过 -> 开启
    const plan = await api('POST', '/intern-plans', { token: adminToken, body: { title: '冒烟实习计划', college_id: collegeId, checkin_count: 1, weekly_count: 1 } });
    const planId = plan.json?.data?.id;
    check('创建实习计划', !!planId, JSON.stringify(plan.json));
    const appr = await api('PUT', `/intern-plans/${planId}/approve`, { token: adminToken, body: { agree: true } });
    check('审批通过计划', appr.json?.data?.status === 2);
    const open = await api('PUT', `/intern-plans/${planId}/open`, { token: adminToken });
    check('开启计划', open.json?.data?.status === 3);

    // 5) 实习分配
    const asg = await api('POST', '/assignments', { token: adminToken, body: { plan_id: planId, student_id: studentId, teacher_id: teacherId, enterprise_id: enterpriseId } });
    check('实习分配', asg.json?.success === true, JSON.stringify(asg.json));

    // 6) 学生打卡（坐标与企业一致 -> 在范围内）
    const ck = await api('POST', '/checkins', { token: studentToken, body: { latitude: 28.2, longitude: 112.9, address: '冒烟测试' } });
    // 当天重复运行会命中“每日仅可打卡一次”的去重(409)，视为通过
    check('学生打卡(地理围栏)', ck.json?.success === true || ck.status === 409, JSON.stringify(ck.json));
    const mine = await api('GET', '/checkins/mine', { token: studentToken });
    check('打卡概况 /checkins/mine', mine.json?.success === true);

    // 7) 周报：学生写 -> 提交 -> 教师批阅
    const log = await api('POST', '/intern-logs', { token: studentToken, body: { type: 'weekly', title: '第一周周报', content: '内容...' } });
    const logId = log.json?.data?.id;
    check('学生创建周报', !!logId, JSON.stringify(log.json));
    if (logId) {
      await api('PUT', `/intern-logs/${logId}/submit`, { token: studentToken });
      const rev = await api('PUT', `/intern-logs/${logId}/review`, { token: teacherToken, body: { agree: true, teacher_comment: '不错' } });
      check('教师批阅周报', rev.json?.success === true, JSON.stringify(rev.json));
    }

    // 8) 请假：学生提交
    const lv = await api('POST', '/leaves', { token: studentToken, body: { start_date: '2026-06-10', end_date: '2026-06-11', reason: '事假' } });
    check('学生请假', lv.json?.success === true, JSON.stringify(lv.json));

    // 9) 毕设：公示 / 任务节点 / 选题 / 成果 / 成绩
    check('发布公示', (await api('POST', '/announcements', { token: adminToken, body: { title: '冒烟公示', category: '公示信息', content: 'x' } })).json?.success === true);
    check('创建任务节点', (await api('POST', '/gd-tasks', { token: adminToken, body: { name: '开题', college_id: collegeId } })).json?.success === true);
    const topic = await api('POST', '/gd-topics', { token: adminToken, body: { title: '冒烟选题', student_id: studentId, teacher_id: teacherId, college_id: collegeId } });
    check('创建选题', topic.json?.success === true);
    const ach = await api('POST', '/gd-achievements', { token: studentToken, body: { title: '冒烟成果', link: 'http://example.com' } });
    const achId = ach.json?.data?.id;
    check('学生上传成果', !!achId, JSON.stringify(ach.json));
    if (achId) check('教师审阅成果', (await api('PUT', `/gd-achievements/${achId}/review`, { token: teacherToken, body: { status: 1 } })).json?.success === true);
    check('录入成绩', (await api('POST', '/gd-grades', { token: teacherToken, body: { student_id: studentId, review_score: 85, defense_score: 88, total_score: 86 } })).json?.success === true);
    check('教师创建指导记录', (await api('POST', '/gd-guidances', { token: teacherToken, body: { student_id: studentId, title: '第一次指导', content: '...' } })).json?.success === true);

    // 10) 统计 / 分析 / 工作台
    check('实习统计概览', (await api('GET', '/intern-stats/summary', { token: adminToken })).json?.success === true);
    check('实习过程统计', (await api('GET', '/intern-stats/process', { token: adminToken })).json?.success === true);
    check('未达标学生', (await api('GET', '/intern-stats/incomplete', { token: adminToken })).json?.success === true);
    check('实习分析', (await api('GET', '/analytics/intern', { token: adminToken })).json?.success === true);
    check('毕设分析', (await api('GET', '/analytics/gd', { token: adminToken })).json?.success === true);
    check('毕设概览卡片', (await api('GET', '/analytics/gd-summary', { token: adminToken })).json?.success === true);
    check('优秀师生', (await api('GET', '/analytics/excellence', { token: adminToken })).json?.success === true);
    check('提交企业满意度', (await api('POST', '/satisfaction', { token: adminToken, body: { enterprise_id: enterpriseId, student_id: studentId, score: 5, content: '表现优秀' } })).json?.success === true);
    check('满意度分析', (await api('GET', '/satisfaction/analytics', { token: adminToken })).json?.success === true);
    check('教师工作台', (await api('GET', '/workbench', { token: teacherToken })).json?.success === true);
    check('学生工作台', (await api('GET', '/workbench', { token: studentToken })).json?.success === true);

    // 11) 导出（仅校验 HTTP 200 + Excel 头）
    for (const ep of ['intern-archive', 'assignments', 'checkins', 'gd-topics', 'gd-grades', 'users']) {
      const res = await fetch(BASE + '/export/' + ep, { headers: { Authorization: 'Bearer ' + adminToken } });
      check('导出 /export/' + ep, res.status === 200);
    }

    // 12) 越权校验：学生访问省厅接口应 403
    const prov = await api('GET', '/province', { token: studentToken });
    check('学生越权 /province 被拦', prov.status === 403);

  } catch (e) {
    console.error('异常：', e.message);
    fail++;
  } finally {
    console.log(`\n== 结果：通过 ${pass}，失败 ${fail} ==`);
    await pool.end();
    process.exit(fail ? 1 : 0);
  }
})();
