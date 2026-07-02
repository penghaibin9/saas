const { enterpriseModel, userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { isValidLat, isValidLng } = require('../utils/geo');
const { notify } = require('../utils/notify');

// 校验经纬度/打卡半径（允许为空，但填了就必须合法）
function validateGeo(body) {
  if (body.longitude !== undefined && body.longitude !== null && body.longitude !== '' && !isValidLng(body.longitude)) {
    return '经度不合法（应在 -180 ~ 180 之间）';
  }
  if (body.latitude !== undefined && body.latitude !== null && body.latitude !== '' && !isValidLat(body.latitude)) {
    return '纬度不合法（应在 -90 ~ 90 之间）';
  }
  if (body.checkin_radius !== undefined && body.checkin_radius !== null && body.checkin_radius !== '') {
    const r = Number(body.checkin_radius);
    if (!Number.isFinite(r) || r < 0) return '打卡半径不合法（应为非负数，单位米，0 表示不约束）';
  }
  return null;
}

const enterpriseController = {
  async list(req, res) {
    try {
      const { status, coop_status, keyword } = req.query;
      const result = await enterpriseModel.findAll(
        {
          status: status !== undefined && status !== '' ? Number(status) : undefined,
          coopStatus: coop_status !== undefined && coop_status !== '' ? Number(coop_status) : undefined,
          keyword
        },
        clampPagination(req.query)
      );
      return success(res, result, '获取企业列表成功');
    } catch (err) {
      return error(res, '获取企业列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const enterprise = await enterpriseModel.findById(Number(req.params.id));
      if (!enterprise) return error(res, '企业不存在', 404);
      return success(res, enterprise, '获取企业详情成功');
    } catch (err) {
      return error(res, '获取企业详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { name, short_name, industry, address, contact_name, contact_phone, contact_email, description, longitude, latitude, checkin_radius,
        credit_code, nature, scale, legal_person, reg_capital, website, license_url, coop_status } = req.body;
      if (!name) return error(res, '企业名称不能为空', 400);
      const geoErr = validateGeo(req.body);
      if (geoErr) return error(res, geoErr, 400);

      const id = await enterpriseModel.create({ name, short_name, industry, address, contact_name, contact_phone, contact_email, description, longitude, latitude, checkin_radius,
        credit_code, nature, scale, legal_person, reg_capital, website, license_url, coop_status });
      const enterprise = await enterpriseModel.findById(id);
      return success(res, enterprise, '创建企业成功', 201);
    } catch (err) {
      return error(res, '创建企业失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const enterprise = await enterpriseModel.findById(id);
      if (!enterprise) return error(res, '企业不存在', 404);
      const geoErr = validateGeo(req.body);
      if (geoErr) return error(res, geoErr, 400);

      await enterpriseModel.update(id, req.body);
      const updated = await enterpriseModel.findById(id);
      return success(res, updated, '更新企业成功');
    } catch (err) {
      return error(res, '更新企业失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const enterprise = await enterpriseModel.findById(id);
      if (!enterprise) return error(res, '企业不存在', 404);
      await enterpriseModel.remove(id);
      return success(res, null, '删除企业成功');
    } catch (err) {
      return error(res, '删除企业失败：' + err.message, 500);
    }
  },

  /** 管理员：待审核入驻企业列表（audit_status=0）。 */
  async pending(req, res) {
    try {
      const result = await enterpriseModel.findAll(
        { auditStatus: 0, keyword: req.query.keyword }, clampPagination(req.query)
      );
      return success(res, result, '获取待审核企业成功');
    } catch (err) {
      return error(res, '获取待审核企业失败：' + err.message, 500);
    }
  },

  /**
   * 管理员：审核企业入驻。approve=true 通过并激活企业账号；否则拒绝。
   * 同步激活/停用该企业绑定的企业导师账号。
   */
  async audit(req, res) {
    try {
      const id = Number(req.params.id);
      const enterprise = await enterpriseModel.findById(id);
      if (!enterprise) return error(res, '企业不存在', 404);

      const approve = req.body && (req.body.approve === true || req.body.approve === 'true' || req.body.approve === 1);
      const remark = req.body && req.body.remark ? String(req.body.remark).slice(0, 255) : null;
      await enterpriseModel.setAudit(id, approve ? 1 : 2, remark);

      // 同步企业绑定账号状态
      const account = await userModel.findByEnterpriseId(id);
      if (account) {
        await userModel.updateInfo(account.id, { status: approve ? 1 : 0 });
        await notify(
          account.id,
          approve ? '企业入驻审核通过' : '企业入驻未通过',
          approve ? '您的企业已通过审核，现在可以登录发布岗位、确认录用了' : `审核未通过：${remark || '请联系学校实训中心'}`,
          approve ? 'success' : 'warning'
        );
      }
      return success(res, null, approve ? '已通过审核' : '已拒绝');
    } catch (err) {
      return error(res, '审核失败：' + err.message, 500);
    }
  }
};

module.exports = enterpriseController;
