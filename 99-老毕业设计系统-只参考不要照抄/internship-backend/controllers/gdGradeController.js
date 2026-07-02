const path = require('path');
const XLSX = require('xlsx');
const multer = require('multer');
const pool = require('../config/db');
const { gdGradeModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

const MAX_IMPORT_ROWS = 1000;
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (['.xlsx', '.xls'].includes(ext)) cb(null, true);
    else cb(new Error('仅支持 .xlsx / .xls 格式'));
  }
});

function validScore(v) {
  if (v === undefined || v === null || v === '') return true;
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 && n <= 100;
}

const gdGradeController = {
  uploadMiddleware: upload.single('file'),

  async list(req, res) {
    try {
      const { class_id, student_id, keyword } = req.query;
      const user = req.user;
      const filter = {
        classId:   class_id   !== undefined ? Number(class_id)   : undefined,
        studentId: student_id !== undefined ? Number(student_id) : undefined,
        keyword
      };
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 3) filter.teacherId = user.id;
      if (user.role === 4) filter.studentId = user.id;
      if (user.role === 5) filter.studentId = -1; // 企业导师无权查看毕设成绩

      const result = await gdGradeModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取成绩列表成功');
    } catch (err) {
      return error(res, '获取成绩列表失败：' + err.message, 500);
    }
  },

  // 学生查看本人成绩
  async mine(req, res) {
    try {
      const g = await gdGradeModel.findByStudent(req.user.id);
      if (g && !g.published) return success(res, null, '成绩尚未发布');
      return success(res, g, '获取本人成绩成功');
    } catch (err) {
      return error(res, '获取成绩失败：' + err.message, 500);
    }
  },

  // 录入/更新单个学生成绩（教师）
  async upsert(req, res) {
    try {
      const { student_id, topic_id, class_id, topic_title, review_score, defense_score, total_score, remark } = req.body;
      if (!student_id) return error(res, '请指定学生', 400);
      if (!validScore(review_score) || !validScore(defense_score) || !validScore(total_score)) {
        return error(res, '成绩需在 0-100 之间', 400);
      }
      await gdGradeModel.upsert({
        student_id: Number(student_id), topic_id, teacher_id: req.user.id,
        class_id, topic_title, review_score, defense_score, total_score, remark
      });
      const g = await gdGradeModel.findByStudent(Number(student_id));
      await notify(Number(student_id), '毕业设计成绩已录入',
        `你的毕业设计成绩已录入${total_score !== undefined && total_score !== '' ? '，综合成绩 ' + total_score : ''}`, 'info');
      return success(res, g, '成绩已保存');
    } catch (err) {
      return error(res, '保存成绩失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const g = await gdGradeModel.findById(id);
      if (!g) return error(res, '成绩记录不存在', 404);
      await gdGradeModel.remove(id);
      return success(res, null, '删除成功');
    } catch (err) {
      return error(res, '删除失败：' + err.message, 500);
    }
  },

  // Excel 批量导入成绩（列：学号 / 评阅成绩 / 答辩成绩 / 综合成绩 / 选题名称）
  async importExcel(req, res) {
    if (!req.file) return error(res, '请上传 Excel 文件', 400);
    let conn;
    try {
      const wb = XLSX.read(req.file.buffer, { type: 'buffer' });
      const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
      if (!rows.length) return error(res, 'Excel 文件为空', 400);
      if (rows.length > MAX_IMPORT_ROWS) return error(res, `单次最多导入 ${MAX_IMPORT_ROWS} 条`, 400);

      const results = { success: 0, errors: [] };
      conn = await pool.getConnection();
      await conn.beginTransaction();

      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const lineNo = i + 2;
        const eeid = String(row['学号'] || row['学生学号'] || '').trim();
        if (!eeid) { results.errors.push(`第 ${lineNo} 行：学号为空`); continue; }
        const review = row['评阅成绩'] ?? row['评阅'];
        const defense = row['答辩成绩'] ?? row['答辩'];
        const total = row['综合成绩'] ?? row['综合'];
        if (!validScore(review) || !validScore(defense) || !validScore(total)) {
          results.errors.push(`第 ${lineNo} 行：成绩需在 0-100 之间`); continue;
        }
        const [s] = await conn.query('SELECT id, college_id, class_id FROM t_user WHERE eeid = ? AND role = 4 AND is_deleted = 0 LIMIT 1', [eeid]);
        if (!s.length) { results.errors.push(`第 ${lineNo} 行：未找到学号 ${eeid}`); continue; }
        if (req.user.role === 3) {
          // 教师导入仅限自己指导的学生（有选题关系）
          const [own] = await conn.query('SELECT id FROM t_gd_topic WHERE student_id = ? AND teacher_id = ? AND is_deleted = 0 LIMIT 1', [s[0].id, req.user.id]);
          if (!own.length) { results.errors.push(`第 ${lineNo} 行：${eeid} 非你指导的学生`); continue; }
        }
        await gdGradeModel.upsert({
          student_id: s[0].id, teacher_id: req.user.id, class_id: s[0].class_id,
          topic_title: String(row['选题名称'] || row['题目'] || '').trim() || null,
          review_score: review, defense_score: defense, total_score: total
        }, conn);
        results.success++;
      }
      await conn.commit();
      return success(res, results, `导入完成：成功 ${results.success} 条，失败 ${results.errors.length} 条`);
    } catch (err) {
      if (conn) { try { await conn.rollback(); } catch (_) { /* ignore */ } }
      return error(res, '导入失败：' + err.message, 500);
    } finally {
      if (conn) conn.release();
    }
  }
};

module.exports = gdGradeController;
