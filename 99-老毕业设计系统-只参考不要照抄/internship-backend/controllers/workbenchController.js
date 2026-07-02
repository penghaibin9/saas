const { workbenchModel, notificationModel, workflowConfigModel } = require('../models');
const { success, error } = require('../utils/response');

const STEP_LABEL_KEYS = {
  application: { 2: 'application_review' },
  leave: { 2: 'leave_review' },
  position: { 2: 'position_audit' },
  assignment_change: { 2: 'assignment_change_teacher', 3: 'assignment_change_admin' },
  complaint: { 2: 'complaint_handle' },
  enterprise: { 2: 'enterprise_audit' },
  filing: { 2: 'filing_submit' }
};

async function loadFlowLabels() {
  const labels = {};
  try {
    await workflowConfigModel.ensureTable();
    const rows = await workflowConfigModel.listAll();
    for (const r of rows) {
      const map = STEP_LABEL_KEYS[r.module_key];
      if (map && map[r.step_no]) labels[map[r.step_no]] = r.step_name;
    }
  } catch (_) {}
  return labels;
}

const workbenchController = {
  async index(req, res) {
    try {
      const user = req.user;
      let data = {};
      if (user.role === 3) data = await workbenchModel.teacher(user.id);
      else if (user.role === 4) data = await workbenchModel.student(user.id);
      else if (user.role === 1) data = await workbenchModel.admin(null);
      else if (user.role === 2) data = await workbenchModel.admin(user.collegeId);

      data.unreadNotifications = await notificationModel.unreadCount(user.id);
      const flowLabels = await loadFlowLabels();
      data.flowLabels = flowLabels;
      data.alerts = workbenchModel.buildAlerts(user.role, data, flowLabels);
      return success(res, data, '获取工作台数据成功');
    } catch (err) {
      return error(res, '获取工作台数据失败：' + err.message, 500);
    }
  }
};

module.exports = workbenchController;
