const path = require('path');
const XLSX = require('xlsx');
const multer = require('multer');
const pool = require('../config/db');
const { gdTopicModel, userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

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

const gdTopicController = {
  uploadMiddleware: upload.single('file'),

  async list(req, res) {
    try {
      const { teacher_id, student_id, class_id, status, keyword } = req.query;
      const user = req.user;
      const filter = {
        teacherId: teacher_id !== undefined ? Number(teacher_id) : undefined,
        studentId: student_id !== undefined ? Number(student_id) : undefined,
        classId:   class_id   !== undefined ? Number(class_id)   : undefined,
        status:    status      !== undefined ? Number(status)     : undefined,
        keyword
      };
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 3) filter.teacherId = user.id;
      if (user.role === 4) filter.studentId = user.id;
      if (user.role === 5) filter.studentId = -1; // 企业导师无权查看毕设选题

      const result = await gdTopicModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取选题列表成功');
    } catch (err) {
      return error(res, '获取选题列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await gdTopicModel.findById(Number(req.params.id));
      if (!item) return error(res, '选题不存在', 404);
      const user = req.user;
      if (user.role === 4 && item.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 3 && item.teacher_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 2 && item.student_college_id && item.student_college_id !== user.collegeId) return error(res, '权限不足', 403);
      return success(res, item, '获取选题详情成功');
    } catch (err) {
      return error(res, '获取选题详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { title, student_id, teacher_id } = req.body;
      if (!title) return error(res, '选题名称不能为空', 400);

      if (teacher_id) {
        const teacher = await userModel.findById(Number(teacher_id));
        if (!teacher || teacher.role !== 3) return error(res, '指导教师无效', 400);
      }
      let college_id = req.body.college_id;
      if (req.user.role === 2) college_id = req.user.collegeId;

      const id = await gdTopicModel.create({ ...req.body, college_id, student_id, teacher_id });
      const item = await gdTopicModel.findById(id);
      return success(res, item, '创建选题成功', 201);
    } catch (err) {
      return error(res, '创建选题失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdTopicModel.findById(id);
      if (!item) return error(res, '选题不存在', 404);
      if (req.user.role === 2 && item.student_college_id && item.student_college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      if (req.body.teacher_id) {
        const teacher = await userModel.findById(Number(req.body.teacher_id));
        if (!teacher || teacher.role !== 3) return error(res, '指导教师无效', 400);
      }
      await gdTopicModel.update(id, req.body);
      const updated = await gdTopicModel.findById(id);
      return success(res, updated, '更新选题成功');
    } catch (err) {
      return error(res, '更新选题失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdTopicModel.findById(id);
      if (!item) return error(res, '选题不存在', 404);
      await gdTopicModel.remove(id);
      return success(res, null, '删除选题成功');
    } catch (err) {
      return error(res, '删除选题失败：' + err.message, 500);
    }
  },

  // 学生主动选题（从题库中选择，status 1→0 待确认）
  async select(req, res) {
    try {
      if (req.user.role !== 4) return error(res, '只有学生可以选题', 403);
      const id = Number(req.params.id);
      const item = await gdTopicModel.findById(id);
      if (!item) return error(res, '课题不存在', 404);
      if (item.status !== 1) return error(res, '该课题当前不可选（非开放状态）', 400);
      if (item.student_id) return error(res, '该课题已被其他同学选定', 409);

      await gdTopicModel.update(id, { student_id: req.user.id, status: 0 });
      const updated = await gdTopicModel.findById(id);
      return success(res, updated, '选题申请已提交，等待教师确认');
    } catch (err) {
      return error(res, '选题失败：' + err.message, 500);
    }
  },

  // 指导教师确认 / 驳回学生选题（status 0→1 确认，0→2 驳回）
  async confirm(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdTopicModel.findById(id);
      if (!item) return error(res, '选题不存在', 404);
      if (req.user.role !== 3) return error(res, '只有指导教师可以确认选题', 403);
      if (item.teacher_id && item.teacher_id !== req.user.id) return error(res, '权限不足，非本人指导的选题', 403);
      if (item.status !== 0) return error(res, '该选题已审阅，无需重复操作', 400);

      const { agree, opinion } = req.body;
      if (agree === undefined) return error(res, '请指定审阅结果', 400);

      const newStatus = agree ? 1 : 2;
      await gdTopicModel.update(id, { status: newStatus });
      const updated = await gdTopicModel.findById(id);
      return success(res, updated, agree ? '已确认选题' : '已驳回选题');
    } catch (err) {
      return error(res, '确认选题失败：' + err.message, 500);
    }
  },

  // 教师配备：Excel 导入（列含 学生学号 / 老师工号 / 选题名称）
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
        const stuEeid = String(row['学生学号'] || row['学号'] || '').trim();
        const teaEeid = String(row['老师工号'] || row['教师工号'] || row['工号'] || '').trim();
        const title   = String(row['选题名称'] || row['课题名称'] || row['题目'] || '').trim();
        if (!title) { results.errors.push(`第 ${lineNo} 行：选题名称为空`); continue; }

        let studentId = null, collegeId = null, majorId = null, classId = null;
        if (stuEeid) {
          const [s] = await conn.query('SELECT id, college_id, major_id, class_id FROM t_user WHERE eeid = ? AND role = 4 AND is_deleted = 0 LIMIT 1', [stuEeid]);
          if (!s.length) { results.errors.push(`第 ${lineNo} 行：未找到学号 ${stuEeid}`); continue; }
          if (req.user.role === 2 && s[0].college_id !== req.user.collegeId) { results.errors.push(`第 ${lineNo} 行：学生不属于本学院`); continue; }
          studentId = s[0].id; collegeId = s[0].college_id; majorId = s[0].major_id; classId = s[0].class_id;
        }
        let teacherId = null;
        if (teaEeid) {
          const [t] = await conn.query('SELECT id FROM t_user WHERE eeid = ? AND role = 3 AND is_deleted = 0 LIMIT 1', [teaEeid]);
          if (!t.length) { results.errors.push(`第 ${lineNo} 行：未找到工号 ${teaEeid}`); continue; }
          teacherId = t[0].id;
        }
        await gdTopicModel.create({
          title, student_id: studentId, teacher_id: teacherId,
          college_id: req.user.role === 2 ? req.user.collegeId : collegeId,
          major_id: majorId, class_id: classId
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

module.exports = gdTopicController;
