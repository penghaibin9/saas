const platformService = require('../services/platformService');
const tenancy = require('../config/tenancy');
const { success, error } = require('../utils/response');

// 统一处理 service 抛出的带状态异常
function fail(res, e) { return error(res, e.message, e.status || 500); }

const platformController = {
  async listTenants(req, res) {
    try { return success(res, await platformService.listTenants(), '租户列表'); }
    catch (e) { return fail(res, e); }
  },
  async getTenant(req, res) {
    try {
      const t = await platformService.getTenant(req.params.code);
      if (!t) return error(res, '租户不存在', 404);
      return success(res, t, '租户详情');
    } catch (e) { return fail(res, e); }
  },
  async provision(req, res) {
    try { return success(res, await platformService.provision(req.body, req.platformOperator), '开通成功', 201); }
    catch (e) { return fail(res, e); }
  },
  async setPlan(req, res) {
    try { await platformService.setPlan(req.params.code, req.body.plan, req.platformOperator); return success(res, null, '套餐已更新'); }
    catch (e) { return fail(res, e); }
  },
  async setQuota(req, res) {
    try { await platformService.setQuota(req.params.code, req.body, req.platformOperator); return success(res, null, '配额已更新'); }
    catch (e) { return fail(res, e); }
  },
  async renew(req, res) {
    try { await platformService.renew(req.params.code, req.body.expire_date, req.platformOperator); return success(res, null, '已续费'); }
    catch (e) { return fail(res, e); }
  },
  async suspend(req, res) {
    try { await platformService.suspend(req.params.code, req.platformOperator); return success(res, null, '已停服'); }
    catch (e) { return fail(res, e); }
  },
  async resume(req, res) {
    try { await platformService.resume(req.params.code, req.platformOperator); return success(res, null, '已恢复'); }
    catch (e) { return fail(res, e); }
  },
  async refreshUsage(req, res) {
    try { return success(res, await platformService.refreshUsage(req.params.code), '用量已刷新'); }
    catch (e) { return fail(res, e); }
  },
  async plans(req, res) {
    try { const tm = require('../models/tenantModel'); return success(res, await tm.listPlans(), '套餐列表'); }
    catch (e) { return fail(res, e); }
  },
  // 连接池统计（监控/排障）
  async poolStats(req, res) {
    return success(res, { mode: tenancy.MODE, ...tenancy.poolStats() }, '连接池统计');
  },

  // ── V2 计费对账 ──
  async billing(req, res) {
    try { return success(res, await require('../services/billingService').report(req.query.period), '计费对账'); }
    catch (e) { return fail(res, e); }
  },
  async billingRefresh(req, res) {
    try { return success(res, await require('../services/billingService').refreshAll(), '全租户用量已聚合'); }
    catch (e) { return fail(res, e); }
  },

  // ── V2 监管局跨校驾驶舱 ──
  async supervision(req, res) {
    try { return success(res, await require('../services/supervisionService').dashboard(), '跨校监管驾驶舱'); }
    catch (e) { return fail(res, e); }
  },
};

module.exports = platformController;
