const path = require('path');
const XLSX = require('xlsx');
const multer = require('multer');
const pool = require('../config/db');
const { provinceModel, gdAchievementModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

const MAX_IMPORT_ROWS = 5000;
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (['.xlsx', '.xls'].includes(ext)) cb(null, true);
    else cb(new Error('仅支持 .xlsx / .xls 格式'));
  }
});

const provinceController = {
  uploadMiddleware: upload.single('file'),

  async list(req, res) {
    try {
      const { matched, uploaded, keyword, batch_year } = req.query;
      const result = await provinceModel.findAll({
        matched:   matched   !== undefined ? Number(matched)   : undefined,
        uploaded:  uploaded  !== undefined ? Number(uploaded)  : undefined,
        batchYear: batch_year !== undefined ? Number(batch_year) : undefined,
        keyword
      }, clampPagination(req.query));
      result.isDemo = true;
      result.integrationMode = 'excel-import';
      result.realReceipt = false;
      return success(res, result, '获取省厅名单成功');
    } catch (err) {
      return error(res, '获取省厅名单失败：' + err.message, 500);
    }
  },

  /**
   * 一键获取省厅名单：因无真实省平台接口，以 Excel 导入模拟“获取”。
   * 列：姓名/性别/身份证号/学号/毕业证书编号/学制/专业编号/专业名称/届别
   */
  async fetchList(req, res) {
    if (!req.file) return error(res, '请上传省厅名单 Excel（模拟一键获取）', 400);
    let conn;
    try {
      const wb = XLSX.read(req.file.buffer, { type: 'buffer' });
      const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
      if (!rows.length) return error(res, 'Excel 文件为空', 400);
      if (rows.length > MAX_IMPORT_ROWS) return error(res, `单次最多 ${MAX_IMPORT_ROWS} 条`, 400);

      let count = 0;
      conn = await pool.getConnection();
      await conn.beginTransaction();
      for (const row of rows) {
        const name = String(row['姓名'] || row['name'] || '').trim();
        if (!name) continue;
        await provinceModel.upsertByKey({
          name,
          gender: String(row['性别'] || '').trim(),
          id_card: String(row['身份证号'] || row['身份证'] || '').trim(),
          eeid: String(row['学号'] || '').trim(),
          cert_no: String(row['毕业证书编号'] || row['证书编号'] || '').trim(),
          edu_system: String(row['学制'] || '').trim(),
          major_code: String(row['专业编号'] || row['专业代码'] || '').trim(),
          major_name: String(row['专业名称'] || '').trim(),
          batch_year: Number(row['届别'] || row['年份']) || null
        }, conn);
        count++;
      }
      await conn.commit();
      return success(res, {
        count,
        isDemo: true,
        integrationMode: 'excel-import',
        realReceipt: false
      }, `已从 Excel 导入名单 ${count} 条（联调演示，非省平台直连）`);
    } catch (err) {
      if (conn) { try { await conn.rollback(); } catch (_) { /* ignore */ } }
      return error(res, '获取省厅名单失败：' + err.message, 500);
    } finally {
      if (conn) conn.release();
    }
  },

  // 校验：将省厅名单与本校学生比对，输出差异
  async verify(req, res) {
    try {
      const province = await provinceModel.all();
      const [locals] = await pool.query(
        `SELECT id, real_name, eeid FROM t_user WHERE role = 4 AND is_deleted = 0`
      );
      const localByEeid = new Map();
      const localByName = new Map();
      for (const s of locals) {
        if (s.eeid) localByEeid.set(String(s.eeid).trim(), s);
        localByName.set(String(s.real_name).trim(), s);
      }

      const onlyInProvince = []; // 省有校无
      const matchedPairs = [];
      const matchedLocalIds = new Set();

      for (const p of province) {
        let local = null;
        if (p.eeid && localByEeid.has(String(p.eeid).trim())) local = localByEeid.get(String(p.eeid).trim());
        else if (localByName.has(String(p.name).trim())) local = localByName.get(String(p.name).trim());

        if (local) {
          matchedPairs.push({ province_id: p.id, name: p.name, local_student_id: local.id, eeid: local.eeid });
          matchedLocalIds.add(local.id);
          await provinceModel.setMatch(p.id, local.id);
        } else {
          onlyInProvince.push({ province_id: p.id, name: p.name, eeid: p.eeid, id_card: p.id_card });
          await provinceModel.setMatch(p.id, null);
        }
      }

      const onlyInLocal = locals
        .filter(s => !matchedLocalIds.has(s.id))
        .map(s => ({ local_student_id: s.id, name: s.real_name, eeid: s.eeid })); // 校有省无

      return success(res, {
        isDemo: true,
        integrationMode: 'local-verify',
        realReceipt: false,
        provinceTotal: province.length,
        localTotal: locals.length,
        matched: matchedPairs.length,
        onlyInProvinceCount: onlyInProvince.length,
        onlyInLocalCount: onlyInLocal.length,
        onlyInProvince,
        onlyInLocal
      }, '校验完成');
    } catch (err) {
      return error(res, '校验失败：' + err.message, 500);
    }
  },

  // 上传毕业设计成果链接至省平台（模拟）。可传 link，或自动取该学生已通过的成果链接
  async uploadAchievement(req, res) {
    try {
      const id = Number(req.params.id);
      const p = await provinceModel.findById(id);
      if (!p) return error(res, '省厅名单记录不存在', 404);
      if (!p.matched || !p.local_student_id) return error(res, '该名单未匹配到本校学生，无法上传', 400);

      let link = req.body.link;
      if (!link) {
        // 自动取该学生已通过的成果链接
        const ach = await gdAchievementModel.findAll({ studentId: p.local_student_id, status: 1 }, { page: 1, pageSize: 1 });
        const a = ach.list[0];
        link = a ? (a.link || a.file_url) : null;
      }
      if (!link) return error(res, '未找到可上传的成果链接，请先确认学生成果已审阅通过', 400);

      await provinceModel.markUploaded(id, link);
      const updated = await provinceModel.findById(id);
      return success(res, {
        ...updated,
        isDemo: true,
        integrationMode: 'local-status',
        realReceipt: false,
        receipt: null
      }, '已记录模拟上传状态（未向省平台发送，不代表真实回执）');
    } catch (err) {
      return error(res, '上传失败：' + err.message, 500);
    }
  },

  // 下载省厅名单导入模板
  async downloadTemplate(req, res) {
    const data = [{
      姓名: '张三', 性别: '男', 身份证号: '430000200201011234', 学号: '20240001',
      毕业证书编号: 'BYZ2026001', 学制: '3年', 专业编号: 'CS', 专业名称: '计算机科学与技术', 届别: 2026
    }];
    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, '省厅名单模板');
    const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', 'attachment; filename="province_list_template.xlsx"');
    return res.send(buf);
  }
};

module.exports = provinceController;
