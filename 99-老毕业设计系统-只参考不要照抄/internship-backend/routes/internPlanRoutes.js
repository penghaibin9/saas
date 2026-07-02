const express = require('express');
const { internPlanController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 查询：所有登录用户（按角色过滤）
router.get('/',    authMiddleware, internPlanController.list);
router.get('/:id', authMiddleware, internPlanController.detail);

// 制定/修改：院校 & 分院管理员
router.post('/',        authMiddleware, requireRole(1, 2), internPlanController.create);
router.put('/:id',      authMiddleware, requireRole(1, 2), internPlanController.update);
router.delete('/:id',   authMiddleware, requireRole(1, 2), internPlanController.remove);

// 审批：仅院校管理员
router.put('/:id/approve', authMiddleware, requireRole(1), internPlanController.approve);

// 开启/结束：院校 & 分院管理员
router.put('/:id/open',  authMiddleware, requireRole(1, 2), internPlanController.open);
router.put('/:id/close', authMiddleware, requireRole(1, 2), internPlanController.close);

module.exports = router;
