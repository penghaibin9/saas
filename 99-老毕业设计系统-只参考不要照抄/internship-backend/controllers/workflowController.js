const workflowService = require('../services/workflowService');
const { success } = require('../utils/response');
const { AppError } = require('../utils/errors');

// 配置化流程引擎接口。管理端配置流程定义；业务端查看状态/驱动流转。
const workflowController = {
  async listDefs(req, res, next) {
    try {
      if (![1, 2].includes(req.user.role)) throw AppError.forbidden('仅管理员可查看流程配置');
      return success(res, await workflowService.listDefs(), '流程定义列表');
    } catch (e) { next(e); }
  },
  async getDef(req, res, next) {
    try {
      if (![1, 2].includes(req.user.role)) throw AppError.forbidden('权限不足');
      return success(res, await workflowService.getDef(req.params.bizType), '流程定义');
    } catch (e) { next(e); }
  },
  async setDefinition(req, res, next) {
    try {
      if (![1, 2].includes(req.user.role)) throw AppError.forbidden('仅管理员可配置流程');
      return success(res, await workflowService.replaceDefinition(req.params.bizType, req.body), '流程已更新');
    } catch (e) { next(e); }
  },
  async setEnabled(req, res, next) {
    try {
      if (![1, 2].includes(req.user.role)) throw AppError.forbidden('权限不足');
      await workflowService.setEnabled(req.params.bizType, req.body.enabled !== false);
      return success(res, null, '已更新');
    } catch (e) { next(e); }
  },
  async seed(req, res, next) {
    try {
      if (![1, 2].includes(req.user.role)) throw AppError.forbidden('权限不足');
      await workflowService.seedDefaults();
      return success(res, null, '已种入缺省流程');
    } catch (e) { next(e); }
  },

  // 业务：当前状态 + 可执行动作 + 历史
  async current(req, res, next) {
    try { return success(res, await workflowService.current(req.params.bizType, req.params.bizId, req.user), '当前流程状态'); }
    catch (e) { next(e); }
  },
  // 业务：驱动流转
  async dispatch(req, res, next) {
    try {
      const r = await workflowService.dispatch(req.params.bizType, req.params.bizId, req.body.action, req.user, req.body.remark);
      return success(res, r, '流转成功');
    } catch (e) { next(e); }
  },
};

module.exports = workflowController;
