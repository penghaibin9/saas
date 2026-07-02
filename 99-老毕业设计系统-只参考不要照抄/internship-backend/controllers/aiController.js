const ai = require('../utils/ai');
const { internLogModel, reportModel, positionModel, userModel } = require('../models');
const { success, error } = require('../utils/response');

/**
 * AI 智能控制器（DeepSeek 驱动，未配置自动降级演示）
 * 所有接口均在路由层挂鉴权 + AI 专用限流；此处再做资源归属/角色校验，防越权。
 */
const aiController = {
  async status(req, res) {
    return success(res, ai.status(), 'AI 服务状态');
  },

  // 当月 AI 用量与配额（管理员/教师）
  async usage(req, res) {
    try {
      if (![1, 2, 3].includes(req.user.role)) return error(res, '权限不足', 403);
      return success(res, await ai.usageStatus(), 'AI 用量');
    } catch (e) { return error(res, '获取用量失败：' + e.message, 500); }
  },

  // 实习周报/月报智能质检（学生本人 / 指导教师 / 院校管理员）
  async scoreLog(req, res) {
    try {
      const log = await internLogModel.findById(Number(req.params.id));
      if (!log) return error(res, '记录不存在', 404);
      const u = req.user;
      const allowed = (u.role === 4 && log.student_id === u.id)
        || (u.role === 3 && log.teacher_id === u.id)
        || (u.role === 2 && log.student_college_id === u.collegeId)
        || u.role === 1;
      if (!allowed) return error(res, '权限不足', 403);
      const result = await ai.scoreLog({ title: log.title, content: log.content, type: log.type });
      return success(res, result, result.isDemo ? '演示结果（未配置 AI）' : 'AI 质检完成');
    } catch (e) { return error(res, 'AI 质检失败：' + e.message, 500); }
  },

  // 实习报告 AI 辅助评阅（仅指导教师，且须为本人指导的报告）
  async reviewReport(req, res) {
    try {
      if (req.user.role !== 3) return error(res, '仅指导教师可使用辅助评阅', 403);
      const report = await reportModel.findById(Number(req.params.id));
      if (!report) return error(res, '报告不存在', 404);
      if (report.teacher_id && report.teacher_id !== req.user.id) {
        return error(res, '只能评阅本人指导学生的报告', 403);
      }
      const result = await ai.reviewReport({ title: report.title, content: report.content });
      return success(res, result, result.isDemo ? '演示结果（未配置 AI）' : 'AI 评阅完成（请教师确认后采纳）');
    } catch (e) { return error(res, 'AI 评阅失败：' + e.message, 500); }
  },

  // 文本风险研判（教师/管理员）：可直接传 text，或对某条日志研判
  async analyzeRisk(req, res) {
    try {
      if (![1, 2, 3].includes(req.user.role)) return error(res, '权限不足', 403);
      let text = typeof req.body.text === 'string' ? req.body.text : '';
      if (!text && req.body.log_id) {
        const log = await internLogModel.findById(Number(req.body.log_id));
        if (!log) return error(res, '日志不存在', 404);
        if (req.user.role === 3 && log.teacher_id !== req.user.id) return error(res, '权限不足', 403);
        if (req.user.role === 2 && log.student_college_id !== req.user.collegeId) return error(res, '权限不足', 403);
        text = `${log.title || ''}\n${log.content || ''}`;
      }
      if (!text.trim()) return error(res, '请提供待分析文本或日志ID', 400);
      const result = await ai.analyzeRiskText({ text });
      return success(res, result, result.isDemo ? '演示结果（未配置 AI）' : 'AI 风险研判完成');
    } catch (e) { return error(res, 'AI 风险研判失败：' + e.message, 500); }
  },

  // 政策/流程问答助手（任意登录用户）
  async assistant(req, res) {
    try {
      const question = typeof req.body.question === 'string' ? req.body.question.trim() : '';
      if (!question) return error(res, '问题不能为空', 400);
      if (question.length > 1000) return error(res, '问题过长（上限1000字）', 400);
      const result = await ai.assistantAnswer({ question, role: req.user.roleName });
      return success(res, result, result.isDemo ? '演示结果（未配置 AI）' : '');
    } catch (e) { return error(res, 'AI 助手失败：' + e.message, 500); }
  },

  // 岗位智能匹配推荐（学生本人）
  async matchPositions(req, res) {
    try {
      if (req.user.role !== 4) return error(res, '仅学生可使用岗位匹配', 403);
      const me = await userModel.findById(req.user.id);
      const skills = (req.body.skills || (me && me.skill_tags) || '').toString().trim();
      if (!skills) return error(res, '请先在个人资料中填写技能标签，或在请求中提供 skills', 400);
      const { list } = await positionModel.findAll({ status: 1, collegeId: me && me.college_id }, { page: 1, pageSize: 30 });
      if (!list.length) return error(res, '暂无可推荐的开放岗位', 404);
      const result = await ai.matchPositions({ skills, positions: list });
      return success(res, result, result.isDemo ? '演示结果（未配置 AI）' : 'AI 匹配完成');
    } catch (e) { return error(res, 'AI 岗位匹配失败：' + e.message, 500); }
  },
};

module.exports = aiController;
