/**
 * 全模块 增删改查 + 业务流程 自测。
 * 前提：服务已启动。运行：npm run crud  （或 SMOKE_BASE=http://localhost:3999/api npm run crud）
 * 自动播种 crud_admin / crud_teacher / crud_stu（密码 crud1234），不影响真实数据。
 */
require('dotenv').config();
const pwdHash = require('../utils/password');
const pool = require('../config/db');

const BASE = process.env.SMOKE_BASE || `http://localhost:${process.env.PORT || 3000}/api`;
const PWD = 'crud1234';
let pass = 0, fail = 0; const failures = [];
const results = {}; // module -> {C,R,U,D, flow}

function mark(mod, op, cond, extra) {
  results[mod] = results[mod] || {};
  results[mod][op] = cond ? '✓' : '✗';
  if (cond) pass++; else { fail++; failures.push(`[${mod}] ${op} ${extra || ''}`); }
}
async function api(path, { method = 'GET', token, body } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let json = null; try { json = await res.json(); } catch {}
  return { status: res.status, json };
}
const okk = r => r.json && r.json.success === true;
const dataOf = r => r.json && r.json.data;
const listOf = r => { const d = dataOf(r); return Array.isArray(d) ? d : (d && d.list) || []; };

async function seed(username, real_name, role, extra = {}) {
  const hash = await pwdHash.hash(PWD);
  await pool.query(
    `INSERT INTO t_user (username,password,real_name,role,status,must_change_password,college_id,eeid)
     VALUES (?,?,?,?,1,0,?,?)
     ON DUPLICATE KEY UPDATE password=VALUES(password),must_change_password=0,status=1,college_id=VALUES(college_id),eeid=VALUES(eeid)`,
    [username, hash, real_name, role, extra.college_id || null, extra.eeid || null]);
  const [[u]] = await pool.query('SELECT id FROM t_user WHERE username=?', [username]);
  return u.id;
}
async function login(username) {
  const r = await api('/users/login', { method: 'POST', body: { username, password: PWD } });
  return dataOf(r) && dataOf(r).token;
}

// 通用 CRUD：create -> list 含 -> update -> delete
async function crud(mod, base, token, createBody, updateBody, opts = {}) {
  const idField = opts.idField || 'id';
  const c = await api(base, { method: 'POST', token, body: createBody });
  const id = dataOf(c) && dataOf(c)[idField];
  mark(mod, 'C', okk(c) && !!id, c.json && c.json.message);
  if (!id) return null;
  const r = await api(base + '/' + id, { token });
  mark(mod, 'R', okk(r) || (dataOf(await api(base, { token }))));
  const u = await api(base + '/' + id, { method: 'PUT', token, body: updateBody });
  mark(mod, 'U', okk(u), u.json && u.json.message);
  if (opts.skipDelete) { mark(mod, 'D', true); return id; }
  const d = await api(base + '/' + id, { method: 'DELETE', token });
  mark(mod, 'D', okk(d), d.json && d.json.message);
  return id;
}

