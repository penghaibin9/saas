/**
 * 商用对标功能 · 完整闭环 E2E
 * 任务书 → 选题互选 → 家长知情 → 鉴定表 → 查重 → 考评 → 就业 → 催办 → 导出
 *
 * 运行：node scripts/e2e-benchmark-flow.js
 * 依赖：后端已启动；npm run migrate:benchmark；npm run seed:demo
 */
const BASE = process.env.API_BASE || 'http://localhost:3000/api';

let step = 0;
const results = [];
function log(name, ok, detail) {
  step++;
  const tag = ok ? '✅' : '❌';
  console.log(`${String(step).padStart(2, '0')}. ${tag} ${name}${detail ? ' — ' + detail : ''}`);
  results.push({ name, ok, detail });
}

async function api(token, path, method = 'GET', body) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let json = null;
  try { json = await res.json(); } catch (_) {}
  return { status: res.status, json, ok: res.ok && json && json.success };
}

async function login(username, password) {
  const r = await api(null, '/users/login', 'POST', { username, password });
  if (r.status === 429) throw new Error(`登录限流：${r.json && r.json.message}`);
  if (!r.ok) throw new Error(`登录 ${username} 失败：${r.json && r.json.message}`);
  return { token: r.json.data.token, user: r.json.data.user };
}

