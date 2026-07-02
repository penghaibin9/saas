/**
 * 端到端业务流程演示脚本
 * 真实调用运行中的后端 API（默认 http://localhost:3000/api），
 * 插入一条实习申请并贯穿整条主业务链路，逐环节打印结果。
 *
 * 运行：node scripts/e2e-flow.js
 * 依赖账号（来自 scripts/seed-demo.js）：
 *   admin/123456、demo_teacher/demo1234、demo_stu1/demo1234
 */
const BASE = process.env.API_BASE || 'http://localhost:3000/api';

let step = 0;
const results = [];
function log(name, ok, detail) {
  step++;
  const tag = ok ? '✅' : '❌';
  console.log(`${String(step).padStart(2, '0')}. ${tag} ${name}${detail ? ' — ' + detail : ''}`);
  results.push({ step, name, ok, detail });
}

async function api(token, path, method = 'GET', body) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await res.json(); } catch (_) {}
  return { status: res.status, json, ok: res.ok && json && json.success };
}
async function login(username, password) {
  const r = await api(null, '/users/login', 'POST', { username, password });
  if (!r.ok) throw new Error(`登录 ${username} 失败：${r.json && r.json.message}`);
  return { token: r.json.data.token, user: r.json.data.user };
}

const todayStr = () => new Date().toISOString().slice(0, 10);
const addDays = (n) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);

