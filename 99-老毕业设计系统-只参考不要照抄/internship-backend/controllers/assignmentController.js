const path = require('path');
const XLSX = require('xlsx');
const multer = require('multer');
const pool = require('../config/db');
const { assignmentModel, userModel, enterpriseModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

const MAX_IMPORT_ROWS = 1000;

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (['.xlsx', '.xls'].includes(ext)) cb(null, true);
    else cb(new Error('仅支持 .xlsx / .xls 格式的 Excel 文件'));
  }
});

const assignmentController = {
  uploadMiddleware: upload.single('file'),

  async list(req, res) {
    try {
      const { plan_id, student_id, teacher_id, enterprise_id, status } = req.query;
      const user = req.user;
      const filter = {
        planId:       plan_id       !== undefined ? Number(plan_id)       : undefined,
        studentId:    student_id    !== undefined ? Number(student_id)    : undefined,
        teacherId:    teacher_id    !== undefined ? Number(teacher_id)    : undefined,
        enterpriseId: enterprise_id !== undefined ? Number(enterprise_id) : undefined,
        status:       status        !== undefined ? Number(status)        : undefined,
      };
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 3) filter.teacherId = user.id;
      if (user.role === 4) filter.studentId = user.id;
      if (user.role === 5) filter.enterpriseId = user.enterpriseId || -1; // 企业导师仅限本企业

      const result = await assignmentModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取实习分配列表成功');
    } catch (err) {
      return error(res, '获取实习分配列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await assignmentModel.findById(Number(req.params.id));
      if (!item) return error(res, '分配记录不存在', 404);
      const user = req.user;
      if (user.role === 4 && item.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 3 && item.teacher_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 2 && item.student_college_id !== user.collegeId) return error(res, '权限不足', 403);
      return success(res, item, '获取分配详情成功');
    } catch (err) {
      return error(res, '获取分配详情失败：' + err.message, 500);
    }
  },

  // 手动为单个学生分配
  async create(req, res) {
    try {
      const { plan_id, student_id, teacher_id, enterprise_id } = req.body;
      if (!student_id) return error(res, '请指定学生', 400);

      const student = await userModel.findById(Number(student_id));
      if (!student || student.role !== 4) return error(res, '学生无效', 400);
      if (req.user.role === 2 && student.college_id !== req.user.collegeId) {
        return error(res, '只能分配本学院的学生', 403);
      }

      if (teacher_id) {
        const teacher = await userModel.findById(Number(teacher_id));
        if (!teacher || teacher.role !== 3) return error(res, '指导教师无效', 400);
        if (req.user.role === 2 && teacher.college_id !== req.user.collegeId) {
          return error(res, '只能分配本学院的指导教师', 403);
        }
      }
      if (enterprise_id) {
        const ent = await enterpriseModel.findById(Number(enterprise_id));
        if (!ent) return error(res, '实习企业不存在', 404);
      }

      const dup = await assignmentModel.findExisting(Number(student_id), plan_id ? Number(plan_id) : null);
      if (dup) return error(res, '该学生在此计划下已有分配记录', 409);

      const id = await assignmentModel.create({
        plan_id: plan_id ? Number(plan_id) : null,
        student_id: Number(student_id),
        teacher_id: teacher_id ? Number(teacher_id) : null,
        enterprise_id: enterprise_id ? Number(enterprise_id) : null
      });
      const item = await assignmentModel.findById(id);
      return success(res, item, '分配成功', 201);
    } catch (err) {
      return error(res, '分配失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await assignmentModel.findById(id);
      if (!item) return error(res, '分配记录不存在', 404);
      if (req.user.role === 2 && item.student_college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }

      const { teacher_id, enterprise_id, plan_id } = req.body;
      if (teacher_id) {
        const teacher = await userModel.findById(Number(teacher_id));
        if (!teacher || teacher.role !== 3) return error(res, '指导教师无效', 400);
      }
      if (enterprise_id) {
        const ent = await enterpriseModel.findById(Number(enterprise_id));
        if (!ent) return error(res, '实习企业不存在', 404);
      }

      await assignmentModel.update(id, {
        teacher_id: teacher_id !== undefined ? (teacher_id ? Number(teacher_id) : null) : undefined,
        enterprise_id: enterprise_id !== undefined ? (enterprise_id ? Number(enterprise_id) : null) : undefined,
        plan_id: plan_id !== undefined ? (plan_id ? Number(plan_id) : null) : undefined
      });
      const updated = await assignmentModel.findById(id);
      return success(res, updated, '分配已更新');
    } catch (err) {
      return error(res, '更新分配失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await assignmentModel.findById(id);
      if (!item) return error(res, '分配记录不存在', 404);
      if (req.user.role === 2 && item.student_college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      await assignmentModel.remove(id);
      return success(res, null, '已移除该学生的分配');
    } catch (err) {
      return error(res, '移除失败：' + err.message, 500);
    }
  },

  // Excel 批量分配：列含 老师工号 / 学生学号 / 企业名称(或组织机构代码)
  async importExcel(req, res) {
    if (!req.file) return error(res, '请上传 Excel 文件', 400);
    let conn;
    try {
      const wb = XLSX.read(req.file.buffer, { type: 'buffer' });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(ws);
      if (!rows.length) return error(res, 'Excel 文件为空', 400);
      if (rows.length > MAX_IMPORT_ROWS) return error(res, `单次最多导入 ${MAX_IMPORT_ROWS} 条`, 400);

      const results = { success: 0, skip: 0, errors: [] };
      conn = await pool.getConnection();
      await conn.beginTransaction();

      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const lineNo = i + 2;
        const stuEeid = String(row['学生学号'] || row['学号'] || row['student_eeid'] || '').trim();
        const teaEeid = String(row['老师工号'] || row['教师工号'] || row['工号'] || row['teacher_eeid'] || '').trim();
        const entName = String(row['企业名称'] || row['企业组织机构代码'] || row['enterprise'] || '').trim();

        if (!stuEeid) { results.errors.push(`第 ${lineNo} 行：学生学号为空`); continue; }

        const [stuRows] = await conn.query(
          'SELECT id, college_id FROM t_user WHERE eeid = ? AND role = 4 AND is_deleted = 0 LIMIT 1', [stuEeid]
        );
        if (!stuRows.length) { results.errors.push(`第 ${lineNo} 行：未找到学号为 ${stuEeid} 的学生`); continue; }
        const student = stuRows[0];
        if (req.user.role === 2 && student.college_id !== req.user.collegeId) {
          results.errors.push(`第 ${lineNo} 行：学生 ${stuEeid} 不属于本学院`); continue;
        }

        let teacherId = null;
        if (teaEeid) {
          const [teaRows] = await conn.query(
            'SELECT id FROM t_user WHERE eeid = ? AND role = 3 AND is_deleted = 0 LIMIT 1', [teaEeid]
          );
          if (!teaRows.length) { results.errors.push(`第 ${lineNo} 行：未找到工号为 ${teaEeid} 的指导教师`); continue; }
          teacherId = teaRows[0].id;
        }

        let enterpriseId = null;
        if (entName) {
          const [entRows] = await conn.query(
            'SELECT id FROM t_enterprise WHERE name = ? AND is_deleted = 0 LIMIT 1', [entName]
          );
          if (!entRows.length) { results.errors.push(`第 ${lineNo} 行：未找到企业 ${entName}`); continue; }
          enterpriseId = entRows[0].id;
        }

        const [dup] = await conn.query(
          'SELECT id FROM t_assignment WHERE student_id = ? AND plan_id IS NULL AND status = 1 AND is_deleted = 0 LIMIT 1',
          [student.id]
        );
        if (dup.length) { results.skip++; continue; }

        await conn.query(
          'INSERT INTO t_assignment (student_id, teacher_id, enterprise_id, status) VALUES (?, ?, ?, 1)',
          [student.id, teacherId, enterpriseId]
        );
        results.success++;
      }

      await conn.commit();
      return success(res, results, `导入完成：成功 ${results.success} 条，跳过 ${results.skip} 条，失败 ${results.errors.length} 条`);
    } catch (err) {
      if (conn) { try { await conn.rollback(); } catch (_) { /* ignore */ } }
      return error(res, '导入失败：' + err.message, 500);
    } finally {
      if (conn) conn.release();
    }
  },

  // 下载分配导入模板
  async downloadTemplate(req, res) {
    const data = [{ 学生学号: '20240001', 老师工号: 'T1001', 企业名称: '杭州软件科技有限公司' }];
    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, '实习分配模板');
    const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', 'attachment; filename="assignment_import_template.xlsx"');
    return res.send(buf);
  }
};

module.exports = assignmentController;
