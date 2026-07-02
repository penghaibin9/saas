const { systemConfigModel } = require('../models');
const { success, error } = require('../utils/response');
const wxMessage = require('../utils/wxMessage');
const sms = require('../utils/sms');

const PUBLIC_KEYS = ['school_name', 'batch_year', 'cas_enabled', 'cas_login_url', 'module_intern_enabled', 'module_gd_enabled'];

const systemConfigController = {
  async getPublic(req, res) {
    try {
      const all = await systemConfigModel.getAll();
      const pub = {};
      PUBLIC_KEYS.forEach(k => { pub[k] = all[k]; });
      pub.cas_server_url = all.cas_server_url || '';
      return success(res, pub, '获取公开配置成功');
    } catch (err) {
      return error(res, '获取配置失败：' + err.message, 500);
    }
  },

  async getChannels(req, res) {
    try {
      const cfg = await systemConfigModel.getAll();
      return success(res, {
        wx: { configured: wxMessage.configured(), enabled: cfg.notify_wx_enabled === '1' },
        sms: { configured: sms.configured(), enabled: cfg.notify_sms_enabled === '1', provider: process.env.SMS_PROVIDER || '' }
      }, '获取消息通道状态成功');
    } catch (err) {
      return error(res, '获取通道状态失败：' + err.message, 500);
    }
  },

  async getAll(req, res) {
    try {
      const all = await systemConfigModel.getAll();
      return success(res, all, '获取系统配置成功');
    } catch (err) {
      return error(res, '获取配置失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const allowed = [
        'school_name', 'batch_year', 'notify_wx_enabled', 'notify_sms_enabled',
        'province_api_mode', 'cas_enabled', 'cas_login_url', 'cas_server_url',
        'cas_validate_url', 'app_public_url', 'webhook_url', 'sla_phone', 'sla_email',
        'module_intern_enabled', 'module_gd_enabled'
      ];
      const body = req.body || {};
      const pairs = {};
      allowed.forEach(k => { if (body[k] !== undefined) pairs[k] = body[k]; });
      if (!Object.keys(pairs).length) return error(res, '无有效配置项', 400);
      await systemConfigModel.setMany(pairs);
      return success(res, await systemConfigModel.getAll(), '配置已保存');
    } catch (err) {
      return error(res, '保存配置失败：' + err.message, 500);
    }
  }
};

module.exports = systemConfigController;