(async () => {
  console.log('==== 毕业设计/实习管理平台 · 端到端流程跑通 ====\n');

  // ---- 0. 登录三种角色 ----
  let admin, teacher, student;
  try {
    admin = await login('admin', '123456');
    teacher = await login('demo_teacher', 'demo1234');
    student = await login('demo_stu1', 'demo1234');
    log('登录 admin / 教师 / 学生', true, `studentId=${student.user.id}, teacherId=${teacher.user.id}`);
  } catch (e) { log('登录', false, e.message); return; }

  const sid = student.user.id, tid = teacher.user.id;

  // ---- 1. 管理员发布实习岗位（插入的“1条数据”起点）----
  let positionId, entId;
  {
    const ent = await api(admin.token, '/enterprises?page_size=1');
    entId = ent.json && ent.json.data && ent.json.data.list && ent.json.data.list[0] && ent.json.data.list[0].id;
    if (!entId) { log('获取企业', false, '无企业数据，先在后台创建企业'); return; }
    const title = '端到端演示岗位 ' + Date.now();
    const r = await api(admin.token, '/positions', 'POST', {
      enterprise_id: entId, title, description: '演示岗位', requirement: '无',
      salary: '3500/月', headcount: 5, location: '长沙'
    });
    positionId = r.ok && r.json.data.id;
    log('① 管理员发布岗位', r.ok, r.ok ? `positionId=${positionId}` : (r.json && r.json.message));
    if (!positionId) return;
  }

  // ---- 2. 学生提交实习申请 ----
  let appId;
  {
    const r = await api(student.token, '/applications', 'POST', { position_id: positionId, student_remark: '希望参与该岗位实习' });
    appId = r.ok && r.json.data.id;
    log('② 学生提交实习申请', r.ok, r.ok ? `applicationId=${appId} status=${r.json.data.status}(待审核)` : (r.json && r.json.message));
    if (!appId) return;
  }

  // ---- 3. 管理员为申请分配指导教师 ----
  {
    const r = await api(admin.token, `/applications/${appId}/assign-teacher`, 'PUT', { teacher_id: tid });
    log('③ 管理员分配指导教师', r.ok, r.ok ? `teacher_id=${tid}` : (r.json && r.json.message));
  }

  // ---- 4. 教师审核申请（同意）----
  {
    const r = await api(teacher.token, `/applications/${appId}/teacher-review`, 'PUT', { agree: true, opinion: '同意该生申请' });
    log('④ 教师审核申请（同意）', r.ok, r.ok ? `status=${r.json.data.status}(教师同意)` : (r.json && r.json.message));
  }

  // ---- 5. 院校管理员审核（通过）----
  {
    const r = await api(admin.token, `/applications/${appId}/admin-review`, 'PUT', { agree: true, opinion: '院校审核通过' });
    log('⑤ 院校审核（通过）', r.ok, r.ok ? `status=${r.json.data.status}(院校通过)` : (r.json && r.json.message));
  }

  // ---- 6. 管理员登记录用结果（录用）----
  {
    const r = await api(admin.token, `/applications/${appId}/recruit-result`, 'PUT', { recruited: true });
    log('⑥ 登记录用结果（已录用）', r.ok, r.ok ? `status=${r.json.data.status}(已录用)` : (r.json && r.json.message));
  }

  // ---- 7. 学生今日打卡 ----
  {
    const r = await api(student.token, '/checkins', 'POST', { latitude: 28.21, longitude: 112.94, address: '端到端演示打卡' });
    const already = r.json && /打过卡|已打卡|已经打/.test(r.json.message || '');
    log('⑦ 学生打卡签到', r.ok || already,
      r.ok ? '打卡成功' : (already ? '今日已打卡（防重复守卫生效）' : (r.json && r.json.message)));
  }

  // ---- 8. 学生写周报 + 提交，教师批阅 ----
  {
    const c = await api(student.token, '/intern-logs', 'POST', { type: 'weekly', title: '端到端演示周报', content: '本周完成了演示任务。' });
    if (c.ok) {
      const lid = c.json.data.id;
      await api(student.token, `/intern-logs/${lid}/submit`, 'PUT');
      const rv = await api(teacher.token, `/intern-logs/${lid}/review`, 'PUT', { agree: true });
      log('⑧ 周报：写→提交→教师批阅', rv.ok, rv.ok ? `logId=${lid} 已通过` : (rv.json && rv.json.message));
    } else log('⑧ 周报创建', false, c.json && c.json.message);
  }

  // ---- 9. 学生请假 + 提交，教师审批 ----
  {
    const c = await api(student.token, '/leaves', 'POST', { start_date: addDays(2), end_date: addDays(3), reason: '端到端演示请假' });
    if (c.ok) {
      const lid = c.json.data.id;
      await api(student.token, `/leaves/${lid}/submit`, 'PUT');
      const rv = await api(teacher.token, `/leaves/${lid}/review`, 'PUT', { agree: true });
      log('⑨ 请假：申请→提交→教师审批', rv.ok, rv.ok ? `leaveId=${lid} 已通过` : (rv.json && rv.json.message));
    } else log('⑨ 请假创建', false, c.json && c.json.message);
  }

  // ---- 10. 学生上传毕设成果，教师审阅 ----
  {
    const c = await api(student.token, '/gd-achievements', 'POST', { title: '端到端演示成果', link: 'http://example.com/work' });
    if (c.ok) {
      const aid = c.json.data.id;
      const rv = await api(teacher.token, `/gd-achievements/${aid}/review`, 'PUT', { status: 1 });
      log('⑩ 成果：上传→教师审阅', rv.ok, rv.ok ? `achievementId=${aid} 已通过` : (rv.json && rv.json.message));
    } else log('⑩ 成果上传', false, c.json && c.json.message);
  }

  // ---- 11. 学生基于已录用申请写实习报告 + 提交，教师评分 ----
  {
    const c = await api(student.token, '/reports', 'POST', { application_id: appId, title: '端到端演示实习报告', content: '实习总结内容。' });
    if (c.ok) {
      const rid = c.json.data.id;
      await api(student.token, `/reports/${rid}/submit`, 'PUT');
      const rv = await api(teacher.token, `/reports/${rid}/review`, 'PUT', { teacher_score: 92, teacher_comment: '报告完整，评分92' });
      log('⑪ 报告：撰写→提交→教师评分', rv.ok, rv.ok ? `reportId=${rid} score=${rv.json.data.teacher_score}` : (rv.json && rv.json.message));
    } else log('⑪ 报告创建', false, c.json && c.json.message);
  }

  // ---- 12. 教师新增指导记录 ----
  {
    const r = await api(teacher.token, '/gd-guidances', 'POST', { student_id: sid, guidance_date: todayStr(), title: '端到端演示指导', content: '指导内容。' });
    log('⑫ 教师新增指导记录', r.ok, r.ok ? `guidanceId=${r.json.data.id}` : (r.json && r.json.message));
  }

  // ---- 13. 学生侧未读通知数（验证全链路通知已下发）----
  {
    const r = await api(student.token, '/notifications/unread-count');
    log('⑬ 学生未读通知数', r.ok, r.ok ? `unread=${r.json.data.count}` : (r.json && r.json.message));
  }

  const pass = results.filter(r => r.ok).length;
  console.log(`\n==== 完成：${pass}/${results.length} 个环节通过 ====`);
})();
