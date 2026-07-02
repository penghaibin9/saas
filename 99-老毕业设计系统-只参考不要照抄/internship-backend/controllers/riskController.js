const { riskModel } = require('../models');
const { success, error } = require('../utils/response');
const { notify } = require('../utils/notify');
const { buildWarnings, summarize } = require('../utils/risk');

// 角色过滤：管理员全量，分院按学院，教师按本人指导学生
function scopeFor(user) {
  if (user.role === 3) return { teacherId: user.id };
  if (user.role === 2) return { collegeId: user.collegeId };
  return {}; // 超管全量
}

const riskController = {
  async warnings(req, res) {
    try {
      if (req.user.role === 4) return error(res, '无权限查看风险预警', 403);
      const rows = await riskModel.getStudentRiskData(scopeFor(req.user));
      const list = [];
      for (const row of rows) list.push(...buildWarnings(row));
      const { summary, list: sorted } = summarize(list, rows.length);
      return success(res, { summary, list: sorted }, '获取风险预警成功');
    } catch (err) {
      return error(res, '获取风险预警失败：' + err.message, 500);
    }
  },

  // 一键通知：给被预警学生发送站内提醒（按当前用户权限范围）
  async notifyAll(req, res) {
    try {
      if (req.user.role === 4) return error(res, '无权限', 403);
      const rows = await riskModel.getStudentRiskData(scopeFor(req.user));
      const byStudent = new Map();
      for (const row of rows) {
        const ws = buildWarnings(row);
        if (ws.length) byStudent.set(row.student_id, ws);
      }
      let sent = 0;
      for (const [studentId, ws] of byStudent.entries()) {
        const msg = ws.map((w) => '· ' + w.message).join('\n');
        await notify(studentId, '实习风险提醒', '检测到以下情况，请及时处理：\n' + msg, 'warning');
        sent++;
      }
      return success(res, { sent }, `已向 ${sent} 名学生发送提醒`);
    } catch (err) {
      return error(res, '发送提醒失败：' + err.message, 500);
    }
  }
};

module.exports = riskController;
