const XLSX = require('xlsx');
const reportingModel = require('../models/reportingModel');
const { auditLogModel } = require('../models');
const { success, error } = require('../utils/response');

const PUSH_URL = process.env.REPORTING_PUSH_URL || '';
const PUSH_KEY = process.env.REPORTING_PUSH_KEY || '';
const PUSH_TIMEOUT = Number(process.env.REPORTING_TIMEOUT || 20000);

function pushConfigured() { return !!PUSH_URL; }

// 仅院校/分院管理员可操作报送
function canReport(role) { return [1, 2].includes(role); }

function scopeFilter(req) {
  const filter = { batchYear: req.query.batchYear, onlyAssigned: req.query.onlyAssigned === '1' };
  if (req.user.role === 2) filter.collegeId = req.user.collegeId;
  else if (req.query.collegeId) filter.collegeId = Number(req.query.collegeId);
  return filter;
}

const reportingController = {
  // 报送字段映射 + 上报通道状态（如实区分演示/已对接）
  async config(req, res) {
    return success(res, {
      fields: reportingModel.fieldMap(),
      push: { configured: pushConfigured(), url: pushConfigured() ? PUSH_URL.replace(/\/\/.*@/, '//') : '' },
    }, '报送配置');
  },

  // 预览报送数据集（返回总数 + 标准列样例，避免一次性传输过大）
  async preview(req, res) {
    try {
      if (!canReport(req.user.role)) return error(res, '仅管理员可生成报送数据', 403);
      const records = await reportingModel.fetchRecords(scopeFilter(req));
      const rows = reportingModel.toStandardRows(records);
      return success(res, { total: rows.length, sample: rows.slice(0, 50), fields: reportingModel.fieldMap() }, '报送预览生成成功');
    } catch (e) { return error(res, '生成失败：' + e.message, 500); }
  },

  // 导出标准报送包（xlsx）
  async export(req, res) {
    try {
      if (!canReport(req.user.role)) return error(res, '仅管理员可导出报送包', 403);
      const records = await reportingModel.fetchRecords(scopeFilter(req));
      const rows = reportingModel.toStandardRows(records);
      const ws = XLSX.utils.json_to_sheet(rows.length ? rows : [{ 说明: '暂无在册实习数据' }]);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, '实习报送');
      const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
      auditLogModel.create({
        user_id: req.user.id, username: req.user.username, real_name: req.user.realName,
        role: req.user.role, college_id: req.user.collegeId, ip: req.ip,
        method: 'GET', path: '/api/reporting/export', action: 'export', target_type: 'reporting',
        status_code: 200, success: 1, detail: JSON.stringify({ count: rows.length }),
      }).catch(() => {});
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', 'attachment; filename=internship_report_package.xlsx');
      return res.send(buf);
    } catch (e) { return error(res, '导出失败：' + e.message, 500); }
  },

  // 推送上报到省级/国家平台（经配置的网关）；未配置则返回演示态预览结果
  async push(req, res) {
    try {
      if (req.user.role !== 1) return error(res, '仅院校管理员可执行上报推送', 403);
      const records = await reportingModel.fetchRecords(scopeFilter(req));
      const rows = reportingModel.toStandardRows(records);
      const batch = { batchNo: 'RPT' + Date.now(), count: rows.length, generatedAt: new Date().toISOString() };

      if (!pushConfigured()) {
        return success(res, { ...batch, isDemo: true, records: rows.slice(0, 20) },
          '未配置上报网关（REPORTING_PUSH_URL），已生成报送包预览（演示）');
      }

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), PUSH_TIMEOUT);
      try {
        const r = await fetch(PUSH_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(PUSH_KEY ? { Authorization: 'Bearer ' + PUSH_KEY } : {}) },
          body: JSON.stringify({ batch, records: rows }),
          signal: controller.signal,
        });
        const ok = r.ok;
        let data = null; try { data = await r.json(); } catch (_) {}
        auditLogModel.create({
          user_id: req.user.id, username: req.user.username, real_name: req.user.realName,
          role: req.user.role, college_id: req.user.collegeId, ip: req.ip,
          method: 'POST', path: '/api/reporting/push', action: 'report_push', target_type: 'reporting',
          status_code: r.status, success: ok ? 1 : 0, detail: JSON.stringify({ count: rows.length, batchNo: batch.batchNo }),
        }).catch(() => {});
        if (!ok) return error(res, '上报网关返回 HTTP ' + r.status, 502, data);
        return success(res, { ...batch, isDemo: false, gateway: data }, '上报成功');
      } finally { clearTimeout(timer); }
    } catch (e) { return error(res, '上报失败：' + e.message, 500); }
  },
};

module.exports = reportingController;
