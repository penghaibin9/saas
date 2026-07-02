const { positionModel, enterpriseModel, collegeModel, userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

const positionController = {
  // 学生岗位智能推荐（按技能标签/学院匹配排序）
  async recommend(req, res) {
    try {
      const student = await userModel.findById(req.user.id);
      if (!student) return error(res, '用户不存在', 404);
      const list = await positionModel.recommendForStudent(student, Number(req.query.limit) || 10);
      return success(res, { list, hasTags: !!(student.skill_tags && student.skill_tags.trim()) }, '获取推荐岗位成功');
    } catch (err) {
      return error(res, '获取推荐岗位失败：' + err.message, 500);
    }
  },

  async list(req, res) {
    try {
      const { enterprise_id, college_id, status, keyword, intern_type } = req.query;
      const result = await positionModel.findAll(
        {
          enterpriseId: enterprise_id !== undefined && enterprise_id !== '' ? Number(enterprise_id) : undefined,
          collegeId:    college_id    !== undefined && college_id    !== '' ? Number(college_id)    : undefined,
          status:       status        !== undefined && status        !== '' ? Number(status)        : undefined,
          internType:   intern_type   !== undefined && intern_type   !== '' ? Number(intern_type)   : undefined,
          keyword
        },
        clampPagination(req.query)
      );
      return success(res, result, '获取岗位列表成功');
    } catch (err) {
      return error(res, '获取岗位列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const position = await positionModel.findById(Number(req.params.id));
      if (!position) return error(res, '岗位不存在', 404);
      return success(res, position, '获取岗位详情成功');
    } catch (err) {
      return error(res, '获取岗位详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { enterprise_id, title, description, requirement, salary, headcount, location, start_date, end_date, college_id, tags,
        intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline } = req.body;
      if (!enterprise_id || !title) return error(res, '企业和岗位名称不能为空', 400);

      const enterprise = await enterpriseModel.findById(Number(enterprise_id));
      if (!enterprise) return error(res, '企业不存在', 404);

      if (college_id !== undefined && college_id !== null) {
        const college = await collegeModel.findById(Number(college_id));
        if (!college) return error(res, '所属学院不存在', 404);
      }

      const id = await positionModel.create({
        enterprise_id: Number(enterprise_id), title, description, requirement,
        salary, headcount, location, start_date, end_date, tags,
        college_id: college_id !== undefined && college_id !== null ? Number(college_id) : null,
        intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline
      });
      const position = await positionModel.findById(id);
      return success(res, position, '创建岗位成功', 201);
    } catch (err) {
      return error(res, '创建岗位失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const position = await positionModel.findById(id);
      if (!position) return error(res, '岗位不存在', 404);

      const { enterprise_id, college_id, title, description, requirement, salary, headcount, location, start_date, end_date, status, tags,
        intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline } = req.body;
      if (enterprise_id !== undefined) {
        if (!enterprise_id) return error(res, '企业不能为空', 400);
        const enterprise = await enterpriseModel.findById(Number(enterprise_id));
        if (!enterprise) return error(res, '企业不存在', 404);
      }
      if (college_id !== undefined && college_id !== null) {
        const college = await collegeModel.findById(Number(college_id));
        if (!college) return error(res, '所属学院不存在', 404);
      }

      await positionModel.update(id, {
        enterprise_id: enterprise_id !== undefined ? Number(enterprise_id) : undefined,
        college_id: college_id !== undefined ? Number(college_id) : undefined,
        title, description, requirement, salary,
        headcount, location, start_date, end_date, status, tags,
        intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline
      });
      const updated = await positionModel.findById(id);
      return success(res, updated, '更新岗位成功');
    } catch (err) {
      return error(res, '更新岗位失败：' + err.message, 500);
    }
  },

  async toggleStatus(req, res) {
    try {
      const id = Number(req.params.id);
      const position = await positionModel.findById(id);
      if (!position) return error(res, '岗位不存在', 404);
      const newStatus = position.status === 1 ? 0 : 1;
      await positionModel.update(id, { status: newStatus });
      return success(res, { status: newStatus }, newStatus === 1 ? '岗位已上架' : '岗位已下架');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  },

  /** 待审核岗位（企业自助发布 status=0） */
  async pending(req, res) {
    try {
      const result = await positionModel.findAll({ status: 0 }, clampPagination(req.query));
      return success(res, result, '获取待审核岗位成功');
    } catch (err) {
      return error(res, '获取待审核岗位失败：' + err.message, 500);
    }
  },

  async audit(req, res) {
    try {
      const id = Number(req.params.id);
      const position = await positionModel.findById(id);
      if (!position) return error(res, '岗位不存在', 404);
      if (position.status !== 0) return error(res, '该岗位不在待审核状态', 400);
      const approve = req.body && (req.body.approve === true || req.body.approve === 'true' || req.body.approve === 1);
      await positionModel.update(id, { status: approve ? 1 : 2 });
      return success(res, { status: approve ? 1 : 2 }, approve ? '岗位已审核通过并上架' : '岗位已驳回');
    } catch (err) {
      return error(res, '审核失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const position = await positionModel.findById(id);
      if (!position) return error(res, '岗位不存在', 404);
      await positionModel.remove(id);
      return success(res, null, '删除岗位成功');
    } catch (err) {
      return error(res, '删除岗位失败：' + err.message, 500);
    }
  }
};

module.exports = positionController;
