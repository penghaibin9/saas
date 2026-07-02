const { analyticsModel, internStatsModel, riskModel } = require('../models');
const { success, error } = require('../utils/response');
const { buildWarnings, summarize } = require('../utils/risk');

// 状态码 -> 文案，便于前端直接渲染图表
const APP_STATUS = { 0: '待审核', 1: '教师同意', 2: '教师拒绝', 3: '院校通过', 4: '院校拒绝', 5: '已录用', 6: '未录用' };
const ACH_STATUS = { 0: '待审阅', 1: '通过', 2: '驳回', 3: '未完成' };
const TASK_STATUS = { 0: '未开始', 1: '进行中', 2: '已完成' };

// 风险数据范围：院校管理员全量，分院管理员限本院
function riskScope(user) {
  return user.role === 2 ? { collegeId: user.collegeId } : {};
}
const pct = (num, den) => (den ? Math.round((num / den) * 1000) / 10 : 0);

const analyticsController = {
  async intern(req, res) {
    try {
      const d = await analyticsModel.intern(req.user);
      d.statusDist = d.statusDist.map(r => ({ name: APP_STATUS[r.status] || r.status, value: r.cnt }));
      return success(res, d, '获取实习分析数据成功');
    } catch (err) {
      return error(res, '获取实习分析数据失败：' + err.message, 500);
    }
  },

  async gd(req, res) {
    try {
      const d = await analyticsModel.gd(req.user);
      d.achievementStatus = d.achievementStatus.map(r => ({ name: ACH_STATUS[r.status] || r.status, value: r.cnt }));
      d.taskStatus = d.taskStatus.map(r => ({ name: TASK_STATUS[r.status] || r.status, value: r.cnt }));
      return success(res, d, '获取毕业设计分析数据成功');
    } catch (err) {
      return error(res, '获取毕业设计分析数据失败：' + err.message, 500);
    }
  },

  async gdSummary(req, res) {
    try {
      const d = await analyticsModel.gdSummary(req.user);
      return success(res, d, '获取毕业设计概览成功');
    } catch (err) {
      return error(res, '获取毕业设计概览失败：' + err.message, 500);
    }
  },

  async excellence(req, res) {
    try {
      const d = await analyticsModel.excellence(req.user);
      return success(res, d, '获取优秀师生成功');
    } catch (err) {
      return error(res, '获取优秀师生失败：' + err.message, 500);
    }
  },

  /**
   * 迎检数据大屏（领导驾驶舱）：一次返回全部 KPI、图表与重点名单，
   * 服务端并行聚合现有实习/风险/分析数据，前端单次请求即可渲染大屏。
   */
  async cockpit(req, res) {
    try {
      const user = req.user;
      const [summary, internData, riskRows, incomplete, todayLeaves] = await Promise.all([
        internStatsModel.summary(user),
        analyticsModel.intern(user),
        riskModel.getStudentRiskData(riskScope(user)),
        internStatsModel.incompleteStudents(user, { page: 1, pageSize: 10 }),
        analyticsModel.todayLeaveCount(user)
      ]);

      // 风险研判（复用共享阈值逻辑）
      const warnings = [];
      for (const row of riskRows) warnings.push(...buildWarnings(row));
      const { summary: riskSummary, list: riskList } = summarize(warnings, riskRows.length);

      const internCount = summary.studentCount || 0;
      const onPost = Math.max(0, internCount - todayLeaves);

      const kpi = {
        internCount,                                   // 在册实习人数
        enterpriseCount: summary.enterpriseCount || 0, // 合作企业数
        todayCheckins: summary.todayCheckins || 0,     // 今日打卡人次
        todayCheckinStudents: summary.todayCheckinStudents || 0, // 今日打卡人数(去重)
        checkinRate: pct(summary.todayCheckinStudents || 0, internCount), // 打卡率(%) = 打卡人数/在册
        onPost,                                        // 今日在岗人数
        todayLeaves,                                   // 今日请假人数
        onPostRate: pct(onPost, internCount),          // 在岗率(%)
        incompleteCount: incomplete.total || 0,        // 过程未达标人数
        riskStudents: riskSummary.students,            // 涉险学生数
        riskHigh: riskSummary.high                     // 高风险预警数
      };

      // 申请状态分布转文案
      const statusDist = (internData.statusDist || []).map(r => ({ name: APP_STATUS[r.status] || r.status, value: r.cnt }));

      return success(res, {
        updatedAt: new Date().toISOString(),
        kpi,
        riskSummary,
        riskList: riskList.slice(0, 10),
        incompleteList: incomplete.list || [],
        charts: {
          statusDist,
          enterpriseTop: internData.enterpriseTop || [],
          checkinTrend: internData.checkinTrend || [],
          collegeDist: internData.collegeDist || [],
          industryDist: internData.industryDist || []
        }
      }, '获取迎检大屏数据成功');
    } catch (err) {
      return error(res, '获取迎检大屏数据失败：' + err.message, 500);
    }
  }
};

module.exports = analyticsController;
