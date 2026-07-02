const XLSX = require('xlsx');
const pool = require('../config/db');
const { filingModel, assignmentModel, systemConfigModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

const STATUS_TEXT = { 0: '待生成', 1: '待提交', 2: '已提交省平台', 3: '已备案', 4: '驳回' };

const filingController = {
  async overview(req, res) {
    try {
      const collegeId = req.user.role === 2 ? req.user.collegeId : null;
      const data = await filingModel.overview(collegeId);
      return success(res, data, '获取备案统计成功');
    } catch (err) {
      return error(res, '获取统计失败：' + err.message, 500);
    }
  },

  async list(req, res) {
    try {
      const filter = {
        status: req.query.status !== undefined ? Number(req.query.status) : undefined,
        batchYear: req.query.batch_year,
        keyword: req.query.keyword
      };
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      const result = await filingModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取备案列表成功');
    } catch (err) {
      return error(res, '获取备案列表失败：' + err.message, 500);
    }
  },

  /** 从在册实习分配批量生成备案记录（待提交） */
  async generate(req, res) {
    try {
      const batchYear = req.body && req.body.batch_year
        ? String(req.body.batch_year)
        : await systemConfigModel.get('batch_year');
      const filter = { status: 1 };
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      const { list } = await assignmentModel.findAll(filter, { page: 1, pageSize: 5000 });
      let created = 0;
      for (const a of list) {
        const [[exists]] = await pool.query(
          'SELECT id FROM t_filing_record WHERE assignment_id = ? AND is_deleted = 0 LIMIT 1', [a.id]
        );
        if (exists) continue;
        await filingModel.createFromAssignment({
          student_id: a.student_id,
          id: a.id,
          enterprise_name: a.enterprise_name,
          position_title: a.position_title || null,
          start_date: a.plan_start_date || null,
          end_date: a.plan_end_date || null
        }, batchYear);
        created++;
      }
      return success(res, { created, batchYear }, `已生成 ${created} 条备案记录`);
    } catch (err) {
      return error(res, '生成备案失败：' + err.message, 500);
    }
  },

  /** 标记提交省平台（mock 模式下模拟对接） */
  async submit(req, res) {
    try {
      const id = Number(req.params.id);
      const rec = await filingModel.findById(id);
      if (!rec) return error(res, '记录不存在', 404);
      if (req.user.role === 2 && rec.college_id !== req.user.collegeId) return error(res, '权限不足', 403);
      if (rec.status !== 1) return error(res, '仅「待提交」状态可提交', 400);
      const mode = await systemConfigModel.get('province_api_mode');
      const refNo = mode === 'live'
        ? (req.body && req.body.province_ref_no) || null
        : `MOCK-${Date.now()}-${id}`;
      if (mode === 'live' && !refNo) return error(res, '真实对接模式下需填写省平台回执号', 400);
      await filingModel.updateStatus(id, 2, { province_ref_no: refNo, remark: req.body && req.body.remark });
      if (rec.student_id) {
        await notify(rec.student_id, '实习备案已提交', `您的实习备案已提交省平台，回执号：${refNo}`, 'info');
      }
      return success(res, { provinceRefNo: refNo }, '已提交省平台');
    } catch (err) {
      return error(res, '提交失败：' + err.message, 500);
    }
  },

  async markFiled(req, res) {
    try {
      const id = Number(req.params.id);
      const rec = await filingModel.findById(id);
      if (!rec) return error(res, '记录不存在', 404);
      if (rec.status !== 2) return error(res, '仅「已提交」状态可确认备案', 400);
      await filingModel.updateStatus(id, 3, { remark: req.body && req.body.remark });
      return success(res, null, '已标记为备案完成');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  },

  async reject(req, res) {
    try {
      const id = Number(req.params.id);
      const remark = req.body && req.body.remark;
      if (!remark) return error(res, '请填写驳回原因', 400);
      await filingModel.updateStatus(id, 4, { remark });
      const rec = await filingModel.findById(id);
      if (rec && rec.student_id) {
        await notify(rec.student_id, '实习备案被驳回', remark, 'warning');
      }
      return success(res, null, '已驳回');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  },

  /** 导出省平台备案包 Excel */
  async exportPack(req, res) {
    try {
      const batchYear = req.query.batch_year || await systemConfigModel.get('batch_year');
      const filter = { batchYear, status: req.query.status !== undefined ? Number(req.query.status) : undefined };
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      const { list } = await filingModel.findAll(filter, { page: 1, pageSize: 5000 });
      const rows = list.map(f => ({
        学号: f.student_eeid || '',
        姓名: f.student_name || '',
        实习单位: f.enterprise_name || '',
        实习岗位: f.position_title || '',
        开始日期: f.start_date ? String(f.start_date).slice(0, 10) : '',
        结束日期: f.end_date ? String(f.end_date).slice(0, 10) : '',
        届别: f.batch_year || batchYear,
        备案状态: STATUS_TEXT[f.status] || f.status,
        省平台回执号: f.province_ref_no || ''
      }));
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(rows.length ? rows : [{ 说明: '暂无数据' }]), '实习备案');
      const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
      const batch = `FILING-${batchYear}-${Date.now()}`;
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      res.setHeader('Content-Disposition', `attachment; filename=filing-${batchYear}.xlsx`);
      return res.send(buf);
    } catch (err) {
      return error(res, '导出失败：' + err.message, 500);
    }
  }
};

module.exports = filingController;
