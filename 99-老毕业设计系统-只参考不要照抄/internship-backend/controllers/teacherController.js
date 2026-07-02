const pwdHash = require('../utils/password');
const pool = require('../config/db');
const { userModel, internStatsModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

// 教师专属：我的实习生 + 帮助学生重置密码
const teacherController = {
  // 我的实习生（含签到/周报/月报完成情况）
  async myStudents(req, res) {
    try {
      const result = await internStatsModel.processStats(req.user, clampPagination(req.query));
      return success(res, result, '获取我的实习生成功');
    } catch (err) {
      return error(res, '获取我的实习生失败：' + err.message, 500);
    }
  },

  // 帮助所指导的学生重置登录密码（重置后强制学生改密）
  async resetStudentPassword(req, res) {
    try {
      const studentId = Number(req.params.id);
      const [rows] = await pool.query(
        'SELECT 1 FROM t_assignment WHERE teacher_id = ? AND student_id = ? AND status = 1 AND is_deleted = 0 LIMIT 1',
        [req.user.id, studentId]
      );
      if (!rows.length) return error(res, '只能重置自己指导学生的密码', 403);

      const student = await userModel.findById(studentId);
      if (!student || student.role !== 4) return error(res, '学生无效', 404);

      const newPwd = req.body.password || '123456';
      if (typeof newPwd !== 'string' || newPwd.length < 6) return error(res, '密码不能少于6位', 400);

      const hash = await pwdHash.hash(newPwd);
      await userModel.updatePassword(studentId, hash, { mustChange: 1 });
      return success(res, null, '已重置该学生密码，学生下次登录需修改');
    } catch (err) {
      return error(res, '重置失败：' + err.message, 500);
    }
  }
};

module.exports = teacherController;