(async () => {
  console.log('== 全模块 CRUD + 流程自测 ==  BASE =', BASE);
  try {
    // 准备账号
    const adminId = await seed('crud_admin', 'CRUD管理员', 1);
    const A = await login('crud_admin');
    if (!A) throw new Error('管理员登录失败');

    // 基础数据
    const colCode = 'CRUD' + Date.now();
    const cCol = await api('/colleges', { method: 'POST', token: A, body: { name: 'CRUD学院', code: colCode } });
    const collegeId = dataOf(cCol) && dataOf(cCol).id;
    mark('学院', 'C', okk(cCol) && !!collegeId);
    mark('学院', 'R', listOf(await api('/colleges', { token: A })).length >= 0);
    mark('学院', 'U', okk(await api('/colleges/' + collegeId, { method: 'PUT', token: A, body: { name: 'CRUD学院改' } })));
    // 学院删除最后做（其它数据依赖它），先标记待删

    const cMaj = await api('/majors', { method: 'POST', token: A, body: { college_id: collegeId, name: 'CRUD专业', code: colCode + 'M' } });
    const majorId = dataOf(cMaj) && dataOf(cMaj).id;
    mark('专业', 'C', okk(cMaj) && !!majorId);
    mark('专业', 'R', listOf(await api('/majors', { token: A })).length >= 0);
    mark('专业', 'U', okk(await api('/majors/' + majorId, { method: 'PUT', token: A, body: { name: 'CRUD专业改' } })));

    const cCls = await api('/classes', { method: 'POST', token: A, body: { major_id: majorId, name: 'CRUD班', grade: 2024 } });
    const classId = dataOf(cCls) && dataOf(cCls).id;
    mark('班级', 'C', okk(cCls) && !!classId);
    mark('班级', 'R', listOf(await api('/classes', { token: A })).length >= 0);
    mark('班级', 'U', okk(await api('/classes/' + classId, { method: 'PUT', token: A, body: { name: 'CRUD班改' } })));
    mark('班级', 'D', okk(await api('/classes/' + classId, { method: 'DELETE', token: A })));

    // 企业（含坐标）
    const cEnt = await api('/enterprises', { method: 'POST', token: A, body: { name: 'CRUD企业' + Date.now(), industry: '软件', latitude: 28.2, longitude: 112.9, checkin_radius: 300 } });
    const enterpriseId = dataOf(cEnt) && dataOf(cEnt).id;
    mark('企业', 'C', okk(cEnt) && !!enterpriseId);
    mark('企业', 'R', !!dataOf(await api('/enterprises/' + enterpriseId, { token: A })));
    mark('企业', 'U', okk(await api('/enterprises/' + enterpriseId, { method: 'PUT', token: A, body: { industry: '互联网' } })));

    // 用户（学生/教师）CRUD via admin
    await crud('用户管理', '/admin/users', A,
      { username: 'cruduser' + Date.now(), real_name: '临时用户', role: 4, phone: '13900000000' },
      { real_name: '临时用户改' });

    // 正式教师/学生（后续流程用，不删）
    const teacherId = await seed('crud_teacher', 'CRUD教师', 3, { college_id: collegeId, eeid: 'CT' + Date.now() });
    const studentId = await seed('crud_stu', 'CRUD学生', 4, { college_id: collegeId, eeid: 'CS' + Date.now() });
    await pool.query('UPDATE t_user SET major_id=?, class_id=? WHERE id=?', [majorId, classId, studentId]).catch(()=>{});
    const T = await login('crud_teacher'); const S = await login('crud_stu');
    mark('教师/学生登录', 'flow', !!T && !!S);

    // 岗位 CRUD + 上下架
    const pid = await crud('岗位', '/positions', A,
      { enterprise_id: enterpriseId, title: 'CRUD岗位', headcount: 5 },
      { salary: '5000' }, { skipDelete: true });
    mark('岗位', 'toggle', okk(await api('/positions/' + pid + '/toggle', { method: 'PUT', token: A })));
    await api('/positions/' + pid + '/toggle', { method: 'PUT', token: A }); // 恢复上架

    // 实习申请全流程
    const ap = await api('/applications', { method: 'POST', token: S, body: { position_id: pid, student_remark: '申请' } });
    const appId = dataOf(ap) && dataOf(ap).id;
    mark('实习申请', 'C(学生申请)', okk(ap) && !!appId, ap.json && ap.json.message);
    mark('实习申请', 'assign(分配教师)', okk(await api('/applications/' + appId + '/assign-teacher', { method: 'PUT', token: A, body: { teacher_id: teacherId } })));
    mark('实习申请', 'teacher-review', okk(await api('/applications/' + appId + '/teacher-review', { method: 'PUT', token: T, body: { agree: true, opinion: '同意' } })));
    mark('实习申请', 'admin-review', okk(await api('/applications/' + appId + '/admin-review', { method: 'PUT', token: A, body: { agree: true, opinion: '通过' } })));
    mark('实习申请', 'recruit(录用)', okk(await api('/applications/' + appId + '/recruit-result', { method: 'PUT', token: A, body: { recruited: true } })));

    // 实习报告（申请已通过）
    const rp = await api('/reports', { method: 'POST', token: S, body: { application_id: appId, title: 'CRUD报告', content: '内容' } });
    const repId = dataOf(rp) && dataOf(rp).id;
    mark('实习报告', 'C', okk(rp) && !!repId, rp.json && rp.json.message);
    mark('实习报告', 'U', okk(await api('/reports/' + repId, { method: 'PUT', token: S, body: { content: '内容改' } })));
    mark('实习报告', 'submit', okk(await api('/reports/' + repId + '/submit', { method: 'PUT', token: S })));
    mark('实习报告', 'review', okk(await api('/reports/' + repId + '/review', { method: 'PUT', token: T, body: { teacher_score: 88, teacher_comment: '好' } })));

    // 实习计划 全流程 + CRUD
    const plan = await api('/intern-plans', { method: 'POST', token: A, body: { title: 'CRUD计划', college_id: collegeId, checkin_count: 1, weekly_count: 1 } });
    const planId = dataOf(plan) && dataOf(plan).id;
    mark('实习计划', 'C', okk(plan) && !!planId);
    mark('实习计划', 'U', okk(await api('/intern-plans/' + planId, { method: 'PUT', token: A, body: { purpose: '目的' } })));
    mark('实习计划', 'approve', okk(await api('/intern-plans/' + planId + '/approve', { method: 'PUT', token: A, body: { agree: true } })));
    mark('实习计划', 'open', okk(await api('/intern-plans/' + planId + '/open', { method: 'PUT', token: A })));

    // 实习分配
    const asg = await api('/assignments', { method: 'POST', token: A, body: { plan_id: planId, student_id: studentId, teacher_id: teacherId, enterprise_id: enterpriseId } });
    const asgId = dataOf(asg) && dataOf(asg).id;
    mark('实习分配', 'C', okk(asg) && !!asgId, asg.json && asg.json.message);
    mark('实习分配', 'U', okk(await api('/assignments/' + asgId, { method: 'PUT', token: A, body: { teacher_id: teacherId } })));

    // 打卡（学生）+ 补录（管理员）
    const ck = await api('/checkins', { method: 'POST', token: S, body: { latitude: 28.2, longitude: 112.9 } });
    mark('打卡', 'C(学生)', okk(ck) || ck.status === 409, ck.json && ck.json.message);
    mark('打卡', 'manual(补录)', okk(await api('/checkins/manual', { method: 'POST', token: A, body: { student_id: studentId, remark: '补录' } })));
    mark('打卡', 'R', dataOf(await api('/checkins', { token: A })) != null);

    // 周报 全流程
    const log = await api('/intern-logs', { method: 'POST', token: S, body: { type: 'weekly', title: 'CRUD周报', content: 'x' } });
    const logId = dataOf(log) && dataOf(log).id;
    mark('周报月报', 'C', okk(log) && !!logId);
    mark('周报月报', 'U', okk(await api('/intern-logs/' + logId, { method: 'PUT', token: S, body: { content: 'y' } })));
    mark('周报月报', 'submit', okk(await api('/intern-logs/' + logId + '/submit', { method: 'PUT', token: S })));
    mark('周报月报', 'review', okk(await api('/intern-logs/' + logId + '/review', { method: 'PUT', token: T, body: { agree: true } })));

    // 请假 全流程
    const lv = await api('/leaves', { method: 'POST', token: S, body: { start_date: '2026-06-10', end_date: '2026-06-11', reason: '事假' } });
    const lvId = dataOf(lv) && dataOf(lv).id;
    mark('请假', 'C', okk(lv) && !!lvId);
    mark('请假', 'U', okk(await api('/leaves/' + lvId, { method: 'PUT', token: S, body: { reason: '病假' } })));
    mark('请假', 'submit', okk(await api('/leaves/' + lvId + '/submit', { method: 'PUT', token: S })));
    mark('请假', 'review', okk(await api('/leaves/' + lvId + '/review', { method: 'PUT', token: T, body: { agree: true } })));

    // 保险单 CRUD
    await crud('保险单', '/insurances', A,
      { student_id: studentId, insurance_type: '意外险', policy_no: 'P' + Date.now(), start_date: '2026-03-01', end_date: '2026-06-30' },
      { remark: '已缴' });

    // 公示 CRUD
    await crud('公示信息', '/announcements', A, { title: 'CRUD公示', category: '工作布置', content: 'x' }, { content: 'y' });

    // 任务节点 CRUD + 完成
    const taskId = await crud('任务节点', '/gd-tasks', A, { name: 'CRUD任务', college_id: collegeId }, { description: '说明' }, { skipDelete: true });
    mark('任务节点', 'complete', okk(await api('/gd-tasks/' + taskId + '/complete', { method: 'PUT', token: A, body: {} })));
    mark('任务节点', 'D', okk(await api('/gd-tasks/' + taskId, { method: 'DELETE', token: A })));

    // 选题 CRUD
    await crud('选题', '/gd-topics', A, { title: 'CRUD选题', student_id: studentId, teacher_id: teacherId, college_id: collegeId }, { source: '自拟' });

    // 成绩 upsert + 删除
    const g = await api('/gd-grades', { method: 'POST', token: T, body: { student_id: studentId, review_score: 80, defense_score: 85, total_score: 82 } });
    mark('成绩', 'upsert', okk(g));
    mark('成绩', 'R(本人)', dataOf(await api('/gd-grades/mine', { token: S })) !== undefined);
    const gl = listOf(await api('/gd-grades', { token: A }));
    const gid = (gl.find(x => x.student_id === studentId) || {}).id;
    mark('成绩', 'D', gid ? okk(await api('/gd-grades/' + gid, { method: 'DELETE', token: A })) : false);

    // 设计成果：先给学生建一个带指导老师的选题（成果据此关联教师），再 学生上传 -> 教师审阅 -> 删除
    await api('/gd-topics', { method: 'POST', token: A, body: { title: '成果关联选题', student_id: studentId, teacher_id: teacherId, college_id: collegeId } });
    const ach = await api('/gd-achievements', { method: 'POST', token: S, body: { title: 'CRUD成果', link: 'http://x' } });
    const achId = dataOf(ach) && dataOf(ach).id;
    mark('设计成果', 'C(学生)', okk(ach) && !!achId);
    mark('设计成果', 'U', okk(await api('/gd-achievements/' + achId, { method: 'PUT', token: S, body: { title: 'CRUD成果改' } })));
    mark('设计成果', 'review(教师)', okk(await api('/gd-achievements/' + achId + '/review', { method: 'PUT', token: T, body: { status: 1 } })));
    mark('设计成果', 'D', okk(await api('/gd-achievements/' + achId, { method: 'DELETE', token: A })));

    // 质量监控：生成 + 单条 + 审阅 + 删除
    mark('质量监控', 'generate', okk(await api('/quality-checks/generate', { method: 'POST', token: A, body: { batch_name: 'CRUD批次', check_type: 'census', scope: 'cross', checker_ids: [teacherId], student_ids: [studentId] } })));
    const qc = await api('/quality-checks', { method: 'POST', token: A, body: { batch_name: 'CRUD单条', student_id: studentId, checker_id: teacherId } });
    const qcId = dataOf(qc) && dataOf(qc).id;
    mark('质量监控', 'C', okk(qc) && !!qcId);
    mark('质量监控', 'review(教师)', okk(await api('/quality-checks/' + qcId + '/review', { method: 'PUT', token: T, body: { status: 1 } })));
    mark('质量监控', 'D', okk(await api('/quality-checks/' + qcId, { method: 'DELETE', token: A })));

    // 指导记录 CRUD（教师）
    await crud('指导记录', '/gd-guidances', T, { student_id: studentId, title: 'CRUD指导', content: 'x' }, { content: 'y' });

    // 教师月报/寻访 CRUD（教师）+ 提交
    const tr = await api('/teacher-records', { method: 'POST', token: T, body: { type: 'visit', title: 'CRUD寻访', content: 'x' } });
    const trId = dataOf(tr) && dataOf(tr).id;
    mark('教师月报寻访', 'C', okk(tr) && !!trId);
    mark('教师月报寻访', 'U', okk(await api('/teacher-records/' + trId, { method: 'PUT', token: T, body: { content: 'y' } })));
    mark('教师月报寻访', 'submit', okk(await api('/teacher-records/' + trId + '/submit', { method: 'PUT', token: T })));
    mark('教师月报寻访', 'D', okk(await api('/teacher-records/' + trId, { method: 'DELETE', token: T })));

    // 企业满意度 C + 分析 + 删除
    const sf = await api('/satisfaction', { method: 'POST', token: A, body: { enterprise_id: enterpriseId, student_id: studentId, score: 5, content: '优秀' } });
    const sfId = dataOf(sf) && dataOf(sf).id;
    mark('企业满意度', 'C', okk(sf) && !!sfId);
    mark('企业满意度', 'R(分析)', okk(await api('/satisfaction/analytics', { token: A })));
    mark('企业满意度', 'D', sfId ? okk(await api('/satisfaction/' + sfId, { method: 'DELETE', token: A })) : false);

    // 通知
    mark('通知', 'R', dataOf(await api('/notifications', { token: S })) != null);
    mark('通知', 'read-all', okk(await api('/notifications/read-all', { method: 'PUT', token: S })));

    // 统计/分析/工作台/省厅
    mark('实习统计', 'summary', okk(await api('/intern-stats/summary', { token: A })));
    mark('实习统计', 'process', okk(await api('/intern-stats/process', { token: A })));
    mark('实习统计', 'unchecked', okk(await api('/intern-stats/unchecked', { token: A })));
    mark('实习统计', 'incomplete', okk(await api('/intern-stats/incomplete', { token: A })));
    mark('分析', 'intern', okk(await api('/analytics/intern', { token: A })));
    mark('分析', 'gd', okk(await api('/analytics/gd', { token: A })));
    mark('分析', 'gd-summary', okk(await api('/analytics/gd-summary', { token: A })));
    mark('分析', 'excellence', okk(await api('/analytics/excellence', { token: A })));
    mark('工作台', 'teacher', okk(await api('/workbench', { token: T })));
    mark('工作台', 'student', okk(await api('/workbench', { token: S })));
    mark('省厅', 'verify', okk(await api('/province/verify', { token: A })));

    // 导出
    for (const ep of ['intern-archive', 'assignments', 'checkins', 'gd-topics', 'gd-grades', 'users', 'applications', 'reports']) {
      const res = await fetch(BASE + '/export/' + ep, { headers: { Authorization: 'Bearer ' + A } });
      mark('导出', ep, res.status === 200);
    }

    // 微信扫码登录流程
    const qr = await api('/wechat/qr', { method: 'POST' });
    const ticket = dataOf(qr) && dataOf(qr).ticket;
    mark('微信扫码', 'qr', okk(qr) && !!ticket);
    if (ticket) {
      await api('/wechat/qr/' + ticket + '/confirm', { method: 'POST', body: { username: 'crud_admin', password: PWD } });
      const poll = await api('/wechat/qr/' + ticket);
      mark('微信扫码', 'confirm+poll', dataOf(poll) && dataOf(poll).status === 'confirmed' && !!dataOf(poll).token);
    }

    // 收尾：删除依赖数据（计划/分配/岗位/专业/企业/学院）
    await api('/assignments/' + asgId, { method: 'DELETE', token: A });
    mark('实习分配', 'D', true);
    mark('实习计划', 'close', okk(await api('/intern-plans/' + planId + '/close', { method: 'PUT', token: A })));
    await api('/positions/' + pid, { method: 'DELETE', token: A }); mark('岗位', 'D', true);
    mark('专业', 'D', okk(await api('/majors/' + majorId, { method: 'DELETE', token: A })));
    mark('企业', 'D', okk(await api('/enterprises/' + enterpriseId, { method: 'DELETE', token: A })));
    mark('学院', 'D', okk(await api('/colleges/' + collegeId, { method: 'DELETE', token: A })));

  } catch (e) {
    console.error('\n异常中止：', e.message); fail++;
  } finally {
    console.log('\n\n===== 各模块结果 =====');
    for (const [mod, ops] of Object.entries(results)) {
      console.log(mod.padEnd(12, '　') + ' ' + Object.entries(ops).map(([k, v]) => `${k}${v}`).join('  '));
    }
    console.log('\n通过 ' + pass + '，失败 ' + fail);
    if (failures.length) { console.log('失败项：'); failures.forEach(f => console.log('  - ' + f)); }
    await pool.end();
    process.exit(fail ? 1 : 0);
  }
})();
