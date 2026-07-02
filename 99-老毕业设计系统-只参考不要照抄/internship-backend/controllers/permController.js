const permModel = require('../models/permModel');
const { success, error } = require('../utils/response');

// 角色/权限管理（院校管理员，或被授予 perm:admin 的自定义角色）
const permController = {
  // 权限码目录 + 数据范围选项（前端配置角色用）
  catalog(req, res) {
    return success(res, { permissions: permModel.PERMISSIONS, scopes: permModel.SCOPES }, '权限目录');
  },

  async listRoles(req, res) {
    try { return success(res, await permModel.listRoles(), '自定义角色列表'); }
    catch (e) { return error(res, e.message, 500); }
  },

  async createRole(req, res) {
    try {
      const { name, code, data_scope, remark, perms } = req.body;
      if (!name || !code) return error(res, '角色名与编码不能为空', 400);
      if (!/^[a-zA-Z0-9_]+$/.test(code)) return error(res, '编码仅限字母数字下划线', 400);
      const id = await permModel.createRole({ name, code, data_scope, remark, perms });
      return success(res, { id }, '已创建', 201);
    } catch (e) {
      if (e.code === 'ER_DUP_ENTRY') return error(res, '角色编码已存在', 409);
      return error(res, '创建失败：' + e.message, 500);
    }
  },

  async setPerms(req, res) {
    try {
      await permModel.setPerms(Number(req.params.id), req.body.perms || []);
      return success(res, null, '权限已更新');
    } catch (e) { return error(res, e.message, 500); }
  },

  async removeRole(req, res) {
    try { await permModel.removeRole(Number(req.params.id)); return success(res, null, '已删除'); }
    catch (e) { return error(res, e.message, 500); }
  },

  async assignUser(req, res) {
    try {
      const { user_id, role_id } = req.body;
      if (!user_id || !role_id) return error(res, '用户与角色不能为空', 400);
      await permModel.assignToUser(Number(user_id), Number(role_id));
      return success(res, null, '已分配');
    } catch (e) { return error(res, e.message, 500); }
  },

  async revokeUser(req, res) {
    try {
      await permModel.revokeFromUser(Number(req.body.user_id), Number(req.body.role_id));
      return success(res, null, '已取消');
    } catch (e) { return error(res, e.message, 500); }
  },

  // 当前用户自身的权限码与数据范围（前端按需展示/隐藏功能）
  async myPerms(req, res) {
    try {
      if (req.user.role === 1) return success(res, { perms: ['*'], scope: 'all', superadmin: true }, '我的权限');
      const r = await permModel.getUserPerms(req.user.id);
      return success(res, { ...r, superadmin: false }, '我的权限');
    } catch (e) { return error(res, e.message, 500); }
  },
};

module.exports = permController;
