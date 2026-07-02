const { defenseModel, userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

// 角色：1超管 2分院 3教师(评委) 4学生
const isAdmin = (u) => u.role === 1 || u.role === 2;

const defenseController = {
  /* ---------- 答辩组 ---------- */
  async listGroups(req, res) {
    try {
      const u = req.user;
      const filter = {};
      if (req.query.status !== undefined) filter.status = Number(req.query.status);
      if (u.role === 2) filter.collegeId = u.collegeId;
      if (u.role === 3) filter.teacherId = u.id; // 教师仅看自己参与评审的组
      const result = await defenseModel.listGroups(filter, clampPagination(req.query));
      return success(res, result, '获取答辩分组成功');
    } catch (err) { return error(res, '获取答辩分组失败：' + err.message, 500); }
  },

  async groupDetail(req, res) {
    try {
      const id = Number(req.params.id);
      const group = await defenseModel.getGroup(id);
      if (!group) return error(res, '答辩组不存在', 404);
      const u = req.user;
      if (u.role === 2 && group.college_id !== u.collegeId) return error(res, '无权查看', 403);
      const isJudge = u.role === 3 && await defenseModel.isJudge(id, u.id);
      if (u.role === 3 && !isJudge) return error(res, '你不是该答辩组评委', 403);
      if (u.role === 4) return error(res, '无权查看', 403);

      const committee = await defenseModel.listCommittee(id);
      const members = await defenseModel.listMembers(id);

      // 评委视角：双盲，仅回填本人评分，隐藏汇总分
      if (isJudge && !isAdmin(u)) {
        const myScores = await defenseModel.judgeScores(id, u.id);
        members.forEach(m => {
          const s = myScores[m.student_id];
          m.my_score = s ? s.score : null;
          m.my_comment = s ? s.comment : null;
          delete m.final_score; delete m.recommended;
        });
        return success(res, { group, committee, members, role: 'judge' }, '获取答辩详情成功');
      }
      // 管理员视角：附每个学生的全部评委评分
      for (const m of members) m.scores = await defenseModel.studentScores(m.student_id);
      return success(res, { group, committee, members, role: 'admin' }, '获取答辩详情成功');
    } catch (err) { return error(res, '获取答辩详情失败：' + err.message, 500); }
  },

  async createGroup(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      const { name, defense_date, location, remark } = req.body;
      if (!name) return error(res, '请填写答辩组名称', 400);
      const college_id = req.user.role === 2 ? req.user.collegeId : (req.body.college_id || null);
      const id = await defenseModel.createGroup({ name, defense_date, location, remark, college_id });
      return success(res, { id }, '答辩组已创建', 201);
    } catch (err) { return error(res, '创建失败：' + err.message, 500); }
  },

  async updateGroup(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      await defenseModel.updateGroup(Number(req.params.id), req.body);
      return success(res, null, '已更新');
    } catch (err) { return error(res, '更新失败：' + err.message, 500); }
  },

  async removeGroup(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      await defenseModel.removeGroup(Number(req.params.id));
      return success(res, null, '已删除');
    } catch (err) { return error(res, '删除失败：' + err.message, 500); }
  },

  /* ---------- 评委 ---------- */
  async addCommittee(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      const { teacher_id, role } = req.body;
      if (!teacher_id) return error(res, '请选择评委教师', 400);
      await defenseModel.addCommittee(Number(req.params.id), Number(teacher_id), role);
      const group = await defenseModel.getGroup(Number(req.params.id));
      await notify(Number(teacher_id), '答辩评委安排', `你被安排为答辩组「${group ? group.name : ''}」评委`, 'info');
      return success(res, null, '已添加评委');
    } catch (err) { return error(res, '添加评委失败：' + err.message, 500); }
  },
  async removeCommittee(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      await defenseModel.removeCommittee(Number(req.params.cid));
      return success(res, null, '已移除评委');
    } catch (err) { return error(res, '移除失败：' + err.message, 500); }
  },

  /* ---------- 答辩学生 ---------- */
  async addMember(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      const { student_id, achievement_id, seq } = req.body;
      if (!student_id) return error(res, '请选择学生', 400);
      await defenseModel.addMember(Number(req.params.id), Number(student_id), achievement_id, seq);
      return success(res, null, '已添加答辩学生');
    } catch (err) { return error(res, '添加失败：' + err.message, 500); }
  },
  async removeMember(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      await defenseModel.removeMember(Number(req.params.mid));
      return success(res, null, '已移除');
    } catch (err) { return error(res, '移除失败：' + err.message, 500); }
  },
  async setRecommend(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      const m = await defenseModel.getMember(Number(req.params.mid));
      if (!m) return error(res, '记录不存在', 404);
      await defenseModel.setRecommended(m.id, req.body.recommended ? 1 : 0);
      if (req.body.recommended) await notify(m.student_id, '推优公示', '恭喜，你的毕业设计被推荐为优秀！', 'success');
      return success(res, null, '已更新推优状态');
    } catch (err) { return error(res, '操作失败：' + err.message, 500); }
  },

  /* ---------- 评分（评委） ---------- */
  async score(req, res) {
    try {
      const groupId = Number(req.params.id);
      const studentId = Number(req.params.sid);
      const u = req.user;
      const allowed = isAdmin(u) || (u.role === 3 && await defenseModel.isJudge(groupId, u.id));
      if (!allowed) return error(res, '你不是该答辩组评委', 403);
      const score = Number(req.body.score);
      if (!(score >= 0 && score <= 100)) return error(res, '评分需在 0~100 之间', 400);
      await defenseModel.upsertScore(groupId, studentId, u.id, score, req.body.comment);
      return success(res, null, '评分已保存');
    } catch (err) { return error(res, '评分失败：' + err.message, 500); }
  },

  // 汇总（管理员）：均分写入 final_score 并置组为已完成
  async finalize(req, res) {
    try {
      if (!isAdmin(req.user)) return error(res, '无权操作', 403);
      const n = await defenseModel.finalizeGroup(Number(req.params.id));
      return success(res, { finalized: n }, `已汇总 ${n} 名学生成绩`);
    } catch (err) { return error(res, '汇总失败：' + err.message, 500); }
  }
};

module.exports = defenseController;
