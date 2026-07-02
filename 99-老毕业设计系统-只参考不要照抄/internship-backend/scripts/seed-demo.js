/**
 * 演示数据种子：贯穿实习 + 毕设两大子系统，便于答辩演示各页面有数据。
 * 幂等：以固定 code/username 判断，已存在则复用，不重复灌入。
 * 前提：基础表与新表已建（先 `npm run migrate:all`）。
 * 运行：npm run seed:demo
 *
 * 演示账号（密码均为 demo1234）：
 *   demo_admin(院校管理员) / demo_teacher(指导教师) / demo_stu1 demo_stu2(学生)
 */
require('dotenv').config();
const fs = require('fs');
const path = require('path');
const pwdHash = require('../utils/password');
const pool = require('../config/db');

function ensureDemoFiles() {
  const dir = path.join(__dirname, '..', 'uploads');
  fs.mkdirSync(dir, { recursive: true });
  // 最小合法 PDF，避免演示页面出现“附件记录存在但文件下载失败”。
  const pdf = Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n');
  for (const name of ['demo-consent.pdf', 'demo-appraisal.pdf', 'demo-paper.pdf']) {
    const file = path.join(dir, name);
    if (!fs.existsSync(file)) fs.writeFileSync(file, pdf);
  }
}

async function one(sql, params) { const [r] = await pool.query(sql, params); return r; }
async function val(sql, params) { const [[row]] = await pool.query(sql, params); return row; }

async function ensureUser(username, real_name, role, extra = {}) {
  const hash = await pwdHash.hash('demo1234');
  await pool.query(
    `INSERT INTO t_user (username,password,real_name,role,status,must_change_password,college_id,major_id,class_id,eeid,phone)
     VALUES (?,?,?,?,1,0,?,?,?,?,?)
     ON DUPLICATE KEY UPDATE real_name=VALUES(real_name), role=VALUES(role), status=1,
       college_id=VALUES(college_id), major_id=VALUES(major_id), class_id=VALUES(class_id), eeid=VALUES(eeid)`,
    [username, hash, real_name, role, extra.college_id || null, extra.major_id || null,
     extra.class_id || null, extra.eeid || null, extra.phone || null]
  );
  return (await val('SELECT id FROM t_user WHERE username = ?', [username])).id;
}

async function ensureMajor(collegeId, code, name) {
  await pool.query(`INSERT INTO t_major (college_id, name, code) VALUES (?,?,?)
    ON DUPLICATE KEY UPDATE name=VALUES(name)`, [collegeId, name, code]);
  return (await val('SELECT id FROM t_major WHERE code=?', [code])).id;
}
async function ensureClass(collegeId, majorId, name, grade) {
  let c = await val('SELECT id FROM t_class WHERE name=? AND college_id=?', [name, collegeId]);
  if (!c) { const r = await one(`INSERT INTO t_class (college_id,major_id,name,grade) VALUES (?,?,?,?)`, [collegeId, majorId, name, grade]); c = { id: r.insertId }; }
  return c.id;
}
async function ensureEnterprise(name, e) {
  let row = await val('SELECT id FROM t_enterprise WHERE name=? AND is_deleted=0', [name]);
  if (!row) {
    const r = await one(`INSERT INTO t_enterprise (name,short_name,industry,address,contact_name,contact_phone,latitude,longitude,checkin_radius,status)
      VALUES (?,?,?,?,?,?,?,?,?,?)`,
      [name, e.short, e.industry, e.address, e.contact, e.phone, e.lat, e.lng, e.radius, e.status ?? 1]);
    row = { id: r.insertId };
  }
  return row.id;
}
const pick = (arr, i) => arr[i % arr.length];

/**
 * 批量灌"丰满"演示数据，让每个页面/筛选 tab 都有数据。幂等：以唯一 username / NOT EXISTS 守护。
 */
