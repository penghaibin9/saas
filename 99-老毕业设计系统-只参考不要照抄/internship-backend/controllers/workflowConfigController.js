const { workflowConfigModel } = require('../models');
const { success, error } = require('../utils/response');

const workflowConfigController = {
  async list(req, res) {
    try {
      const rows = await workflowConfigModel.listAll();
      const grouped = {};
      rows.forEach(r => {
        if (!grouped[r.module_key]) {
          grouped[r.module_key] = { moduleKey: r.module_key, label: workflowConfigModel.moduleLabel(r.module_key), steps: [] };
        }
        grouped[r.module_key].steps.push(r);
      });
      return success(res, { modules: Object.values(grouped), list: rows }, '获取流程配置成功');
    } catch (err) {
      return error(res, '获取流程配置失败：' + err.message, 500);
    }
  },

  async updateStep(req, res) {
    try {
      const id = Number(req.params.id);
      const { step_name, role_id, description, is_enabled } = req.body || {};
      const n = await workflowConfigModel.updateStep(id, { step_name, role_id, description, is_enabled });
      if (!n) return error(res, '步骤不存在或无变更', 404);
      return success(res, null, '流程步骤已更新');
    } catch (err) {
      return error(res, '更新失败：' + err.message, 500);
    }
  }
};

module.exports = workflowConfigController;
