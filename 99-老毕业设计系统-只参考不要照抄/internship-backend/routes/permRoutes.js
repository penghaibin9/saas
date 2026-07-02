const express = require('express');
const permController = require('../controllers/permController');
const { requireRole } = require('../middlewares/auth');

const router = express.Router();

// 任意登录用户：查看自身权限 + 权限码目录
router.get('/my', permController.myPerms);
router.get('/catalog', permController.catalog);

// 角色/授权管理：院校/分院管理员
const admin = requireRole(1, 2);
router.get('/roles',         admin, permController.listRoles);
router.post('/roles',        admin, permController.createRole);
router.put('/roles/:id/perms', admin, permController.setPerms);
router.delete('/roles/:id',  admin, permController.removeRole);
router.post('/assign',       admin, permController.assignUser);
router.post('/revoke',       admin, permController.revokeUser);

module.exports = router;