async function seedBulk({ collegeId, baseMajorId, baseClassId, baseTeacherId, baseEntId, planId, stu1, stu2 }) {
  console.log('== 灌入丰满批量数据 ==');

  // —— 3 专业 ——（含已有软件技术）
  const majors = [
    { id: baseMajorId, code: 'DEMO_SE', name: '软件技术' },
    { id: await ensureMajor(collegeId, 'DEMO_BD', '大数据技术'), code: 'DEMO_BD' },
    { id: await ensureMajor(collegeId, 'DEMO_IOT', '物联网应用技术'), code: 'DEMO_IOT' },
  ];
  // —— 6 班 ——（每专业 2 班）
  const classes = [];
  classes.push({ id: baseClassId, majorId: baseMajorId }); // 演示2024班（软件）
  const classDefs = [
    ['软件技术2402班', majors[0].id], ['大数据2401班', majors[1].id], ['大数据2402班', majors[1].id],
    ['物联网2401班', majors[2].id], ['物联网2402班', majors[2].id],
  ];
  for (const [nm, mid] of classDefs) classes.push({ id: await ensureClass(collegeId, mid, nm, 2024), majorId: mid });

  // —— 3 教师 ——（含已有 demo_teacher）
  const teachers = [baseTeacherId];
  teachers.push(await ensureUser('demo_t002', '李明（样例教师）', 3, { college_id: collegeId, eeid: 'DT002', phone: '13800000010' }));
  teachers.push(await ensureUser('demo_t003', '王芳（样例教师）', 3, { college_id: collegeId, eeid: 'DT003', phone: '13800000011' }));

  // —— 10 企业 ——（含已有演示科技），坐标在长沙岳麓区附近
  const entDefs = [
    ['湘江网络科技有限公司', '湘江网络', '互联网', '长沙市岳麓区麓谷大道', '刘经理', '0731-85000001', 28.2030, 112.9050, 400],
    ['麓谷软件股份有限公司', '麓谷软件', '软件开发', '长沙市岳麓区文轩路', '陈经理', '0731-85000002', 28.1985, 112.8970, 500],
    ['星城大数据有限公司', '星城数据', '大数据', '长沙市岳麓区岳麓大道', '周经理', '0731-85000003', 28.2100, 112.9100, 350],
    ['岳麓智能制造有限公司', '岳麓智能', '智能制造', '长沙市岳麓区桐梓坡路', '赵经理', '0731-85000004', 28.1950, 112.9200, 600],
    ['潇湘云计算有限公司', '潇湘云', '云计算', '长沙市岳麓区学士路', '钱经理', '0731-85000005', 28.2200, 112.8900, 450],
    ['长沙物联科技有限公司', '长沙物联', '物联网', '长沙市岳麓区雷锋大道', '孙经理', '0731-85000006', 28.1900, 112.9000, 500],
    ['橘子洲信息技术有限公司', '橘子洲科技', '信息技术', '长沙市天心区湘江中路', '吴经理', '0731-85000007', 28.1880, 112.9650, 400],
    ['天心信息工程有限公司', '天心信息', '信息工程', '长沙市天心区韶山路', '郑经理', '0731-85000008', 28.1100, 112.9900, 550],
    ['芙蓉智造科技有限公司', '芙蓉智造', '智能硬件', '长沙市芙蓉区五一大道', '冯经理', '0731-85000009', 28.1950, 113.0100, 500],
  ];
  const enterprises = [baseEntId];
  for (const d of entDefs) {
    enterprises.push(await ensureEnterprise(d[0], {
      short: d[1], industry: d[2], address: d[3], contact: d[4], phone: d[5], lat: d[6], lng: d[7], radius: d[8],
    }));
  }
  const entCoords = {}; // id -> {lat,lng,radius}
  for (const id of enterprises) {
    const e = await val('SELECT latitude,longitude,checkin_radius FROM t_enterprise WHERE id=?', [id]);
    entCoords[id] = { lat: Number(e.latitude), lng: Number(e.longitude), radius: Number(e.checkin_radius) || 300 };
  }

  // —— 20 岗位 ——（每企业约 2 个；2 个待审核 status=0 供"岗位审核"页有数据）
  const posTitles = ['Java开发实习生', '前端开发实习生', '大数据分析实习生', '测试工程师实习生', '运维实习生',
    'UI设计实习生', '产品助理实习生', '物联网开发实习生', '算法实习生', '技术支持实习生'];
  const positions = []; // {id, entId}
  for (let i = 0; i < 20; i++) {
    const entId = pick(enterprises, i);
    const title = `${pick(posTitles, i)}`;
    const st = i >= 18 ? 0 : 1; // 末尾 2 个待审核
    let p = await val('SELECT id FROM t_position WHERE title=? AND enterprise_id=? AND is_deleted=0', [title + '#' + (i + 1), entId]);
    if (!p) {
      const r = await one(`INSERT INTO t_position (enterprise_id,title,description,requirement,salary,headcount,location,college_id,status,intern_type,major_req,edu_req,work_time,welfare,to_regular,deadline,start_date,end_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
        [entId, title + '#' + (i + 1), '参与真实项目研发，跟随导师成长。', '相关专业，熟悉基础开发。', pick(['3000-4000', '4000-5000', '5000-6000'], i),
          pick([2, 3, 5], i), '长沙市岳麓区', collegeId, st, pick([1, 2], i), pick(['软件技术', '大数据技术', '物联网应用技术'], i),
          '大专', '弹性工作', '五险一金,餐补', pick([1, 0], i), '2026-05-31', '2026-03-01', '2026-06-30']);
      p = { id: r.insertId };
    }
    positions.push({ id: p.id, entId });
  }

  // —— 30 学生 ——（含已有 demo_stu1/2），分布到 6 班
  const students = [stu1, stu2];
  const sampleNames = ['张晨','李雨桐','王浩然','刘欣怡','陈子轩','杨思琪','赵文博','黄佳宁','周宇航','吴梦瑶','徐嘉豪','孙可欣','胡俊杰','朱雅婷','高铭泽','林诗涵','何宇辰','郭雨菲','马天佑','罗欣悦','梁睿','宋安琪','郑凯文','谢依诺','韩博文','唐思妍','冯皓','曹语彤'];
  for (let i = 1; i <= 28; i++) {
    const cls = pick(classes, i);
    const id = await ensureUser(`demo_s${String(i).padStart(3, '0')}`, `${sampleNames[i - 1]}（样例）`, 4,
      { college_id: collegeId, major_id: cls.majorId, class_id: cls.id, eeid: `DS${String(i + 10).padStart(3, '0')}`, phone: `139${String(10000000 + i).padStart(8, '0')}` });
    students.push(id);
  }

  // —— 分配（前 28 个学生进入实习）——
  const assigned = students.slice(0, 28);
  const asgOf = {}; // studentId -> {assignmentId, entId}
  for (let i = 0; i < assigned.length; i++) {
    const sid = assigned[i];
    const entId = pick(enterprises, i);
    const tId = pick(teachers, i);
    let a = await val('SELECT id FROM t_assignment WHERE student_id=? AND plan_id=? AND is_deleted=0', [sid, planId]);
    if (!a) { const r = await one(`INSERT INTO t_assignment (plan_id,student_id,teacher_id,enterprise_id,status) VALUES (?,?,?,?,1)`, [planId, sid, tId, entId]); a = { id: r.insertId }; }
    asgOf[sid] = { assignmentId: a.id, entId, teacherId: tId };
  }

  // —— 申请录用（30 条，覆盖全状态）——
  const appStatuses = [0, 0, 1, 1, 3, 5, 5, 5, 2, 4, 6];
  for (let i = 0; i < students.length; i++) {
    const sid = students[i];
    const pos = pick(positions.filter(p => true), i);
    const st = pick(appStatuses, i);
    const exists = await val('SELECT id FROM t_application WHERE student_id=? AND position_id=? AND is_deleted=0', [sid, pos.id]);
    if (!exists) {
      await one(`INSERT INTO t_application (student_id,position_id,enterprise_id,teacher_id,student_remark,teacher_opinion,admin_opinion,status,apply_time)
        VALUES (?,?,?,?,?,?,?,?, NOW() - INTERVAL ? DAY)`,
        [sid, pos.id, pos.entId, pick(teachers, i), '希望能到贵司实习，提升实践能力。',
          st >= 1 ? '该生表现良好，同意推荐。' : null, st >= 3 ? '符合实习要求，通过。' : null, st, i % 20]);
    }
  }

  // —— 三方协议（15 条，覆盖签署状态）——
  for (let i = 0; i < 15; i++) {
    const sid = assigned[i];
    const a = asgOf[sid];
    const st = pick([0, 1, 1, 2, 2, 2, 3], i); // 0待签 1签署中 2已生效 3作废
    const exists = await val('SELECT id FROM t_agreement WHERE student_id=? AND is_deleted=0', [sid]);
    if (!exists) {
      await one(`INSERT INTO t_agreement (student_id,enterprise_id,teacher_id,college_id,title,content,start_date,end_date,student_signed,student_sign_name,student_sign_time,teacher_signed,teacher_sign_time,school_signed,school_sign_time,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
        [sid, a.entId, a.teacherId, collegeId, '学生顶岗实习三方协议', '甲乙丙三方就实习事宜达成如下协议……', '2026-03-01', '2026-06-30',
          st >= 1 ? 1 : 0, st >= 1 ? '演示学生' : null, st >= 1 ? new Date() : null,
          st >= 2 ? 1 : 0, st >= 2 ? new Date() : null, st >= 2 ? 1 : 0, st >= 2 ? new Date() : null, st]);
    }
  }

  // —— 打卡（前 20 个在岗学生，每人近 10 天，范围内）——
  for (let i = 0; i < 20; i++) {
    const sid = assigned[i];
    const a = asgOf[sid];
    const c = entCoords[a.entId];
    const cnt = await val('SELECT COUNT(*) AS c FROM t_checkin WHERE student_id=?', [sid]);
    if (cnt.c >= 5) continue;
    for (let d = 1; d <= 10; d++) {
      await one(`INSERT INTO t_checkin (student_id,assignment_id,enterprise_id,latitude,longitude,distance,within_range,address,checkin_time,slot)
        VALUES (?,?,?,?,?,?,1,?, NOW() - INTERVAL ? DAY, 'day')`,
        [sid, a.assignmentId, a.entId, c.lat + 0.0001, c.lng + 0.0001, 15, '企业打卡点', d]);
    }
  }

  // —— 周报/月报（覆盖草稿/提交/通过/驳回）——
  for (let i = 0; i < 18; i++) {
    const sid = assigned[i];
    const a = asgOf[sid];
    const cnt = await val("SELECT COUNT(*) AS c FROM t_intern_log WHERE student_id=?", [sid]);
    if (cnt.c >= 3) continue;
    for (let w = 1; w <= 3; w++) {
      const st = pick([1, 2, 2, 3, 0], i + w);
      await one(`INSERT INTO t_intern_log (student_id,assignment_id,plan_id,teacher_id,type,title,content,status,teacher_comment,submit_time)
        VALUES (?,?,?,?,?,?,?,?,?, NOW() - INTERVAL ? DAY)`,
        [sid, a.assignmentId, planId, a.teacherId, 'weekly', `第${w}周周报`, '本周参与项目开发，完成既定任务，收获良多。', st,
          st === 2 ? '记录详实，继续保持。' : (st === 3 ? '内容过于简单，请补充。' : null), w * 7]);
    }
    // 一份月报
    await one(`INSERT INTO t_intern_log (student_id,assignment_id,plan_id,teacher_id,type,title,content,status,submit_time)
      VALUES (?,?,?,?, 'monthly','三月份月报','本月系统学习并参与了模块开发……',?, NOW() - INTERVAL 20 DAY)`,
      [sid, a.assignmentId, planId, a.teacherId, pick([1, 2], i)]);
  }

  // —— 请假（10 条，覆盖状态）——
  for (let i = 0; i < 10; i++) {
    const sid = assigned[i + 2];
    const a = asgOf[sid];
    const st = pick([1, 2, 2, 3], i); // 1提交 2通过 3驳回
    const exists = await val('SELECT id FROM t_leave WHERE student_id=? AND is_deleted=0', [sid]);
    if (!exists) {
      await one(`INSERT INTO t_leave (student_id,assignment_id,teacher_id,start_date,end_date,days,reason,status,reject_reason,submit_time)
        VALUES (?,?,?, CURDATE() + INTERVAL ? DAY, CURDATE() + INTERVAL ? DAY, ?,?,?,?, NOW())`,
        [sid, a.assignmentId, a.teacherId, i, i + 1, 2.0, pick(['家中有事', '身体不适需就医', '参加学校活动'], i), st,
          st === 3 ? '请假理由不充分' : null]);
    }
  }

  // —— 巡访记录（12 条）——
  for (let i = 0; i < 12; i++) {
    const sid = assigned[i];
    const a = asgOf[sid];
    const exists = await val('SELECT id FROM t_teacher_visit WHERE student_id=? AND teacher_id=? AND is_deleted=0', [sid, a.teacherId]);
    if (!exists) {
      await one(`INSERT INTO t_teacher_visit (teacher_id,student_id,assignment_id,visit_date,location,content,problems)
        VALUES (?,?,?, CURDATE() - INTERVAL ? DAY, ?, ?, ?)`,
        [a.teacherId, sid, a.assignmentId, i, '企业现场', '走访学生实习情况，沟通岗位适应与项目进展。', pick(['无异常', '需加强沟通能力', '建议轮岗学习'], i)]);
    }
  }

  // —— 投诉/安全上报（6 条，覆盖紧急度/状态）——
  for (let i = 0; i < 6; i++) {
    const sid = assigned[i];
    const st = pick([0, 1, 2, 3], i);
    const title = pick(['岗位与专业不符', '加班时长偏高', '住宿安全隐患', '工资发放延迟', '导师指导不足', '工作环境反馈'], i);
    const exists = await val('SELECT id FROM t_complaint WHERE title=? AND student_id=? AND is_deleted=0', [title, sid]);
    if (!exists) {
      await one(`INSERT INTO t_complaint (category,title,content,student_id,reporter_id,reporter_role,contact_phone,college_id,urgency,status,handler_id,handle_remark,handle_time)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`,
        [pick(['投诉', '安全', '异常'], i), title, '请学校协助处理该问题，谢谢。', sid, sid, 4, '13800000099', collegeId,
          pick([1, 2, 3], i), st, st >= 2 ? baseTeacherId : null, st >= 2 ? '已联系企业核实并妥善处理。' : null, st >= 2 ? new Date() : null]);
    }
  }

  // —— 保险（26 人投保，留 4 人未投保触发"保险预警"，2 人即将到期）——
  for (let i = 0; i < 26; i++) {
    const sid = assigned[i] || students[i];
    if (!sid) continue;
    const exists = await val('SELECT id FROM t_insurance WHERE student_id=? AND is_deleted=0', [sid]);
    if (!exists) {
      const soon = i < 2; // 前 2 人即将到期
      await one(`INSERT INTO t_insurance (student_id,insurance_type,policy_no,company,start_date,end_date,college_id,remark)
        VALUES (?,?,?,?, '2026-03-01', ?, ?, ?)`,
        [sid, '实习责任险', 'PICC' + String(100000 + i), '中国人保',
          '2026-06-30', collegeId, soon ? '即将到期' : null]);
    }
  }
  // 修正"即将到期"日期（上面占位字符串无效，单独 UPDATE 两条）
  await pool.query(`UPDATE t_insurance SET end_date = CURDATE() + INTERVAL 5 DAY WHERE remark='即将到期'`);

  // —— 企业评价（12 条已提交）——
  for (let i = 0; i < 12; i++) {
    const sid = assigned[i];
    const a = asgOf[sid];
    const exists = await val('SELECT id FROM t_enterprise_eval WHERE student_id=? AND is_deleted=0', [sid]);
    if (!exists) {
      await one(`INSERT INTO t_enterprise_eval (student_id,enterprise_id,assignment_id,college_id,token,mentor_name,mentor_title,score_overall,score_attitude,score_skill,score_discipline,comment,status,submit_time)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1, NOW())`,
        [sid, a.entId, a.assignmentId, collegeId, 'tok_eval_' + sid, '企业导师' + (i + 1), '项目经理',
          pick([85, 90, 78, 92, 88], i), pick([4, 5, 4, 5], i), pick([4, 4, 5, 3], i), pick([5, 4, 5, 4], i),
          '该生工作认真，学习能力强，能较好完成交办任务。', ]);
    }
  }

  // —— 企业满意度（8 条）——
  for (let i = 0; i < 8; i++) {
    const sid = assigned[i];
    const a = asgOf[sid];
    const exists = await val('SELECT id FROM t_satisfaction WHERE student_id=? AND is_deleted=0', [sid]);
    if (!exists) {
      await one(`INSERT INTO t_satisfaction (enterprise_id,student_id,college_id,score,content,created_by)
        VALUES (?,?,?,?,?,?)`,
        [a.entId, sid, collegeId, pick([4, 5, 5, 3], i), '对学校输送的实习生整体满意。', baseTeacherId]);
    }
  }

  // —— 毕设：选题 + 指导记录 + 成果/查重 + 成绩（覆盖更多学生）——
  const gdTitles = ['基于Vue的校企协同平台', '实习数据可视化分析系统', '物联网考勤终端设计', '微服务实习管理后端',
    '智能岗位推荐算法研究', '实习风险预警模型', '移动端实习打卡App', '企业评价数据挖掘'];
  for (let i = 0; i < 20; i++) {
    const sid = students[i];
    const tId = pick(teachers, i);
    const t = await val('SELECT id FROM t_gd_topic WHERE student_id=? AND is_deleted=0', [sid]);
    let topicId = t && t.id;
    if (!topicId) {
      const cls = await val('SELECT major_id,class_id FROM t_user WHERE id=?', [sid]);
      const r = await one(`INSERT INTO t_gd_topic (title,student_id,teacher_id,college_id,major_id,class_id,status) VALUES (?,?,?,?,?,?,1)`,
        [pick(gdTitles, i) + (i >= 8 ? ' ' + (i + 1) : ''), sid, tId, collegeId, cls.major_id, cls.class_id]);
      topicId = r.insertId;
    }
    // 指导记录
    if (i < 15) {
      const g = await val('SELECT id FROM t_gd_guidance WHERE student_id=? AND is_deleted=0', [sid]);
      if (!g) await one(`INSERT INTO t_gd_guidance (topic_id,student_id,teacher_id,college_id,title,content,guidance_date)
        VALUES (?,?,?,?,?,?, CURDATE() - INTERVAL ? DAY)`,
        [topicId, sid, tId, collegeId, '第' + ((i % 3) + 1) + '次指导', '讨论论文结构与实现方案，布置下阶段任务。', i]);
    }
    // 成果 + 查重
    if (i < 12) {
      const ach = await val('SELECT id FROM t_gd_achievement WHERE student_id=? AND is_deleted=0', [sid]);
      if (!ach) await one(`INSERT INTO t_gd_achievement (student_id,teacher_id,title,link,status,submit_time) VALUES (?,?,?,?,?, NOW())`,
        [sid, tId, '毕业设计论文终稿', '/uploads/demo-paper.pdf', pick([1, 2], i)]);
    }
    // 成绩
    if (i < 12) {
      await pool.query(`INSERT INTO t_gd_grade (student_id,teacher_id,class_id,topic_title,review_score,defense_score,total_score)
        SELECT ?,?,class_id,?,?,?,? FROM t_user WHERE id=? AND NOT EXISTS (SELECT 1 FROM t_gd_grade WHERE student_id=?)`,
        [sid, tId, pick(gdTitles, i), pick([82, 88, 75, 90], i), pick([85, 90, 80, 92], i), pick([84, 89, 78, 91], i), sid, sid]);
    }
  }

  // —— 就业去向（15 条）——
  for (let i = 0; i < 15; i++) {
    const sid = students[i];
    const exists = await val('SELECT id FROM t_employment_destination WHERE student_id=? AND is_deleted=0', [sid]);
    if (!exists) {
      const dt = pick(['employed', 'employed', 'employed', 'further', 'startup', 'pending'], i);
      await one(`INSERT INTO t_employment_destination (student_id,dest_type,company_name,position_title,city,salary_range,remark)
        VALUES (?,?,?,?,?,?,?)`,
        [sid, dt, dt === 'employed' ? pick(entDefs, i)[0] : null, dt === 'employed' ? '软件开发' : null,
          '长沙', dt === 'employed' ? pick(['5-7k', '6-8k', '7-9k'], i) : null, dt === 'further' ? '专升本' : null]);
    }
  }

  // —— 家长知情书 + 实习鉴定表（覆盖状态）——
  for (let i = 0; i < 10; i++) {
    const sid = assigned[i];
    const a = asgOf[sid];
    const pc = await val('SELECT id FROM t_parent_consent WHERE student_id=? AND is_deleted=0', [sid]);
    if (!pc) await one(`INSERT INTO t_parent_consent (student_id,assignment_id,file_url,status,reviewer_id,review_time)
      VALUES (?,?,?,?,?,?)`, [sid, a.assignmentId, '/uploads/demo-consent.pdf', pick([0, 1, 1, 2], i),
      i % 4 >= 1 ? baseTeacherId : null, i % 4 >= 1 ? new Date() : null]);
    const ap = await val('SELECT id FROM t_intern_appraisal WHERE student_id=? AND is_deleted=0', [sid]);
    if (!ap) await one(`INSERT INTO t_intern_appraisal (student_id,assignment_id,file_url,enterprise_comment,status)
      VALUES (?,?,?,?,?)`, [sid, a.assignmentId, '/uploads/demo-appraisal.pdf', '实习表现优秀，准予通过。', pick([0, 1, 1, 2], i)]);
  }

  console.log('   批量：3专业 / 6班 / 30学生 / 3教师 / 10企业 / 20岗位 + 申请·协议·打卡·周月报·请假·巡访·投诉·保险·企业评价·满意度·毕设全套');
}

async function run() {
  try {
    console.log('== 灌入演示数据 ==');
    ensureDemoFiles();

    // 学院 / 专业 / 班级
    await pool.query(`INSERT INTO t_college (name, code, description) VALUES ('演示学院','DEMO','演示用学院')
      ON DUPLICATE KEY UPDATE name=VALUES(name)`);
    const collegeId = (await val("SELECT id FROM t_college WHERE code='DEMO'")).id;

    await pool.query(`INSERT INTO t_major (college_id, name, code) VALUES (?,'软件技术','DEMO_SE')
      ON DUPLICATE KEY UPDATE name=VALUES(name)`, [collegeId]);
    const majorId = (await val("SELECT id FROM t_major WHERE code='DEMO_SE'")).id;

    let cls = await val("SELECT id FROM t_class WHERE name='演示2024班' AND college_id=?", [collegeId]);
    if (!cls) { const r = await one(`INSERT INTO t_class (college_id,major_id,name,grade) VALUES (?,?,?,2024)`, [collegeId, majorId, '演示2024班']); cls = { id: r.insertId }; }
    const classId = cls.id;

    // 企业（含坐标 + 打卡半径）
    let ent = await val("SELECT id FROM t_enterprise WHERE name='演示科技有限公司' AND is_deleted=0");
    if (!ent) { const r = await one(`INSERT INTO t_enterprise (name,short_name,industry,address,contact_name,contact_phone,latitude,longitude,checkin_radius)
      VALUES ('演示科技有限公司','演示科技','软件','长沙市岳麓区','张经理','0731-88888888',28.200000,112.900000,300)`); ent = { id: r.insertId }; }
    const enterpriseId = ent.id;

    // 用户
    const teacherId = await ensureUser('demo_teacher', '周建国（样例教师）', 3, { college_id: collegeId, eeid: 'DT001', phone: '13800000001' });
    const stu1 = await ensureUser('demo_stu1', '陈思远（样例学生）', 4, { college_id: collegeId, major_id: majorId, class_id: classId, eeid: 'DS001', phone: '13800000002' });
    const stu2 = await ensureUser('demo_stu2', '李若溪（样例学生）', 4, { college_id: collegeId, major_id: majorId, class_id: classId, eeid: 'DS002', phone: '13800000003' });
    await ensureUser('demo_admin', '教务管理员（样例）', 1, {});

    // 实习计划（开启状态）
    let plan = await val("SELECT id FROM t_intern_plan WHERE title='演示实习计划' AND is_deleted=0");
    if (!plan) { const r = await one(`INSERT INTO t_intern_plan (college_id,major_id,title,start_date,end_date,purpose,content,checkin_count,weekly_count,monthly_count,status,created_by)
      VALUES (?,?,?,'2026-03-01','2026-06-30','提升工程实践能力','参与真实项目开发',20,8,2,3,?)`, [collegeId, majorId, '演示实习计划', teacherId]); plan = { id: r.insertId }; }
    const planId = plan.id;

    // 分配（两个学生）
    for (const sid of [stu1, stu2]) {
      const exists = await val('SELECT id FROM t_assignment WHERE student_id=? AND plan_id=? AND is_deleted=0', [sid, planId]);
      if (!exists) await one(`INSERT INTO t_assignment (plan_id,student_id,teacher_id,enterprise_id,status) VALUES (?,?,?,?,1)`, [planId, sid, teacherId, enterpriseId]);
    }

    // 打卡（学生甲若今天未打则补一条历史打卡）
    const ckCnt = await val('SELECT COUNT(*) AS c FROM t_checkin WHERE student_id=?', [stu1]);
    if (ckCnt.c === 0) {
      await one(`INSERT INTO t_checkin (student_id,enterprise_id,latitude,longitude,distance,within_range,address,checkin_time)
        VALUES (?,?,28.200010,112.900010,2,1,'演示企业前台', NOW() - INTERVAL 1 DAY)`, [stu1, enterpriseId]);
    }

    // 周报（学生甲，已提交）
    const logCnt = await val("SELECT COUNT(*) AS c FROM t_intern_log WHERE student_id=? AND type='weekly'", [stu1]);
    if (logCnt.c === 0) {
      await one(`INSERT INTO t_intern_log (student_id,plan_id,teacher_id,type,title,content,status,submit_time)
        VALUES (?,?,?, 'weekly','第一周周报','本周完成环境搭建与需求分析。',1, NOW())`, [stu1, planId, teacherId]);
    }

    // 毕设：公示 / 任务 / 选题 / 成果 / 成绩
    await pool.query(`INSERT INTO t_announcement (title,category,content,college_id,publisher_id,status,publish_time)
      SELECT '毕业设计工作启动通知','工作布置','请各位同学按时完成选题。',?,?,1,NOW()
      FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM t_announcement WHERE title='毕业设计工作启动通知' AND is_deleted=0)`, [collegeId, teacherId]);

    const taskExists = await val("SELECT id FROM t_gd_task WHERE name='选题与开题' AND is_deleted=0");
    if (!taskExists) await one(`INSERT INTO t_gd_task (name,scope,college_id,require_time,status) VALUES ('选题与开题','全院',?, '2026-03-15',1)`, [collegeId]);

    for (const [sid, title] of [[stu1, '基于Node.js的实习管理系统设计'], [stu2, '校企协同育人平台数据分析']]) {
      const t = await val('SELECT id FROM t_gd_topic WHERE student_id=? AND is_deleted=0', [sid]);
      if (!t) await one(`INSERT INTO t_gd_topic (title,student_id,teacher_id,college_id,major_id,class_id,status) VALUES (?,?,?,?,?,?,1)`,
        [title, sid, teacherId, collegeId, majorId, classId]);
    }

    const achExists = await val('SELECT id FROM t_gd_achievement WHERE student_id=? AND is_deleted=0', [stu1]);
    if (!achExists) await one(`INSERT INTO t_gd_achievement (student_id,teacher_id,title,link,status,submit_time) VALUES (?,?,?,?,1,NOW())`,
      [stu1, teacherId, '毕业设计成果-演示', '/uploads/demo-paper.pdf']);

    await pool.query(`INSERT INTO t_gd_grade (student_id,teacher_id,class_id,topic_title,review_score,defense_score,total_score)
      VALUES (?,?,?,?,86,90,88) ON DUPLICATE KEY UPDATE total_score=VALUES(total_score)`,
      [stu1, teacherId, classId, '基于Node.js的实习管理系统设计']);

    // —— 丰满批量数据（让每个页面/筛选 tab 都有数据）——
    await seedBulk({
      collegeId, baseMajorId: majorId, baseClassId: classId, baseTeacherId: teacherId,
      baseEntId: enterpriseId, planId, stu1, stu2,
    });

    console.log('✅ 演示数据就绪：');
    console.log('   学院ID=%d 专业ID=%d 班级ID=%d 企业ID=%d 计划ID=%d', collegeId, majorId, classId, enterpriseId, planId);
    console.log('   账号(密码 demo1234)：demo_admin / demo_teacher / demo_stu1 / demo_stu2 / demo_s001~demo_s028');
  } catch (err) {
    console.error('❌ 灌入失败：', err.message);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
}

run();
