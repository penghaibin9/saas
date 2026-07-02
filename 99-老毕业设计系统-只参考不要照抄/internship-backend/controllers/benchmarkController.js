const XLSX = require('xlsx');
const {
  benchmarkModel, gdTopicModel, gdAchievementModel, gdGradeModel,
  assignmentModel, assignmentChangeModel, userModel, notificationModel, auditLogModel
} = require('../models');
const { success, error } = require('../utils/response');

// 敏感数据导出审计（合规：记录谁在何时导出了多少条 PII）
function auditExport(req, action, targetType, count) {
  try {
    const u = req.user || {};
    auditLogModel.create({
      user_id: u.id || null, username: u.username || null, real_name: u.realName || null,
      role: u.role ?? null, college_id: u.collegeId ?? null,
      ip: (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || req.ip || null,
      method: req.method, path: (req.originalUrl || '').split('?')[0].slice(0, 255),
      action, target_type: targetType, target_id: null,
      status_code: 200, success: 1, detail: JSON.stringify({ count })
    }).catch(e => console.warn('导出审计写入失败:', e.message));
  } catch (e) { console.warn('导出审计异常:', e.message); }
}
const { clampPagination } = require('../utils/validate');
const { createUploader, keyToUrl } = require('../utils/upload');
const { notify, notifyGroup } = require('../utils/notify');

const upload = createUploader({ prefix: 'bench' });

function canAccessStudentRecord(user, row) {
  if (!user || !row) return false;
  if (user.role === 1) return true;
  if (user.role === 2) return Number(row.student_college_id) === Number(user.collegeId);
  if (user.role === 3) {
    const teacherId = row.teacher_id ?? row.assignment_teacher_id;
    return Number(teacherId) === Number(user.id);
  }
  if (user.role === 4) return Number(row.student_id) === Number(user.id);
  return false;
}

const benchmarkController = {
  upload: upload.single('file'),

  /* ===== 任务书 ===== */
  async listTaskBooks(req, res) {
    try {
      const u = req.user;
      const filter = {};
      if (u.role === 4) filter.studentId = u.id;
      if (u.role === 3) filter.teacherId = u.id;
      if (u.role === 2) filter.collegeId = u.collegeId;
      const result = await benchmarkModel.listTaskBooks(filter, clampPagination(req.query));
      return success(res, result);
    } catch (e) { return error(res, e.message, 500); }
  },
  async upsertTaskBook(req, res) {
    try {
      if (req.user.role !== 3 && req.user.role > 2) return error(res, '权限不足', 403);
      const { student_id, title, content } = req.body;
      if (!student_id || !title) return error(res, '请指定学生和标题', 400);
      const topics = await gdTopicModel.findAll({ studentId: Number(student_id) }, { page: 1, pageSize: 1 });
      const topic = topics.list[0];
      if (!topic) return error(res, '该学生尚未分配毕业设计课题与指导教师', 400);
      if (req.user.role === 3 && Number(topic.teacher_id) !== Number(req.user.id)) {
        return error(res, '只能为本人指导的学生下达任务书', 403);
      }
      // file_url 只能来自服务端上传流程，禁止客户端提交任意 URL/协议。
      const file_url = req.file ? keyToUrl(req.file.filename) : undefined;
      const id = await benchmarkModel.upsertTaskBook({
        student_id: Number(student_id), topic_id: topic?.id, teacher_id: req.user.id,
        title, content, file_url
      });
      await notify(Number(student_id), '毕设任务书已下达', `请登录确认任务书：${title}`, 'info');
      return success(res, { id }, '任务书已保存', 201);
    } catch (e) { return error(res, e.message, 500); }
  },
  async confirmTaskBook(req, res) {
    try {
      await benchmarkModel.confirmTaskBook(req.user.id);
      return success(res, null, '已确认任务书');
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 家长知情 ===== */
  async listParentConsents(req, res) {
    try {
      const filter = { status: req.query.status !== undefined ? Number(req.query.status) : undefined };
      if (req.user.role === 4) filter.studentId = req.user.id;
      if (req.user.role === 3) filter.teacherId = req.user.id;
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      const result = await benchmarkModel.listSimple('parent', filter, null, clampPagination(req.query));
      return success(res, result);
    } catch (e) { return error(res, e.message, 500); }
  },
  async createParentConsent(req, res) {
    try {
      const file_url = req.file ? keyToUrl(req.file.filename) : null;
      if (!file_url) return error(res, '请上传家长知情同意书', 400);
      const a = await assignmentModel.findActiveByStudent(req.user.id);
      const id = await benchmarkModel.createParentConsent({
        student_id: req.user.id, assignment_id: a?.id, file_url
      });
      return success(res, { id }, '已提交，等待审核', 201);
    } catch (e) { return error(res, e.message, 500); }
  },
  async reviewParentConsent(req, res) {
    try {
      const id = Number(req.params.id);
      const record = await benchmarkModel.getParentConsent(id);
      if (!record) return error(res, '家长知情书不存在', 404);
      if (!canAccessStudentRecord(req.user, record)) return error(res, '无权审核该学生材料', 403);
      const { status, reject_reason } = req.body;
      await benchmarkModel.reviewParentConsent(id, Number(status), req.user.id, reject_reason);
      return success(res, null, '已审核');
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 实习鉴定 ===== */
  async listAppraisals(req, res) {
    try {
      const filter = {};
      if (req.user.role === 4) filter.studentId = req.user.id;
      if (req.user.role === 3) filter.teacherId = req.user.id;
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      const result = await benchmarkModel.listSimple('appraisal', filter, null, clampPagination(req.query));
      return success(res, result);
    } catch (e) { return error(res, e.message, 500); }
  },
  async getAppraisal(req, res) {
    try {
      const row = await benchmarkModel.getAppraisal(req.params.id);
      if (!row) return error(res, '鉴定表不存在', 404);
      if (!canAccessStudentRecord(req.user, row)) return error(res, '无权查看该学生鉴定表', 403);
      return success(res, row);
    } catch (e) { return error(res, e.message, 500); }
  },
  async getTaskBook(req, res) {
    try {
      const row = await benchmarkModel.getTaskBook(req.params.id);
      if (!row) return error(res, '任务书不存在', 404);
      if (!canAccessStudentRecord(req.user, row)) return error(res, '无权查看该学生任务书', 403);
      return success(res, row);
    } catch (e) { return error(res, e.message, 500); }
  },
  // 学生下拉选项：供教师/管理员在巡访、指导记录等场景选择学生
  async studentOptions(req, res) {
    try {
      const filter = {};
      if (req.user.role !== 1) filter.collegeId = req.user.collegeId; // 院校管理员看全部，其余按学院
      const result = await benchmarkModel.studentOptions(filter);
      return success(res, result);
    } catch (e) { return error(res, e.message, 500); }
  },
  async upsertAppraisal(req, res) {
    try {
      const file_url = req.file ? keyToUrl(req.file.filename) : null;
      if (!file_url) return error(res, '请上传鉴定表扫描件', 400);
      const a = await assignmentModel.findActiveByStudent(req.user.id);
      const id = await benchmarkModel.upsertAppraisal({
        student_id: req.user.id, assignment_id: a?.id,
        file_url, enterprise_comment: req.body.enterprise_comment
      });
      return success(res, { id }, '鉴定表已提交', 201);
    } catch (e) { return error(res, e.message, 500); }
  },
  async reviewAppraisal(req, res) {
    try {
      if (req.user.role > 3) return error(res, '权限不足', 403);
      const id = Number(req.params.id);
      const record = await benchmarkModel.getAppraisal(id);
      if (!record) return error(res, '鉴定表不存在', 404);
      if (!canAccessStudentRecord(req.user, record)) return error(res, '无权审核该学生鉴定表', 403);
      await benchmarkModel.reviewAppraisal(id, Number(req.body.status), req.body.reject_reason);
      const [[row]] = await require('../config/db').query('SELECT student_id FROM t_intern_appraisal WHERE id=?', [id]);
      if (row && Number(req.body.status) === 1) {
        await notify(row.student_id, '实习鉴定表已通过', '你的实习鉴定表已审核通过', 'info');
      }
      return success(res, null, '已审核');
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 巡访 ===== */
  async listVisits(req, res) {
    try {
      const filter = {};
      if (req.user.role === 3) filter.teacherId = req.user.id;
      if (req.user.role === 4) filter.studentId = req.user.id;
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      return success(res, await benchmarkModel.listVisits(filter, clampPagination(req.query)));
    } catch (e) { return error(res, e.message, 500); }
  },
  async createVisit(req, res) {
    try {
      if (req.user.role !== 3) return error(res, '仅指导教师可登记巡访', 403);
      const { student_id, visit_date, location, content, problems } = req.body;
      if (!student_id || !visit_date) return error(res, '请填写学生和巡访日期', 400);
      const a = await assignmentModel.findActiveByStudent(Number(student_id));
      const photo_url = req.file ? keyToUrl(req.file.filename) : null;
      const id = await benchmarkModel.createVisit({
        teacher_id: req.user.id, student_id: Number(student_id), assignment_id: a?.id,
        visit_date, location, content, problems, photo_url
      });
      await notify(Number(student_id), '教师巡访记录', `指导老师已登记 ${visit_date} 巡访记录`, 'info');
      return success(res, { id }, '巡访已登记', 201);
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 就业去向 ===== */
  async getEmployment(req, res) {
    try {
      const sid = req.user.role === 4 ? req.user.id : Number(req.query.student_id);
      if (!sid) return error(res, '请指定学生', 400);
      return success(res, await benchmarkModel.getEmployment(sid));
    } catch (e) { return error(res, e.message, 500); }
  },
  async employmentStats(req, res) {
    try {
      if (req.user.role > 3) return error(res, '权限不足', 403);
      const collegeId = req.user.role === 2 ? req.user.collegeId : (req.query.college_id ? Number(req.query.college_id) : null);
      return success(res, await benchmarkModel.employmentStats(collegeId));
    } catch (e) { return error(res, e.message, 500); }
  },
  async upsertEmployment(req, res) {
    try {
      if (req.user.role !== 4) return error(res, '仅学生可填报', 403);
      const { dest_type, company_name, position_title, city, salary_range, remark } = req.body;
      if (!dest_type) return error(res, '请选择去向类型', 400);
      const id = await benchmarkModel.upsertEmployment({
        student_id: req.user.id, dest_type, company_name, position_title, city, salary_range, remark
      });
      return success(res, { id }, '去向已保存', 201);
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 免实习/其他去向 ===== */
  async listAlternatives(req, res) {
    try {
      const filter = { status: req.query.status !== undefined ? Number(req.query.status) : undefined };
      if (req.user.role === 4) filter.studentId = req.user.id;
      if (req.user.role === 3) filter.teacherId = req.user.id;
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      return success(res, await benchmarkModel.listSimple('alternative', filter, null, clampPagination(req.query)));
    } catch (e) { return error(res, e.message, 500); }
  },
  async createAlternative(req, res) {
    try {
      const { alt_type, reason } = req.body;
      if (!alt_type || !reason) return error(res, '请填写类型和原因', 400);
      const file_url = req.file ? keyToUrl(req.file.filename) : null;
      const id = await benchmarkModel.createAlternative({ student_id: req.user.id, alt_type, reason, file_url });
      return success(res, { id }, '申请已提交', 201);
    } catch (e) { return error(res, e.message, 500); }
  },
  async reviewAlternative(req, res) {
    try {
      if (req.user.role > 2) return error(res, '权限不足', 403);
      const id = Number(req.params.id);
      const record = await benchmarkModel.getAlternative(id);
      if (!record) return error(res, '免实习/其他去向申请不存在', 404);
      if (!canAccessStudentRecord(req.user, record)) return error(res, '无权审核其他学院学生申请', 403);
      await benchmarkModel.reviewAlternative(id, Number(req.body.status), req.user.id, req.body.remark);
      return success(res, null, '已审核');
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 结束实习 ===== */
  async completeIntern(req, res) {
    try {
      const a = await assignmentModel.findActiveByStudent(req.user.id);
      if (!a) return error(res, '无有效实习分配', 400);
      const pending = await assignmentChangeModel.findPendingByStudent(req.user.id);
      if (pending) return error(res, '已有进行中的变更申请', 400);
      const id = await assignmentChangeModel.create({
        assignment_id: a.id, student_id: req.user.id, change_type: 'complete',
        old_enterprise_id: a.enterprise_id, reason: req.body.reason || '实习期满，申请结束',
        applicant_id: req.user.id, applicant_role: req.user.role
      });
      await assignmentChangeModel.updateStatus(id, 2, { teacher_opinion: '实习期满' });
      const pool = require('../config/db');
      await pool.query('UPDATE t_assignment SET status=0, update_time=NOW() WHERE id=?', [a.id]);
      await notify(a.teacher_id, '学生结束实习', `${req.user.realName || ''} 实习期满已结束`, 'info');
      return success(res, { id }, '实习已结束', 201);
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 选题互选 ===== */
  async listTopicPool(req, res) {
    try {
      const filter = {};
      if (req.user.role === 3) filter.teacherId = req.user.id;
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      return success(res, { list: await benchmarkModel.listTopicPool(filter) });
    } catch (e) { return error(res, e.message, 500); }
  },
  async createTopicPool(req, res) {
    try {
      if (req.user.role !== 3) return error(res, '仅教师可发布课题', 403);
      const id = await benchmarkModel.createTopicPool({ ...req.body, teacher_id: req.user.id, college_id: req.user.collegeId });
      return success(res, { id }, '课题已发布', 201);
    } catch (e) { return error(res, e.message, 500); }
  },
  async listRounds(req, res) {
    try {
      const collegeId = req.user.role === 2 ? req.user.collegeId : null;
      return success(res, { list: await benchmarkModel.listRounds(collegeId) });
    } catch (e) { return error(res, e.message, 500); }
  },
  async createRound(req, res) {
    try {
      if (req.user.role > 2) return error(res, '权限不足', 403);
      const { name, max_choices, start_time, end_time } = req.body;
      if (!name || !String(name).trim()) return error(res, '请填写轮次名称', 400);
      const id = await benchmarkModel.createRound({
        name: String(name).trim(),
        max_choices: max_choices || 3,
        start_time: start_time || null,
        end_time: end_time || null,
        college_id: req.user.collegeId || null
      });
      return success(res, { id }, '轮次已创建', 201);
    } catch (e) { return error(res, e.message, 500); }
  },
  async setRoundStatus(req, res) {
    try {
      if (req.user.role > 2) return error(res, '权限不足', 403);
      await benchmarkModel.setRoundStatus(Number(req.params.id), Number(req.body.status));
      if (Number(req.body.status) === 2 && req.body.match) {
        const n = await benchmarkModel.matchRound(Number(req.params.id));
        return success(res, { matched: n }, '轮次已结束并完成匹配');
      }
      return success(res, null, '轮次状态已更新');
    } catch (e) { return error(res, e.message, 500); }
  },
  async submitChoices(req, res) {
    try {
      const { round_id, choices } = req.body;
      if (!round_id || !choices?.length) return error(res, '请选择志愿', 400);
      await benchmarkModel.submitChoices(Number(round_id), req.user.id, choices);
      return success(res, null, '志愿已提交');
    } catch (e) { return error(res, e.message, 500); }
  },
  async listChoices(req, res) {
    try {
      const filter = req.user.role === 4 ? { studentId: req.user.id } : {};
      return success(res, { list: await benchmarkModel.listChoices(Number(req.params.roundId), filter) });
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 实习成绩 ===== */
  async getScoreConfig(req, res) {
    try {
      const collegeId = req.user.role === 2 ? req.user.collegeId : (req.query.college_id ? Number(req.query.college_id) : null);
      return success(res, await benchmarkModel.getScoreConfig(collegeId));
    } catch (e) { return error(res, e.message, 500); }
  },
  async saveScoreConfig(req, res) {
    try {
      if (req.user.role > 2) return error(res, '权限不足', 403);
      const b = req.body;
      const row = {
        college_id: req.user.collegeId || null,
        checkin_weight: b.checkin_weight ?? 20,
        weekly_weight: b.weekly_weight ?? b.log_weight ?? 20,
        monthly_weight: b.monthly_weight ?? b.report_weight ?? 10,
        enterprise_weight: b.enterprise_weight ?? b.eval_weight ?? 30,
        school_weight: b.school_weight ?? 20,
        pass_line: b.pass_line ?? 60
      };
      const id = await benchmarkModel.saveScoreConfig(row);
      return success(res, { id }, '配置已保存');
    } catch (e) { return error(res, e.message, 500); }
  },
  async computeInternScore(req, res) {
    try {
      const sid = req.query.student_id ? Number(req.query.student_id) : req.user.id;
      if (req.user.role === 4 && sid !== req.user.id) return error(res, '权限不足', 403);
      const schoolScore = req.body && (req.body.school_score ?? req.body.schoolScore);
      const s = await benchmarkModel.computeInternScore(sid, { schoolScore, scoredBy: req.user.id });
      if (!s) return error(res, '无有效实习分配，无法核算', 400);
      const missing = s._missing || [];
      const labelMap = { enterprise: '企业评价', school: '校内评分', checkin: '打卡', log: '日志' };
      const msg = missing.length
        ? `已核算（缺：${missing.map(k => labelMap[k] || k).join('、')}，当前为按已到位分项折算的临时分）`
        : '成绩已核算';
      return success(res, { ...s, missing }, msg);
    } catch (e) { return error(res, e.message, 500); }
  },
  async getInternScore(req, res) {
    try {
      const sid = req.user.role === 4 ? req.user.id : Number(req.query.student_id);
      const allow = req.user.role <= 3;
      const s = await benchmarkModel.getInternScore(sid, allow);
      return success(res, s);
    } catch (e) { return error(res, e.message, 500); }
  },
  async publishInternScore(req, res) {
    try {
      if (req.user.role > 3) return error(res, '权限不足', 403);
      await benchmarkModel.publishInternScore(Number(req.params.studentId));
      await notify(Number(req.params.studentId), '实习成绩已公布', '你的岗位实习综合考评成绩已发布', 'info');
      return success(res, null, '已发布');
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 催办 ===== */
  async urgeList(req, res) {
    try {
      if (req.user.role > 3) return error(res, '权限不足', 403);
      const collegeId = req.user.role === 2 ? req.user.collegeId : null;
      return success(res, await benchmarkModel.urgeList(collegeId));
    } catch (e) { return error(res, e.message, 500); }
  },
  async urgeNotify(req, res) {
    try {
      if (req.user.role > 3) return error(res, '权限不足', 403);
      const { student_ids, title, content } = req.body;
      if (!student_ids?.length) return error(res, '请选择学生', 400);
      for (const id of student_ids) {
        await notify(Number(id), title || '实习催办提醒', content || '请及时完成实习要求事项', 'warning');
      }
      // 向教师/管理群广播催办汇总（企业微信/钉钉,未配置则静默跳过）
      notifyGroup('实习催办已发送', `${req.user.realName || '管理员'} 向 ${student_ids.length} 名学生发送了「${title || '实习催办提醒'}」`);
      return success(res, { count: student_ids.length }, '已发送提醒');
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 补签 ===== */
  async makeupCheckin(req, res) {
    try {
      const { latitude, longitude, address, reason } = req.body;
      const a = await assignmentModel.findActiveByStudent(req.user.id);
      if (!a) return error(res, '无有效实习', 400);
      const pool = require('../config/db');
      const photo_url = req.file ? keyToUrl(req.file.filename) : null;
      const makeupReason = reason || '补签申请';
      const [r] = await pool.query(
        `INSERT INTO t_checkin (student_id, assignment_id, enterprise_id, latitude, longitude, address, photo_url, remark, is_makeup, makeup_status, makeup_reason, within_range, checkin_time)
         VALUES (?,?,?,?,?,?,?,?,1,0,?,1,NOW())`,
        [req.user.id, a.id, a.enterprise_id, latitude ?? null, longitude ?? null, address ?? null, photo_url, makeupReason, makeupReason]);
      return success(res, { id: r.insertId }, '补签申请已提交', 201);
    } catch (e) { return error(res, e.message, 500); }
  },
  async reviewMakeup(req, res) {
    try {
      if (req.user.role !== 3) return error(res, '仅教师可审批补签', 403);
      const pool = require('../config/db');
      const status = Number(req.body.status);
      await pool.query('UPDATE t_checkin SET makeup_status=? WHERE id=? AND is_makeup=1', [status, Number(req.params.id)]);
      if (status === 1) await benchmarkModel.addCheckinPoints(Number(req.body.student_id));
      return success(res, null, '已处理');
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 查重 ===== */
  async runPlagiarism(req, res) {
    try {
      const achievementId = Number(req.params.achievementId);
      const ach = await gdAchievementModel.findById(achievementId);
      if (!ach) return error(res, '成果不存在', 404);
      if (req.user.role === 4 && ach.student_id !== req.user.id) return error(res, '权限不足', 403);
      const fileUrl = ach.file_url || ach.link || null;
      const r = await benchmarkModel.runPlagiarism(ach.student_id, achievementId, fileUrl);
      if (r.status === 2) {
        return error(res, '查重服务暂不可用：' + (r._error || '请稍后重试或联系管理员'), 502);
      }
      const isDemo = r.is_demo === 1 || r.is_demo === true;
      return success(res, {
        ...r,
        similarity_rate: r.similarity,
        similarity: r.similarity,
        is_demo: isDemo ? 1 : 0
      }, isDemo ? '检测完成（演示数据，未对接查重服务）' : '检测完成');
    } catch (e) { return error(res, e.message, 500); }
  },
  async getPlagiarism(req, res) {
    try {
      const r = await benchmarkModel.getPlagiarism(Number(req.params.achievementId));
      if (r) r.similarity_rate = r.similarity;
      return success(res, r);
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 学信网导出 ===== */
  async chsiExport(req, res) {
    try {
      if (req.user.role > 2) return error(res, '权限不足', 403);
      const collegeId = req.user.role === 2 ? req.user.collegeId : null;
      const rows = await benchmarkModel.chsiData(collegeId);
      const data = benchmarkModel.chsiExportRows(rows);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(data.length ? data : [{ '说明': '暂无数据' }]), '实习监管数据');
      const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
      auditExport(req, '导出学信网实习监管数据', 'chsi-export', rows.length);
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename=chsi-intern-export.xlsx');
      return res.send(buf);
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 档案导出 ===== */
  async internHandbook(req, res) {
    try {
      const sid = req.user.role === 4 ? req.user.id : Number(req.query.student_id);
      const pool = require('../config/db');
      const [[stu]] = await pool.query(
        `SELECT s.real_name, s.eeid, e.name AS enterprise_name, t.real_name AS teacher_name,
                (SELECT COUNT(*) FROM t_checkin WHERE student_id=s.id) AS checkins,
                (SELECT COUNT(*) FROM t_intern_log WHERE student_id=s.id AND is_deleted=0) AS logs
         FROM t_user s
         LEFT JOIN t_assignment a ON a.student_id=s.id AND a.status=1
         LEFT JOIN t_enterprise e ON a.enterprise_id=e.id LEFT JOIN t_user t ON a.teacher_id=t.id
         WHERE s.id=?`, [sid]);
      const score = await benchmarkModel.getInternScore(sid, true);
      const rows = [
        ['实习手册（汇总）', ''], ['姓名', stu?.real_name], ['学号', stu?.eeid],
        ['实习单位', stu?.enterprise_name], ['指导教师', stu?.teacher_name],
        ['签到次数', stu?.checkins], ['日志份数', stu?.logs],
        ['综合考评', score?.total_score ?? '未核算']
      ];
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), '实习手册');
      const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
      auditExport(req, `导出实习手册(学生#${sid})`, 'intern-handbook', 1);
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', `attachment; filename=intern-handbook-${sid}.xlsx`);
      return res.send(buf);
    } catch (e) { return error(res, e.message, 500); }
  },
  async gdArchive(req, res) {
    try {
      const sid = req.user.role === 4 ? req.user.id : Number(req.query.student_id);
      const [topics, achs, grade] = await Promise.all([
        gdTopicModel.findAll({ studentId: sid }, { page: 1, pageSize: 5 }),
        gdAchievementModel.findAll({ studentId: sid }, { page: 1, pageSize: 50 }),
        gdGradeModel.findByStudent(sid)
      ]);
      const rows = [['毕设档案汇总', ''], ['选题', topics.list[0]?.title || '-'], ['指导教师', topics.list[0]?.teacher_name || '-']];
      achs.list.forEach(a => rows.push([benchmarkModel.DOC_LABELS[a.doc_type] || a.doc_type || '成果', `${a.title} (${a.status})`]));
      if (grade) rows.push(['综合成绩', grade.total_score], ['评阅', grade.review_score], ['答辩', grade.defense_score]);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), '毕设档案');
      const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
      auditExport(req, `导出毕设档案(学生#${sid})`, 'gd-archive', 1);
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', `attachment; filename=gd-archive-${sid}.xlsx`);
      return res.send(buf);
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 班主任 ===== */
  async classTeacherDashboard(req, res) {
    try {
      const students = await benchmarkModel.classTeacherStudents(req.user.id);
      const urge = await benchmarkModel.urgeList(null);
      const ids = new Set(students.map(s => s.id));
      const filter = arr => (arr || []).filter(x => ids.has(x.student_id));
      return success(res, { students, urge: {
        noCheckin: filter(urge.noCheckin), noWeekly: filter(urge.noWeekly),
        noConsent: filter(urge.noConsent), noAppraisal: filter(urge.noAppraisal)
      }});
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 学生答辩 ===== */
  async myDefense(req, res) {
    try {
      if (req.user.role !== 4) return error(res, '仅学生可查看', 403);
      return success(res, await benchmarkModel.studentDefense(req.user.id));
    } catch (e) { return error(res, e.message, 500); }
  },

  /* ===== 毕设成绩发布 ===== */
  async publishGdGrade(req, res) {
    try {
      if (req.user.role > 3) return error(res, '权限不足', 403);
      const pool = require('../config/db');
      await pool.query('UPDATE t_gd_grade SET published=1 WHERE student_id=?', [Number(req.params.studentId)]);
      await notify(Number(req.params.studentId), '毕设成绩已公布', '你的毕业设计成绩已正式发布', 'info');
      return success(res, null, '已发布');
    } catch (e) { return error(res, e.message, 500); }
  },

  docTypes(req, res) {
    return success(res, { types: benchmarkModel.DOC_TYPES, labels: benchmarkModel.DOC_LABELS });
  },

  async flowStatus(req, res) {
    try {
      if (req.user.role === 4) {
        return success(res, await benchmarkModel.studentFlowStatus(req.user.id));
      }
      if (req.user.role === 3) {
        return success(res, await benchmarkModel.teacherFlowPending(req.user.id));
      }
      return success(res, { message: '管理员请使用催办中心' });
    } catch (e) { return error(res, e.message, 500); }
  }
};

module.exports = benchmarkController;