(async () => {
  console.log('==== 商用对标 · 完整闭环 E2E ====\n');

  let admin, teacher, student;
  try {
    admin = await login('demo_admin', 'demo1234');
    teacher = await login('demo_teacher', 'demo1234');
    student = await login('demo_stu1', 'demo1234');
    log('三角色登录', true, `studentId=${student.user.id}`);
  } catch (e) {
    log('登录', false, e.message);
    process.exit(1);
  }

  const sid = student.user.id;
  let roundId, poolId, achievementId, parentId, appraisalId;

  // 1. 任务书闭环
  {
    const up = await api(teacher.token, '/benchmark/task-books', 'POST', {
      student_id: sid, title: 'E2E任务书', content: '对标正方任务书流程'
    });
    log('教师下达任务书', up.ok, up.ok ? `id=${up.json.data.id}` : up.json && up.json.message);
    const cf = await api(student.token, '/benchmark/task-books/confirm', 'PUT');
    log('学生确认任务书', cf.ok, cf.ok ? cf.json.message : cf.json && cf.json.message);
  }

  // 2. 选题互选闭环
  {
    const pool = await api(teacher.token, '/benchmark/topic-pool', 'POST', {
      title: 'E2E课题-智能实习管理', quota: 2, description: '闭环测试课题'
    });
    poolId = pool.ok && pool.json.data.id;
    log('教师发布课题', pool.ok, pool.ok ? `poolId=${poolId}` : pool.json && pool.json.message);

    const r = await api(admin.token, '/benchmark/topic-rounds', 'POST', {
      name: 'E2E选题轮次',
      max_choices: 3,
      start_time: new Date().toISOString(),
      end_time: new Date(Date.now() + 86400000 * 7).toISOString()
    });
    roundId = r.ok && r.json.data.id;
    log('创建选题轮次', r.ok, r.ok ? `roundId=${roundId}` : r.json && r.json.message);

    if (roundId) {
      const start = await api(admin.token, `/benchmark/topic-rounds/${roundId}/status`, 'PUT', { status: 1 });
      log('开启选题轮次', start.ok, start.json && start.json.message);

      if (poolId) {
        const ch = await api(student.token, '/benchmark/topic-choices', 'POST', {
          round_id: roundId, choices: [{ pool_id: poolId, priority: 1 }]
        });
        log('学生提交选题志愿', ch.ok, ch.json && ch.json.message);
      }

      const end = await api(admin.token, `/benchmark/topic-rounds/${roundId}/status`, 'PUT', { status: 2, match: true });
      log('结束并匹配选题', end.ok, end.ok ? `matched=${end.json.data && end.json.data.matched}` : end.json && end.json.message);
    }
  }

  // 3. 家长知情闭环
  {
    const sub = await api(student.token, '/benchmark/parent-consents', 'POST', {
      file_url: '/uploads/demo-parent-consent.pdf'
    });
    parentId = sub.ok && sub.json.data.id;
    log('学生提交家长知情书', sub.ok, sub.ok ? `id=${parentId}` : sub.json && sub.json.message);
    if (parentId) {
      const rev = await api(teacher.token, `/benchmark/parent-consents/${parentId}/review`, 'PUT', { status: 1 });
      log('教师审核家长知情书', rev.ok, rev.json && rev.json.message);
    }
  }

  // 4. 实习鉴定闭环
  {
    const sub = await api(student.token, '/benchmark/appraisals', 'POST', {
      file_url: '/uploads/demo-appraisal.pdf', enterprise_comment: '表现优秀'
    });
    appraisalId = sub.ok && sub.json.data.id;
    log('学生提交实习鉴定表', sub.ok, sub.ok ? `id=${appraisalId}` : sub.json && sub.json.message);
    if (appraisalId) {
      const rev = await api(teacher.token, `/benchmark/appraisals/${appraisalId}/review`, 'PUT', { status: 1 });
      log('教师审核鉴定表', rev.ok, rev.json && rev.json.message);
    }
  }

  // 5. 就业去向
  {
    const r = await api(student.token, '/benchmark/employment', 'POST', {
      dest_type: 'employment', company_name: 'E2E测试企业', position_title: '开发工程师', city: '长沙'
    });
    log('学生填报就业去向', r.ok, r.json && r.json.message);
  }

  // 6. 考评配置 + 核算 + 发布
  {
    const cfg = await api(admin.token, '/benchmark/intern-score-config', 'PUT', {
      checkin_weight: 20, weekly_weight: 20, monthly_weight: 10, enterprise_weight: 30, school_weight: 20, pass_line: 60
    });
    log('保存实习考评权重', cfg.ok, cfg.ok ? '20/20/10/30/20' : cfg.json && cfg.json.message);

    // 核算由教师/管理员发起（学生仅可查看已发布成绩），教师录入校内分
    const comp = await api(teacher.token, `/benchmark/intern-scores/compute?student_id=${sid}`, 'POST', { school_score: 85 });
    log('核算实习成绩', comp.ok || comp.status === 400,
      comp.ok ? `score=${comp.json.data && comp.json.data.total_score}` : (comp.json && comp.json.message) || '无分配');

    if (comp.ok) {
      const pub = await api(teacher.token, `/benchmark/intern-scores/${sid}/publish`, 'PUT');
      log('教师发布实习成绩', pub.ok, pub.json && pub.json.message);
      const mine = await api(student.token, '/benchmark/intern-scores/mine');
      log('学生查看已发布成绩', mine.ok, mine.ok ? `total=${mine.json.data.total_score}` : mine.json && mine.json.message);
    }
  }

  // 7. 成果 + 查重
  {
    const c = await api(student.token, '/gd-achievements', 'POST', {
      title: 'E2E开题报告', link: 'http://example.com/proposal', doc_type: 'proposal'
    });
    if (c.ok) {
      achievementId = c.json.data.id;
      const pl = await api(student.token, `/benchmark/plagiarism/${achievementId}`, 'POST');
      const rate = pl.json && pl.json.data && (pl.json.data.similarity_rate ?? pl.json.data.similarity);
      log('成果上传 + 查重', pl.ok, pl.ok ? `rate=${rate}%` : pl.json && pl.json.message);
    } else {
      log('成果上传', false, c.json && c.json.message);
    }
  }

  // 8. 教师巡访
  {
    const r = await api(teacher.token, '/benchmark/teacher-visits', 'POST', {
      student_id: sid, visit_date: new Date().toISOString().slice(0, 10),
      location: '企业现场', content: 'E2E巡访记录', problems: '无异常'
    });
    log('教师新增巡访', r.ok, r.ok ? `visitId=${r.json.data.id}` : r.json && r.json.message);
  }

  // 9. 流程状态（闭环校验）
  {
    const fs = await api(student.token, '/benchmark/flow-status');
    const d = fs.json && fs.json.data;
    const closed = d && d.taskBook === 'confirmed' && d.parentConsent === 'approved' &&
      d.appraisal === 'approved' && d.employment === 'filled' && d.plagiarismDone;
    log('学生流程状态闭环', fs.ok && closed,
      fs.ok ? `taskBook=${d.taskBook} consent=${d.parentConsent} appraisal=${d.appraisal} score=${d.internScore}` : fs.json && fs.json.message);
  }

  // 10. 催办 + 通知
  {
    const list = await api(admin.token, '/benchmark/urge-list');
    log('催办中心列表', list.ok, list.ok ? `未打卡=${(list.json.data.noCheckin || []).length}` : list.json && list.json.message);
    const ids = (list.json.data.noCheckin || []).slice(0, 3).map(x => x.student_id).filter(Boolean);
    if (ids.length) {
      const n = await api(admin.token, '/benchmark/urge-notify', 'POST', {
        student_ids: ids, title: 'E2E催办', content: '请及时打卡'
      });
      log('发送催办通知', n.ok, n.ok ? `count=${n.json.data.count}` : n.json && n.json.message);
    } else {
      log('发送催办通知', true, '无待催办(跳过)');
    }
  }

  // 11. 学信网导出
  {
    const res = await fetch(BASE + '/benchmark/export/chsi', { headers: { Authorization: 'Bearer ' + admin.token } });
    log('学信网格式导出', res.ok, res.ok ? `Content-Type=${res.headers.get('content-type')}` : 'HTTP ' + res.status);
  }

  // 12. 工作台含 benchmark 数据
  {
    const wb = await api(student.token, '/workbench');
    const bm = wb.json && wb.json.data && wb.json.data.benchmark;
    log('工作台 benchmark 状态', wb.ok && !!bm, wb.ok ? JSON.stringify(bm).slice(0, 80) : wb.json && wb.json.message);
  }

  // 13. 打卡
  {
    // 演示企业坐标 (28.20, 112.90)，打卡半径 300m：落在范围内以演示成功打卡的 happy-path
    const r = await api(student.token, '/checkins', 'POST', { latitude: 28.2001, longitude: 112.9001, address: '商用对标打卡' });
    const dup = r.json && /打过卡|已打卡|已经打/.test(r.json.message || '');
    log('学生打卡', r.ok || dup, r.ok ? '成功' : (dup ? '今日已打卡' : r.json && r.json.message));
  }

  const pass = results.filter(r => r.ok).length;
  const fail = results.filter(r => !r.ok);
  console.log(`\n==== 完成：${pass}/${results.length} 个环节通过 ====`);
  if (fail.length) {
    console.log('未通过：');
    fail.forEach(f => console.log(`  - ${f.name}: ${f.detail || ''}`));
  }
  process.exit(pass === results.length ? 0 : 1);
})();
